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
from typing import Iterator, List, Optional

from . import _objc
from ._objc import BOOL, NSInteger, NSUInteger
from ._system import framework, run
from .errors import AppNotFoundError, CommandError

__all__ = ["App", "running", "frontmost", "get", "open"]

# NSApplicationActivationPolicy
_POLICY_REGULAR = 0

# NSApplicationActivateAllWindows
_ACTIVATE_ALL_WINDOWS = 1 << 0


@lru_cache(maxsize=None)
def _running_application_class() -> int:
    framework("AppKit")
    return _objc.cls("NSRunningApplication")


@lru_cache(maxsize=None)
def _workspace() -> int:
    framework("AppKit")
    return _objc.send(_objc.cls("NSWorkspace"), "sharedWorkspace")


@lru_cache(maxsize=None)
def _libproc() -> ctypes.CDLL:
    lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    lib.proc_listallpids.argtypes = (ctypes.c_void_p, ctypes.c_int)
    lib.proc_listallpids.restype = ctypes.c_int
    return lib


def _pids() -> List[int]:
    lib = _libproc()
    # The process count can grow between the sizing call and the real one, so
    # leave headroom and retry if the buffer came back full.
    capacity = lib.proc_listallpids(None, 0) + 64
    while True:
        buffer = (ctypes.c_int * capacity)()
        count = lib.proc_listallpids(buffer, ctypes.sizeof(buffer))
        if count < capacity:
            return [pid for pid in buffer[: max(count, 0)] if pid > 0]
        capacity *= 2


def _handle(pid: int) -> Optional[int]:
    """The ``NSRunningApplication`` for ``pid``, or ``None`` if it isn't an app."""
    return _objc.send(
        _running_application_class(), "runningApplicationWithProcessIdentifier:", pid, argtypes=(ctypes.c_int,)
    )


def _handles(include_background: bool) -> Iterator[int]:
    """
    Yield an ``NSRunningApplication`` for every running app.

    ``NSWorkspace.runningApplications`` would be the obvious source, but it is
    only refreshed by notifications on the *main* run loop, which a script
    never spins: from a worker thread it keeps returning a stale list. Asking
    LaunchServices about each process is always current, and costs a few
    milliseconds.
    """
    for pid in _pids():
        handle = _handle(pid)
        if handle and (include_background or _objc.send(handle, "activationPolicy", restype=NSInteger) == _POLICY_REGULAR):
            yield handle


@dataclass(frozen=True)
class App:
    """A running application."""

    name: Optional[str]
    bundle_id: Optional[str]
    pid: int
    path: Optional[str]

    def _handle(self) -> int:
        handle = _handle(self.pid)
        if not handle:
            raise AppNotFoundError("{} (pid {}) is no longer running".format(self.name, self.pid))
        return handle

    @property
    def is_running(self) -> bool:
        with _objc.autorelease_pool():
            handle = _handle(self.pid)
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
    with _objc.autorelease_pool():
        return [_app(handle) for handle in _handles(include_background)]


def frontmost() -> Optional[App]:
    """Return the application that currently has keyboard focus."""
    with _objc.autorelease_pool():
        for handle in _handles(include_background=True):
            if _objc.send(handle, "isActive", restype=BOOL):
                return _app(handle)
    return None


def _is_path(name: str) -> bool:
    return "/" in name or name.startswith("~")


def get(name: str) -> Optional[App]:
    """
    Find a running application by name, bundle identifier or path.

    Names are compared case-insensitively against the displayed (localized)
    name and the ``.app`` file name, with or without the extension, so
    ``"Calculator"`` also finds it on a system where it is shown as
    ``"Calculadora"``. Paths may be symlinks. Returns ``None`` if it isn't
    running.
    """
    if _is_path(name):
        wanted_path = os.path.realpath(os.path.expanduser(name))
        for app in running(include_background=True):
            if app.path and os.path.realpath(app.path) == wanted_path:
                return app
        return None

    wanted = name.casefold()
    for app in running(include_background=True):
        file_name = os.path.basename(app.path or "")
        candidates = (app.name, app.bundle_id, file_name, os.path.splitext(file_name)[0])
        if wanted in {part.casefold() for part in candidates if part}:
            return app
    return None


def _locate(name: str) -> str:
    """Resolve an app name, bundle identifier or path to the real path of its bundle."""
    if _is_path(name) or os.path.isdir(name):
        expanded = os.path.expanduser(name)
        if not os.path.isdir(expanded):
            raise AppNotFoundError("no application at {!r}".format(name))
        return os.path.realpath(expanded)

    with _objc.autorelease_pool():
        url = _objc.send(
            _workspace(), "URLForApplicationWithBundleIdentifier:", _objc.nsstring(name), argtypes=(_objc.id,)
        )
        path = _objc.pystring(_objc.send(url, "path")) if url else None
        if path is None:
            # Looks the name up the way `open -a` does: "Safari", "Safari.app"
            # and names with dots in them, like "zoom.us", all work.
            path = _objc.pystring(
                _objc.send(_workspace(), "fullPathForApplication:", _objc.nsstring(name), argtypes=(_objc.id,))
            )
    if path is None:
        raise AppNotFoundError("unable to find application {!r}".format(name))
    return os.path.realpath(path)


def _bundle_id(path: str) -> Optional[str]:
    with _objc.autorelease_pool():
        bundle = _objc.send(_objc.cls("NSBundle"), "bundleWithPath:", _objc.nsstring(path), argtypes=(_objc.id,))
        return _objc.pystring(_objc.send(bundle, "bundleIdentifier")) if bundle else None


def _find_launched(path: str, bundle_id: Optional[str]) -> Optional[App]:
    with _objc.autorelease_pool():
        if bundle_id is not None:
            # Only asks about this one bundle id, instead of listing every
            # process on each poll.
            launched = _objc.send(
                _running_application_class(),
                "runningApplicationsWithBundleIdentifier:",
                _objc.nsstring(bundle_id),
                argtypes=(_objc.id,),
            )
            for handle in _objc.nsarray(launched):
                if not _objc.send(handle, "isTerminated", restype=BOOL):
                    return _app(handle)
            return None
    return get(path)


def open(name: str, *, background: bool = False, timeout: float = 10.0) -> App:
    """
    Launch an application (or activate it, if it's already running) and return it.

    ``name`` may be an app name (``"Safari"``), a bundle identifier
    (``"com.apple.Safari"``) or a path to an ``.app``. ``background=True``
    launches it without bringing it to the front.
    """
    path = _locate(name)
    bundle_id = _bundle_id(path)

    try:
        run(["open", *(["-g"] if background else []), "-a", path])
    except CommandError as error:
        raise AppNotFoundError("unable to launch {!r}: {}".format(name, error.stderr or error)) from error

    deadline = time.monotonic() + timeout
    while True:
        app = _find_launched(path, bundle_id)
        if app is not None:
            return app
        if time.monotonic() >= deadline:
            raise AppNotFoundError("{!r} was launched but did not show up within {}s".format(name, timeout))
        time.sleep(0.1)
