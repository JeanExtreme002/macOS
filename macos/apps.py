# -*- coding: utf-8 -*-

"""
List, open, activate and quit applications.

::

    for app in macos.apps.running():
        print(app.name, app.bundle_id, app.pid)

    safari = macos.apps.open("Safari")
    macos.apps.frontmost()                  # App(name='Safari', ...)
    safari.quit()

Running applications come from ``NSWorkspace`` (the same list the Dock and the
Force Quit window use), queried natively through the Objective-C runtime.
"""

import ctypes
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from . import _cf, _objc
from ._objc import BOOL, NSInteger, NSUInteger
from ._system import framework, run
from .errors import AppNotFoundError, CommandError

__all__ = ["App", "running", "frontmost", "get", "open"]

# NSApplicationActivationPolicy
_POLICY_REGULAR = 0

# NSApplicationActivateAllWindows
_ACTIVATE_ALL_WINDOWS = 1 << 0


@lru_cache(maxsize=None)
def _workspace() -> int:
    framework("AppKit")
    return _objc.send(_objc.cls("NSWorkspace"), "sharedWorkspace")


def _refresh() -> None:
    """
    Let ``NSWorkspace`` process pending launch/quit notifications.

    Its application list is updated by notifications delivered on the run
    loop, which a script never spins, so without this a long-running process
    would keep seeing the list from its first call.
    """
    cf = _cf.lib()
    cf.CFRunLoopRunInMode.argtypes = (ctypes.c_void_p, ctypes.c_double, ctypes.c_bool)
    cf.CFRunLoopRunInMode.restype = ctypes.c_int32
    cf.CFRunLoopRunInMode(_cf.constant(cf, "kCFRunLoopDefaultMode"), 0.0, True)


@dataclass(frozen=True)
class App:
    """A running application."""

    name: Optional[str]
    bundle_id: Optional[str]
    pid: int
    path: Optional[str]

    def _handle(self) -> int:
        handle = _objc.send(
            _objc.cls("NSRunningApplication"),
            "runningApplicationWithProcessIdentifier:",
            self.pid,
            argtypes=(ctypes.c_int,),
        )
        if not handle:
            raise AppNotFoundError("{} (pid {}) is no longer running".format(self.name, self.pid))
        return handle

    @property
    def is_running(self) -> bool:
        with _objc.autorelease_pool():
            handle = _objc.send(
                _objc.cls("NSRunningApplication"),
                "runningApplicationWithProcessIdentifier:",
                self.pid,
                argtypes=(ctypes.c_int,),
            )
            return bool(handle) and not _objc.send(handle, "isTerminated", restype=BOOL)

    @property
    def is_active(self) -> bool:
        """Whether this is the frontmost application."""
        with _objc.autorelease_pool():
            return bool(_objc.send(self._handle(), "isActive", restype=BOOL))

    @property
    def is_hidden(self) -> bool:
        with _objc.autorelease_pool():
            return bool(_objc.send(self._handle(), "isHidden", restype=BOOL))

    def activate(self) -> bool:
        """Bring the application to the front. Return ``False`` if macOS refused."""
        with _objc.autorelease_pool():
            return bool(
                _objc.send(
                    self._handle(), "activateWithOptions:", _ACTIVATE_ALL_WINDOWS, argtypes=(NSUInteger,), restype=BOOL
                )
            )

    def hide(self) -> bool:
        with _objc.autorelease_pool():
            return bool(_objc.send(self._handle(), "hide", restype=BOOL))

    def unhide(self) -> bool:
        with _objc.autorelease_pool():
            return bool(_objc.send(self._handle(), "unhide", restype=BOOL))

    def quit(self, *, force: bool = False, timeout: Optional[float] = None) -> bool:
        """
        Ask the application to quit, like choosing *Quit* from its menu.

        The app may show a "save changes?" dialog or refuse. ``force=True``
        kills it instead, like *Force Quit*, losing unsaved work. With a
        ``timeout`` (seconds), wait for it to exit and return whether it did;
        otherwise return whether the request was delivered.
        """
        with _objc.autorelease_pool():
            selector = "forceTerminate" if force else "terminate"
            delivered = bool(_objc.send(self._handle(), selector, restype=BOOL))

        if timeout is None or not delivered:
            return delivered

        deadline = time.monotonic() + timeout
        while self.is_running:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)
        return True


def _app(handle: int) -> App:
    url = _objc.send(handle, "bundleURL")
    return App(
        name=_objc.pystring(_objc.send(handle, "localizedName")),
        bundle_id=_objc.pystring(_objc.send(handle, "bundleIdentifier")),
        pid=_objc.send(handle, "processIdentifier", restype=ctypes.c_int),
        path=_objc.pystring(_objc.send(url, "path")) if url else None,
    )


def running(*, include_background: bool = False) -> List[App]:
    """
    Return the running applications.

    By default only regular apps (the ones with a Dock icon) are listed.
    ``include_background=True`` adds menu-bar extras, agents and helpers.
    """
    _refresh()
    with _objc.autorelease_pool():
        apps = []
        for handle in _objc.nsarray(_objc.send(_workspace(), "runningApplications")):
            if include_background or _objc.send(handle, "activationPolicy", restype=NSInteger) == _POLICY_REGULAR:
                apps.append(_app(handle))
        return apps


def frontmost() -> Optional[App]:
    """Return the application that currently has keyboard focus."""
    _refresh()
    with _objc.autorelease_pool():
        handle = _objc.send(_workspace(), "frontmostApplication")
        return _app(handle) if handle else None


def get(name: str) -> Optional[App]:
    """
    Find a running application by name, bundle identifier or path.

    Names are compared case-insensitively against both the displayed
    (localized) name and the ``.app`` file name, so ``"Calculator"`` also
    finds it on a system where it is shown as ``"Calculadora"``. Returns
    ``None`` if it isn't running.
    """
    wanted = name.casefold()
    for app in running(include_background=True):
        bundle_name = os.path.splitext(os.path.basename(app.path or ""))[0]
        if wanted in {part.casefold() for part in (app.name, app.bundle_id, app.path, bundle_name) if part}:
            return app
    return None


def open(name: str, *, background: bool = False, timeout: float = 10.0) -> App:
    """
    Launch an application (or activate it, if it's already running) and return it.

    ``name`` may be an app name (``"Safari"``), a bundle identifier
    (``"com.apple.Safari"``) or a path to an ``.app``. ``background=True``
    launches it without bringing it to the front.
    """
    if os.path.isdir(name):
        target = ["-a", os.path.abspath(name)]
    elif "." in name and "/" not in name and not name.endswith(".app"):
        target = ["-b", name]
    else:
        target = ["-a", name]

    try:
        run(["open", *(["-g"] if background else []), *target])
    except CommandError as error:
        raise AppNotFoundError("unable to find application {!r}".format(name)) from error

    deadline = time.monotonic() + timeout
    while True:
        app = get(os.path.abspath(name) if os.path.isdir(name) else name)
        if app is not None or time.monotonic() >= deadline:
            break
        time.sleep(0.05)

    if app is None:
        raise AppNotFoundError("{!r} was launched but did not show up within {}s".format(name, timeout))
    return app
