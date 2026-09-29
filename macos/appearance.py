# -*- coding: utf-8 -*-

"""
Read and switch the system appearance (Light / Dark mode), and read the accent color.

::

    if macos.appearance.is_dark():
        theme = "dark"
    macos.appearance.accent_color()      # '#007aff'
    macos.appearance.set_mode("dark")

The value is read fresh from the preferences daemon on every call, so it
follows the user switching modes (or *Auto* switching at sunset) while your
program runs.
"""

import ctypes
import time
from typing import Optional

from . import _cf, _objc
from ._system import framework, run as _run
from .errors import CommandError, PermissionDeniedError

__all__ = ["is_dark", "mode", "set_mode", "is_auto", "accent_color", "wait_for_change"]


def _read(key: str) -> Optional[int]:
    """Return an owned reference to a global-domain preference value (or ``None``)."""
    cf = _cf.lib()
    domain = _cf.constant(cf, "kCFPreferencesAnyApplication")
    cf.CFPreferencesAppSynchronize(domain)
    with _cf.owned(_cf.string(key)) as name:
        return cf.CFPreferencesCopyAppValue(name, domain)


def mode() -> str:
    """Return ``"dark"`` or ``"light"``."""
    with _cf.owned(_read("AppleInterfaceStyle")) as value:
        style = _cf.to_str(value)
    return "dark" if style == "Dark" else "light"


def is_dark() -> bool:
    """Whether Dark mode is currently in effect."""
    return mode() == "dark"


def set_mode(mode: str) -> None:
    """
    Switch the whole system to ``"dark"`` or ``"light"`` mode, like System Settings › Appearance.

    Goes through System Events, so the first time macOS asks to allow the app
    running Python (your terminal or IDE) to control it; if that's denied,
    :class:`~macos.errors.PermissionDeniedError` is raised.
    """
    if mode not in ("dark", "light"):
        raise ValueError("mode must be 'dark' or 'light', not {!r}".format(mode))
    script = 'tell application "System Events" to tell appearance preferences to set dark mode to {}'.format(
        "true" if mode == "dark" else "false"
    )
    try:
        _run(["osascript", "-e", script])
    except CommandError as error:
        if "-1743" in error.stderr:  # errAEEventNotPermitted
            raise PermissionDeniedError(
                "Automation permission is missing: allow the app running Python (your terminal or IDE) to control "
                "System Events in System Settings › Privacy & Security › Automation"
            ) from None
        raise


def is_auto() -> bool:
    """Whether the appearance is set to *Auto* (switches between Light and Dark by time of day)."""
    with _cf.owned(_read("AppleInterfaceStyleSwitchesAutomatically")) as value:
        return _cf.to_bool(value)


def accent_color() -> str:
    """
    Return the accent color chosen in System Settings › Appearance, as hex (``'#007aff'``).

    That's the color of buttons, checkboxes and selections. With *Multicolor*
    selected, it's the default blue. Handy to theme a web view, a plot or a
    terminal UI to match the Mac.
    """
    framework("AppKit")
    with _objc.autorelease_pool():
        color = _objc.send(_objc.cls("NSColor"), "controlAccentColor")
        srgb = _objc.send(_objc.cls("NSColorSpace"), "sRGBColorSpace")
        color = _objc.send(color, "colorUsingColorSpace:", srgb, argtypes=(_objc.id,))
        channels = [
            _objc.send(color, name, restype=ctypes.c_double) for name in ("redComponent", "greenComponent", "blueComponent")
        ]
    return "#" + "".join("{:02x}".format(round(min(max(value, 0.0), 1.0) * 255)) for value in channels)


def wait_for_change(*, timeout: Optional[float] = None, interval: float = 1.0) -> str:
    """
    Wait until the system switches between Light and Dark mode, and return the new mode.

    Useful to restyle a terminal UI or a plot as soon as the user (or *Auto*)
    switches. Raises :class:`TimeoutError` if nothing changes within
    ``timeout`` seconds. ``interval`` is how often to check, in seconds.
    """
    if interval <= 0:
        raise ValueError("interval must be positive, not {}".format(interval))
    start = mode()
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        current = mode()
        if current != start:
            return current
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("the appearance didn't change within {}s".format(timeout))
            time.sleep(min(interval, remaining))
        else:
            time.sleep(interval)
