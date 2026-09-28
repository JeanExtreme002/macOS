# -*- coding: utf-8 -*-

"""
Global keyboard shortcuts: run a function when a key combination is pressed, in any app.

::

    def screenshot():
        macos.screenshot("~/Desktop/shot.png")

    macos.hotkeys.register("ctrl+option+s", screenshot)
    macos.hotkeys.run()                       # until macos.hotkeys.stop() or Ctrl-C

    macos.hotkeys.wait("cmd+shift+k")         # or just wait for one press

Shortcuts are written as for :func:`macos.keyboard.press`. A registered
shortcut doesn't reach the app in front. Listening to the keyboard needs the
*Input Monitoring* permission for the app running Python (your terminal or
IDE), and keeping the shortcut from the app in front needs *Accessibility*.
"""

import ctypes
import threading
import time
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Tuple, Union

from . import keyboard
from ._system import framework
from .errors import PermissionDeniedError

__all__ = ["Hotkey", "register", "unregister", "run", "stop", "wait", "has_permission", "request_permission"]

_KEY_DOWN, _KEY_UP = 10, 11  # kCGEventKeyDown, kCGEventKeyUp
_TAP_DISABLED = (0xFFFFFFFE, 0xFFFFFFFF)  # by timeout, by user input: turn the tap back on
_KEY_CODE = 9  # kCGKeyboardEventKeycode
_AUTOREPEAT = 8  # kCGKeyboardEventAutorepeat: the key is held, repeating
_SESSION_TAP = 1  # kCGSessionEventTap
_HEAD = 0  # kCGHeadInsertEventTap
# The modifiers that tell shortcuts apart; Caps Lock and the keypad flag don't.
_MODIFIERS = (1 << 17) | (1 << 18) | (1 << 19) | (1 << 20) | (1 << 23)

_Callback = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p)


@lru_cache(maxsize=None)
def _graphics() -> ctypes.CDLL:
    cg = framework("CoreGraphics")
    pointer = ctypes.c_void_p
    signatures = {
        "CGPreflightListenEventAccess": ((), ctypes.c_bool),
        "CGRequestListenEventAccess": ((), ctypes.c_bool),
        "CGEventTapCreate": ((ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint64, _Callback, pointer), pointer),
        "CGEventTapEnable": ((pointer, ctypes.c_bool), None),
        "CGEventGetIntegerValueField": ((pointer, ctypes.c_uint32), ctypes.c_int64),
        "CGEventGetFlags": ((pointer,), ctypes.c_uint64),
    }
    for name, (argtypes, restype) in signatures.items():
        function = getattr(cg, name)
        function.argtypes = argtypes
        function.restype = restype
    return cg


@lru_cache(maxsize=None)
def _run_loop() -> ctypes.CDLL:
    cf = framework("CoreFoundation")
    pointer = ctypes.c_void_p
    cf.CFMachPortCreateRunLoopSource.argtypes = (pointer, pointer, ctypes.c_long)
    cf.CFMachPortCreateRunLoopSource.restype = pointer
    cf.CFMachPortInvalidate.argtypes = (pointer,)
    cf.CFMachPortInvalidate.restype = None
    cf.CFRunLoopGetCurrent.argtypes = ()
    cf.CFRunLoopGetCurrent.restype = pointer
    cf.CFRunLoopAddSource.argtypes = (pointer, pointer, pointer)
    cf.CFRunLoopAddSource.restype = None
    cf.CFRunLoopRemoveSource.argtypes = (pointer, pointer, pointer)
    cf.CFRunLoopRemoveSource.restype = None
    cf.CFRunLoopRunInMode.argtypes = (pointer, ctypes.c_double, ctypes.c_bool)
    cf.CFRunLoopRunInMode.restype = ctypes.c_int32
    cf.CFRelease.argtypes = (pointer,)
    cf.CFRelease.restype = None
    return cf


def has_permission() -> bool:
    """Whether this process may listen to the keyboard (Input Monitoring), without prompting the user."""
    return bool(_graphics().CGPreflightListenEventAccess())


def request_permission() -> bool:
    """
    Ask for the Input Monitoring permission, showing the system prompt; return whether it's granted.

    After the user allows the app running Python in System Settings ›
    Privacy & Security › Input Monitoring, that app must be restarted.
    """
    return bool(_graphics().CGRequestListenEventAccess())


class Hotkey:
    """A registered shortcut. :meth:`unregister` removes it."""

    def __init__(self, keys: str, code: int, flags: int, callback: Callable[[], object]) -> None:
        self.keys = keys
        """As passed to :func:`register`, such as ``'cmd+shift+k'``."""
        self.callback = callback
        self._combination = (code, flags)

    def __repr__(self) -> str:
        return "Hotkey({!r})".format(self.keys)

    def unregister(self) -> None:
        """Stop reacting to this shortcut."""
        unregister(self)


_lock = threading.Lock()
_registered: Dict[Tuple[int, int], Hotkey] = {}
_stop = threading.Event()


def _combination(keys: str) -> Tuple[int, int]:
    """The key code and modifier flags of a shortcut such as ``"cmd+shift+k"``."""
    modifiers, code, shifted = keyboard._parse(keys)
    flags = 0
    for flag, _ in modifiers:
        flags |= flag
    if shifted:
        flags |= keyboard._SHIFT[0]
    return code, flags


