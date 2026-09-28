# -*- coding: utf-8 -*-

"""
List the windows of running apps, and move, resize, focus, minimize and close them.

::

    for window in macos.windows.list("Safari"):
        print(window.title, window.frame)

    window = macos.windows.focused()           # the window in front
    window.move(0, 25)
    window.resize(1280, 800)
    window.minimize()

Uses the Accessibility API, like window managers such as Rectangle, so it
needs the *Accessibility* permission for the app running Python (your
terminal or IDE), the same one :mod:`macos.keyboard` and :mod:`macos.mouse`
need.
"""

import builtins
import ctypes
import time
from functools import lru_cache
from typing import Any, Optional, Tuple, Union

from . import _cf, _objc, apps
from ._objc import CGPoint, CGSize
from ._system import framework
from .errors import MacOSError, PermissionDeniedError

__all__ = ["Window", "list", "focused", "has_permission", "request_permission"]

_SUCCESS = 0
_API_DISABLED = -25211  # kAXErrorAPIDisabled: no Accessibility permission
_INVALID_ELEMENT = -25202  # kAXErrorInvalidUIElement: the window is gone
_CANNOT_COMPLETE = -25204  # kAXErrorCannotComplete: the app didn't answer, or quit
_POINT, _SIZE = 1, 2  # kAXValueCGPointType, kAXValueCGSizeType
_TIMEOUT = 2.0  # seconds to wait for an app that doesn't answer
_FULL_SCREEN_TIMEOUT = 10.0
_FULL_SCREEN_ANIMATION = 1.0


@lru_cache(maxsize=None)
def _accessibility() -> ctypes.CDLL:
    ax = framework("ApplicationServices")
    pointer = ctypes.c_void_p
    signatures = {
        "AXIsProcessTrusted": ((), ctypes.c_bool),
        "AXIsProcessTrustedWithOptions": ((pointer,), ctypes.c_bool),
        "AXUIElementCreateApplication": ((ctypes.c_int,), pointer),
        "AXUIElementCopyAttributeValue": ((pointer, pointer, ctypes.POINTER(pointer)), ctypes.c_int32),
        "AXUIElementSetAttributeValue": ((pointer, pointer, pointer), ctypes.c_int32),
        "AXUIElementPerformAction": ((pointer, pointer), ctypes.c_int32),
        "AXUIElementSetMessagingTimeout": ((pointer, ctypes.c_float), ctypes.c_int32),
        "AXValueCreate": ((ctypes.c_int, pointer), pointer),
        "AXValueGetValue": ((pointer, ctypes.c_int, pointer), ctypes.c_bool),
    }
    for name, (argtypes, restype) in signatures.items():
        function = getattr(ax, name)
        function.argtypes = argtypes
        function.restype = restype
    return ax


def has_permission() -> bool:
    """Whether this process may control other apps' windows, without prompting the user."""
    return bool(_accessibility().AXIsProcessTrusted())


def request_permission() -> bool:
    """
    Ask for the Accessibility permission, showing the system prompt; return whether it's granted.

    After the user allows the app running Python in System Settings ›
    Privacy & Security › Accessibility, that app must be restarted.
    """
    ax = _accessibility()
    key = ctypes.c_void_p.in_dll(ax, "kAXTrustedCheckOptionPrompt").value or 0
    options = _cf.dictionary({key: _cf.constant(_cf.lib(), "kCFBooleanTrue")})
    with _cf.owned(options):
        return bool(ax.AXIsProcessTrustedWithOptions(options))


def _check(status: int, what: str) -> None:
    if status == _SUCCESS:
        return
    if status == _API_DISABLED:
        raise PermissionDeniedError(
            "Accessibility permission is missing: allow the app running Python (your terminal or IDE) in "
            "System Settings › Privacy & Security › Accessibility, then restart it"
        )
    if status == _INVALID_ELEMENT:
        raise MacOSError("could not {}: the window is gone".format(what))
    if status == _CANNOT_COMPLETE:
        raise MacOSError("could not {}: its app didn't answer (it may be busy, or have quit)".format(what))
    raise MacOSError("could not {} (AXError {})".format(what, status))


def _copy(element: int, attribute: str) -> Tuple[int, Optional[int]]:
    """The status and the owned value of an attribute."""
    value = ctypes.c_void_p()
    with _cf.owned(_cf.string(attribute)) as name:
        status = _accessibility().AXUIElementCopyAttributeValue(element, name, ctypes.byref(value))
    return status, value.value if status == _SUCCESS else None


def _set(element: int, attribute: str, value: int, what: str) -> None:
    with _cf.owned(_cf.string(attribute)) as name:
        _check(_accessibility().AXUIElementSetAttributeValue(element, name, value), what)


def _app_element(pid: int) -> int:
    """An owned accessibility element for the app with ``pid``, which gives up on an app that hangs."""
    ax = _accessibility()
    element = ax.AXUIElementCreateApplication(pid)
    if not element:
        raise MacOSError("could not reach the app with pid {}".format(pid))
    ax.AXUIElementSetMessagingTimeout(element, _TIMEOUT)
    return int(element)


