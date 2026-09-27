# -*- coding: utf-8 -*-

"""
Query the system appearance (Light / Dark mode).

::

    if macos.appearance.is_dark():
        theme = "dark"

The value is read fresh from the preferences daemon on every call, so it
follows the user switching modes (or *Auto* switching at sunset) while your
program runs.
"""

from typing import Optional

from . import _cf

__all__ = ["is_dark", "mode", "is_auto"]


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


def is_auto() -> bool:
    """Whether the appearance is set to *Auto* (switches between Light and Dark by time of day)."""
    with _cf.owned(_read("AppleInterfaceStyleSwitchesAutomatically")) as value:
        return _cf.to_bool(value)