def register(keys: str, callback: Callable[[], object]) -> Hotkey:
    """
    Call ``callback`` (with no arguments) each time ``keys`` is pressed, in any app, while :func:`run` runs.

    ``keys`` is a shortcut such as ``"ctrl+option+s"`` or ``"f5"``, written
    as for :func:`macos.keyboard.press`. Pick one apps don't use: the app in
    front won't get it. Registering a shortcut again replaces its callback.
    Holding the keys doesn't repeat the call.
    """
    code, flags = _combination(keys)
    hotkey = Hotkey(keys, code, flags, callback)
    with _lock:
        _registered[(code, flags)] = hotkey
    return hotkey


def unregister(hotkey: Union[Hotkey, str]) -> None:
    """Remove a shortcut, given the :class:`Hotkey` :func:`register` returned or its keys."""
    combination = hotkey._combination if isinstance(hotkey, Hotkey) else _combination(hotkey)
    with _lock:
        _registered.pop(combination, None)


def stop() -> None:
    """Make :func:`run` return, from a callback or from another thread."""
    _stop.set()


def _listen(on_press: Callable[[Tuple[int, int]], bool], timeout: Optional[float]) -> None:
    """
    Run an event tap on this thread until ``stop()``, the timeout, or ``on_press`` returning ``True``.

    ``on_press`` gets the pressed combinations that match a shortcut; it runs
    outside the tap, so a slow callback can't make macOS switch the tap off.
    """
    cg, cf = _graphics(), _run_loop()
    pending: List[Tuple[int, int]] = []
    swallowing = set()
    port_holder: List[int] = []

    def tap(proxy: int, kind: int, event: int, refcon: int) -> Optional[int]:
        if kind in _TAP_DISABLED:  # macOS switched the tap off: switch it back on
            if port_holder:
                cg.CGEventTapEnable(port_holder[0], True)
            return event
        if kind not in (_KEY_DOWN, _KEY_UP):
            return event
        code = cg.CGEventGetIntegerValueField(event, _KEY_CODE)
        combination = (code, cg.CGEventGetFlags(event) & _MODIFIERS)
        with _lock:
            matches = combination in _registered
        if kind == _KEY_DOWN and matches:
            if not cg.CGEventGetIntegerValueField(event, _AUTOREPEAT):
                pending.append(combination)
            swallowing.add(code)
            return None  # the app in front never sees it
        if kind == _KEY_UP and code in swallowing:
            swallowing.discard(code)
            return None
        return event

    callback = _Callback(tap)  # kept alive for as long as the tap runs
    mask = (1 << _KEY_DOWN) | (1 << _KEY_UP)
    port = cg.CGEventTapCreate(_SESSION_TAP, _HEAD, 0, mask, callback, None)
    if not port:
        raise PermissionDeniedError(
            "listening to the keyboard needs the Input Monitoring and Accessibility permissions: allow the app "
            "running Python (your terminal or IDE) in System Settings › Privacy & Security, then restart it"
        )
    port_holder.append(port)
    source = cf.CFMachPortCreateRunLoopSource(None, port, 0)
    loop = cf.CFRunLoopGetCurrent()
    mode = ctypes.c_void_p.in_dll(cf, "kCFRunLoopDefaultMode")
    cf.CFRunLoopAddSource(loop, source, mode)
    _stop.clear()
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        while not _stop.is_set():
            remaining = 0.1 if deadline is None else min(0.1, deadline - time.monotonic())
            if remaining <= 0:
                break
            cf.CFRunLoopRunInMode(mode, remaining, True)
            while pending:
                if on_press(pending.pop(0)):
                    return
    finally:
        cf.CFRunLoopRemoveSource(loop, source, mode)
        cf.CFMachPortInvalidate(port)
        cf.CFRelease(source)
        cf.CFRelease(port)


def run(*, timeout: Optional[float] = None) -> None:
    """
    Listen for the registered shortcuts and call their callbacks, until :func:`stop` or ``timeout`` seconds.

    Callbacks run on this thread, one at a time; an exception in one stops
    :func:`run` and propagates. Ctrl-C stops it too.
    """

    def call(combination: Tuple[int, int]) -> bool:
        with _lock:
            hotkey = _registered.get(combination)
        if hotkey is not None:
            hotkey.callback()
        return False

    _listen(call, timeout)


def wait(keys: str, *, timeout: Optional[float] = None) -> bool:
    """
    Wait until ``keys`` is pressed, in any app; return ``False`` if ``timeout`` seconds pass first.

    Handy to start or pause a script from anywhere::

        print("Press Ctrl-Option-S to start")
        macos.hotkeys.wait("ctrl+option+s")
    """
    combination = _combination(keys)
    temporary = combination not in _registered
    if temporary:
        with _lock:
            _registered[combination] = Hotkey(keys, combination[0], combination[1], lambda: None)
    pressed: List[bool] = []

    def check(hit: Tuple[int, int]) -> bool:
        if hit == combination:
            pressed.append(True)
            return True
        with _lock:
            hotkey = _registered.get(hit)
        if hotkey is not None:  # another shortcut: still serve it
            hotkey.callback()
        return False

    try:
        _listen(check, timeout)
    finally:
        if temporary:
            with _lock:
                _registered.pop(combination, None)
    return bool(pressed)