class Window:
    """
    A window of a running app.

    Its title, position and size are read fresh each time, so they follow the
    user moving it. Get windows with :func:`list` or :func:`focused`.
    """

    def __init__(self, element: int, app: str, pid: int) -> None:
        # ``element`` is an owned reference, released with the object.
        self._element = element
        self.app = app
        """The name of the app it belongs to, such as ``'Safari'``."""
        self.pid = pid
        """The app's process ID."""

    def __del__(self) -> None:
        element, self._element = getattr(self, "_element", 0), 0
        if element:
            _cf.release(element)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Window):
            return NotImplemented
        return bool(_cf.lib().CFEqual(self._element, other._element))

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        try:
            return "Window(app={!r}, title={!r}, frame={!r})".format(self.app, self.title, self.frame)
        except MacOSError:
            return "Window(app={!r}, closed)".format(self.app)

    def _read(self, attribute: str) -> Optional[int]:
        status, value = _copy(self._element, attribute)
        if status != _SUCCESS and status not in (-25212, -25205):  # no value, unsupported: treat as missing
            _check(status, "read the window's {}".format(attribute))
        return value

    def _geometry(self, attribute: str, kind: int, holder: Any) -> Any:
        value = self._read(attribute)
        if not value:
            raise MacOSError("the window has no {}".format(attribute))
        with _cf.owned(value):
            if not _accessibility().AXValueGetValue(value, kind, ctypes.byref(holder)):
                raise MacOSError("could not read the window's {}".format(attribute))
        return holder

    @property
    def title(self) -> str:
        """As shown in its title bar; ``''`` for untitled windows."""
        value = self._read("AXTitle")
        with _cf.owned(value):
            return _cf.to_str(value) or ""

    @property
    def position(self) -> Tuple[int, int]:
        """``(x, y)`` of its top-left corner, in points from the top-left of the main display."""
        point = self._geometry("AXPosition", _POINT, CGPoint())
        return (round(point.x), round(point.y))

    @property
    def size(self) -> Tuple[int, int]:
        """``(width, height)`` in points, title bar included."""
        size = self._geometry("AXSize", _SIZE, CGSize())
        return (round(size.width), round(size.height))

    @property
    def frame(self) -> Tuple[int, int, int, int]:
        """``(x, y, width, height)``, as :attr:`position` and :attr:`size`, like :func:`macos.screenshot`'s ``region``."""
        return self.position + self.size

    @property
    def minimized(self) -> bool:
        """Whether it's minimized into the Dock."""
        value = self._read("AXMinimized")
        with _cf.owned(value):
            return _cf.to_bool(value)

    @property
    def fullscreen(self) -> bool:
        """Whether it's in full screen, in a Space of its own."""
        value = self._read("AXFullScreen")
        with _cf.owned(value):
            return _cf.to_bool(value)

    def set_fullscreen(self, on: bool = True) -> None:
        """
        Enter full screen (or leave it with ``on=False``), like its green button.

        macOS animates the change into a Space of its own; this returns once
        it's done, after a second or two. Windows that can't go full screen
        raise :class:`~macos.errors.MacOSError`.
        """
        what = "{} full screen".format("enter" if on else "leave")
        try:
            self._set_flag("AXFullScreen", on, what)
        except MacOSError as error:
            if on and "AXError -25200" in str(error):  # kAXErrorFailure
                raise MacOSError("this window can't go full screen: its app doesn't allow it") from None
            raise
        deadline = time.monotonic() + _FULL_SCREEN_TIMEOUT
        while self.fullscreen != bool(on):
            if time.monotonic() > deadline:
                raise MacOSError("could not {} within {} seconds".format(what, _FULL_SCREEN_TIMEOUT))
            time.sleep(0.1)
        # The state changes as the animation starts, and macOS ignores a new
        # request until it ends: let it finish.
        time.sleep(_FULL_SCREEN_ANIMATION)

    def move(self, x: float, y: float) -> None:
        """Move its top-left corner to ``(x, y)``."""
        point = CGPoint(x, y)
        value = _accessibility().AXValueCreate(_POINT, ctypes.byref(point))
        with _cf.owned(value):
            _set(self._element, "AXPosition", value, "move the window")

    def resize(self, width: float, height: float) -> None:
        """
        Resize it to ``width`` x ``height`` points.

        Apps may refuse sizes below their minimum or above the screen, and
        keep the closest size they accept.
        """
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive, not {} x {}".format(width, height))
        size = CGSize(width, height)
        value = _accessibility().AXValueCreate(_SIZE, ctypes.byref(size))
        with _cf.owned(value):
            _set(self._element, "AXSize", value, "resize the window")

    def set_frame(self, x: float, y: float, width: float, height: float) -> None:
        """Move and resize it at once: ``window.set_frame(0, 25, 1280, 800)``."""
        self.move(x, y)
        self.resize(width, height)
        # A window moved near the edge of the screen may have refused a size
        # that didn't fit there yet: try again now that it's in place.
        self.move(x, y)

    def center(self) -> None:
        """
        Center it on the display it's on (the main one, if it's on none), keeping its size.

        A window taller than the display keeps its top edge on the display.
        """
        from . import screen

        x, y, width, height = self.frame
        middle_x, middle_y = x + width / 2, y + height / 2
        displays = screen.displays()
        if not displays:
            raise MacOSError("no display is connected")
        display = next(
            (
                candidate
                for candidate in displays
                if candidate.x <= middle_x < candidate.x + candidate.width
                and candidate.y <= middle_y < candidate.y + candidate.height
            ),
            displays[0],  # the main display comes first
        )
        left = display.x + (display.width - width) / 2
        top = max(display.y + (display.height - height) / 2, display.y)
        self.move(round(left), round(top))

    def _set_flag(self, attribute: str, on: bool, what: str) -> None:
        flag = _cf.constant(_cf.lib(), "kCFBooleanTrue" if on else "kCFBooleanFalse")
        _set(self._element, attribute, flag, what)

    def focus(self) -> None:
        """Bring it to the front, with its app, ready for keystrokes."""
        if self.minimized:
            self.restore()
        app = next((running for running in apps.running(include_background=True) if running.pid == self.pid), None)
        if app is not None:
            try:
                app.activate()
            except MacOSError:
                pass  # LaunchServices can't activate some apps (helper processes): Accessibility below still can
        # macOS may refuse an activation asked by another app: make the app
        # frontmost through Accessibility too, as window managers do.
        element = _app_element(self.pid)
        try:
            true = _cf.constant(_cf.lib(), "kCFBooleanTrue")
            _set(element, "AXFrontmost", true, "bring the app to the front")
        finally:
            _cf.release(element)
        with _cf.owned(_cf.string("AXRaise")) as action:
            _check(_accessibility().AXUIElementPerformAction(self._element, action), "raise the window")
        self._set_flag("AXMain", True, "focus the window")

    def minimize(self) -> None:
        """Minimize it into the Dock."""
        self._set_flag("AXMinimized", True, "minimize the window")

    def restore(self) -> None:
        """Bring it back from the Dock."""
        self._set_flag("AXMinimized", False, "restore the window")

    def close(self) -> None:
        """
        Close it, like its red button.

        The app may ask to save changes first, or keep running without windows.
        """
        button = self._read("AXCloseButton")
        if not button:
            raise MacOSError("the window has no close button")
        with _cf.owned(button), _cf.owned(_cf.string("AXPress")) as press:
            _check(_accessibility().AXUIElementPerformAction(button, press), "close the window")


