# -*- coding: utf-8 -*-

"""
Internal helpers for :mod:`macos.keyboard` and :mod:`macos.mouse`: posting
Quartz events and the Accessibility permission they need, and listening to
the user's input.
"""

import collections
import ctypes
import time
from functools import lru_cache
from typing import Any, Callable, Iterator, List, Optional

from ._objc import CGPoint
from ._system import framework
from .errors import PermissionDeniedError

HID_TAP = 0  # kCGHIDEventTap: as if the events came from the hardware
PAUSE = 0.005  # between events, so apps see them in order

# The modifier flags of the keys held down by macos.keyboard.hold(), one entry
# per key: every event posted meanwhile carries them, so a click becomes a
# Shift-click.
HELD: List[int] = []


def held_flags() -> int:
    flags = 0
    for flag in HELD:
        flags |= flag
    return flags


_TapCallback = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p)


@lru_cache(maxsize=None)
def graphics() -> ctypes.CDLL:
    cg = framework("CoreGraphics")
    pointer = ctypes.c_void_p
    signatures = {
        "CGPreflightPostEventAccess": ((), ctypes.c_bool),
        "CGRequestPostEventAccess": ((), ctypes.c_bool),
        "CGEventCreate": ((pointer,), pointer),
        "CGEventGetLocation": ((pointer,), CGPoint),
        "CGEventCreateKeyboardEvent": ((pointer, ctypes.c_uint16, ctypes.c_bool), pointer),
        "CGEventKeyboardSetUnicodeString": ((pointer, ctypes.c_ulong, ctypes.POINTER(ctypes.c_uint16)), None),
        "CGEventCreateMouseEvent": ((pointer, ctypes.c_uint32, CGPoint, ctypes.c_uint32), pointer),
        "CGEventCreateScrollWheelEvent2": (
            (pointer, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32),
            pointer,
        ),
        "CGEventSetFlags": ((pointer, ctypes.c_uint64), None),
        "CGEventSetIntegerValueField": ((pointer, ctypes.c_uint32, ctypes.c_int64), None),
        "CGEventPost": ((ctypes.c_uint32, pointer), None),
        "CGEventSourceFlagsState": ((ctypes.c_int32,), ctypes.c_uint64),
        "CGEventGetIntegerValueField": ((pointer, ctypes.c_uint32), ctypes.c_int64),
        "CGEventGetFlags": ((pointer,), ctypes.c_uint64),
        "CGEventKeyboardGetUnicodeString": (
            (pointer, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_uint16)),
            None,
        ),
        "CGEventTapCreate": (
            (ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint64, _TapCallback, pointer),
            pointer,
        ),
        "CGEventTapEnable": ((pointer, ctypes.c_bool), None),
        "CFRelease": ((pointer,), None),
    }
    for name, (argtypes, restype) in signatures.items():
        function = getattr(cg, name)
        function.argtypes = argtypes
        function.restype = restype
    return cg


def has_permission() -> bool:
    """Whether this process may send keystrokes and mouse events, without prompting the user."""
    return bool(graphics().CGPreflightPostEventAccess())


def request_permission() -> bool:
    """
    Ask for the Accessibility permission, which sending keystrokes and mouse events needs; return whether it's granted.

    macOS asks only once: after that, the user must allow the app running
    Python (your terminal or IDE) in System Settings › Privacy & Security ›
    Accessibility, and restart it.
    """
    return bool(graphics().CGRequestPostEventAccess())


def require_permission() -> None:
    # Without the permission macOS doesn't fail: it silently drops the events.
    if not has_permission():
        raise PermissionDeniedError(
            "Accessibility permission is missing: allow the app running Python (your terminal or IDE) in "
            "System Settings › Privacy & Security › Accessibility, then restart it"
        )


def post(event: int) -> None:
    """Post an owned event, then release it."""
    cg = graphics()
    try:
        cg.CGEventPost(HID_TAP, event)
    finally:
        cg.CFRelease(event)
    time.sleep(PAUSE)


_SESSION_TAP, _TAIL = 1, 1  # kCGSessionEventTap, kCGTailAppendEventTap
_LISTEN_ONLY = 1  # kCGEventTapOptionListenOnly: see the events without holding them up
_TAP_DISABLED = (0xFFFFFFFE, 0xFFFFFFFF)  # by timeout, by user input: turn the tap back on


def listen(kinds: List[int], convert: Callable[[int, int], Any], timeout: Optional[float], denied: str) -> Iterator[Any]:
    """
    Yield ``convert(kind, event)`` for each input event of ``kinds`` (CGEventType values), as it happens.

    A listen-only tap on this thread's run loop: the events go on to the apps
    unchanged. ``convert`` runs inside the tap, so it must be quick; returning
    ``None`` skips the event. Stops after ``timeout`` seconds, or when the
    caller stops iterating. ``denied`` is the error when macOS refuses the tap.
    """
    cg = graphics()
    run_loop = framework("CoreFoundation")
    pointer = ctypes.c_void_p
    run_loop.CFMachPortCreateRunLoopSource.argtypes = (pointer, pointer, ctypes.c_long)
    run_loop.CFMachPortCreateRunLoopSource.restype = pointer
    run_loop.CFMachPortInvalidate.argtypes = (pointer,)
    run_loop.CFRunLoopGetCurrent.restype = pointer
    run_loop.CFRunLoopAddSource.argtypes = (pointer, pointer, pointer)
    run_loop.CFRunLoopRemoveSource.argtypes = (pointer, pointer, pointer)
    run_loop.CFRunLoopRunInMode.argtypes = (pointer, ctypes.c_double, ctypes.c_bool)
    run_loop.CFRunLoopRunInMode.restype = ctypes.c_int32

    pending: "collections.deque[Any]" = collections.deque()
    port_holder: List[int] = []

    def tap(proxy: int, kind: int, event: int, refcon: int) -> int:
        if kind in _TAP_DISABLED:  # macOS switched the tap off (a slow consumer): switch it back on
            if port_holder:
                cg.CGEventTapEnable(port_holder[0], True)
            return event
        try:
            item = convert(kind, event)
        except Exception:  # an exception must not cross back into the window server
            item = None
        if item is not None:
            pending.append(item)
        return event

    callback = _TapCallback(tap)  # kept alive for as long as the tap runs
    mask = 0
    for kind in kinds:
        mask |= 1 << kind
    port = cg.CGEventTapCreate(_SESSION_TAP, _TAIL, _LISTEN_ONLY, mask, callback, None)
    if not port:
        raise PermissionDeniedError(denied)
    port_holder.append(port)
    source = run_loop.CFMachPortCreateRunLoopSource(None, port, 0)
    loop = run_loop.CFRunLoopGetCurrent()
    mode = ctypes.c_void_p.in_dll(run_loop, "kCFRunLoopDefaultMode")
    run_loop.CFRunLoopAddSource(loop, source, mode)
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        while True:
            while pending:
                yield pending.popleft()
            remaining = 0.1 if deadline is None else min(0.1, deadline - time.monotonic())
            if remaining <= 0:
                return
            run_loop.CFRunLoopRunInMode(mode, remaining, True)
    finally:
        run_loop.CFRunLoopRemoveSource(loop, source, mode)
        run_loop.CFMachPortInvalidate(port)
        cg.CFRelease(source)
        cg.CFRelease(port)