_REGULAR, _ACCESSORY = 0, 1  # NSApplicationActivationPolicy: apps that can have windows


def _apps_with_windows() -> "builtins.list[apps.App]":
    """The regular apps and the accessory ones (menu bar apps), which can have windows too."""
    with _objc.autorelease_pool():
        return [
            apps._app(handle)
            for handle in apps._handles(True)
            if _objc.send(handle, "activationPolicy", restype=_objc.NSInteger) in (_REGULAR, _ACCESSORY)
        ]


def _windows_of(app: apps.App) -> "builtins.list[Window]":
    element = _app_element(app.pid)
    try:
        status, value = _copy(element, "AXWindows")
        if status == _API_DISABLED:
            _check(status, "list the windows")
        if not value:
            return []  # no windows, or an app that doesn't answer
        with _cf.owned(value):
            found = []
            for window in _cf.items(value):
                found.append(Window(_cf.retain(window), app.name or "", app.pid))
            return found
    finally:
        _cf.release(element)


def list(app: Union[str, apps.App, None] = None, *, title: Optional[str] = None) -> "builtins.list[Window]":
    """
    Return the windows of the running apps (menu bar apps included), or only of ``app``, front to back within each app.

    ``app`` is an :class:`~macos.apps.App` or an app's name (``"Safari"``).
    ``title`` keeps the windows whose title contains it, ignoring case.
    Minimized windows are included; check :attr:`Window.minimized`.
    """
    if not has_permission():
        _check(_API_DISABLED, "list the windows")
    if app is None:
        targets = _apps_with_windows()
    elif isinstance(app, apps.App):
        targets = [app]
    else:
        found = apps.get(app)
        targets = [found] if found is not None else []
    windows = [window for target in targets for window in _windows_of(target)]
    if title is not None:
        wanted = title.casefold()
        windows = [window for window in windows if wanted in window.title.casefold()]
    return windows


def focused() -> Optional[Window]:
    """Return the window in front (the one keystrokes go to), or ``None`` when the front app has none."""
    if not has_permission():
        _check(_API_DISABLED, "read the focused window")
    front = apps.frontmost()
    if front is None:
        return None
    element = _app_element(front.pid)
    try:
        status, value = _copy(element, "AXFocusedWindow")
        return Window(value, front.name or "", front.pid) if value else None
    finally:
        _cf.release(element)
