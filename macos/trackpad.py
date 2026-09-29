# -*- coding: utf-8 -*-

"""
Configure the trackpad: tap to click, the scroll direction and the pointer speed.

::

    macos.trackpad.set_tap_to_click(True)
    macos.trackpad.set_natural_scrolling(False)
    macos.trackpad.set_tracking_speed(0.7)

No permission is needed. Most settings apply at once, as in System
Settings; the pointer speed waits for the next login.
"""

from . import defaults
from ._system import apply_input_settings

__all__ = [
    "tap_to_click",
    "set_tap_to_click",
    "natural_scrolling",
    "set_natural_scrolling",
    "tracking_speed",
    "set_tracking_speed",
]

# The built-in trackpad and Bluetooth ones (Magic Trackpad) keep their own copy.
_TRACKPADS = ("com.apple.AppleMultitouchTrackpad", "com.apple.driver.AppleBluetoothMultitouch.trackpad")
_SPEED_MAX = 3.0  # the slider's range in System Settings goes up to 3


def tap_to_click() -> bool:
    """Whether a tap on the trackpad clicks, without pressing it."""
    return bool(defaults.read(_TRACKPADS[0], "Clicking", default=False))


def set_tap_to_click(on: bool = True) -> None:
    """Click with a tap on the trackpad, or only by pressing it (``False``)."""
    for domain in _TRACKPADS:
        defaults.write(domain, "Clicking", bool(on))
    defaults.write(defaults.GLOBAL, "com.apple.mouse.tapBehavior", 1 if on else 0)
    apply_input_settings()


def natural_scrolling() -> bool:
    """Whether content follows the fingers ("natural" scrolling, the default), for the trackpad and mice."""
    return bool(defaults.read(defaults.GLOBAL, "com.apple.swipescrolldirection", default=True))


def set_natural_scrolling(on: bool = True) -> None:
    """Scroll the "natural" way, or the classic way (``False``), for the trackpad and mice alike."""
    defaults.write(defaults.GLOBAL, "com.apple.swipescrolldirection", bool(on))
    apply_input_settings()


def tracking_speed() -> float:
    """The pointer speed with the trackpad, from 0.0 (slowest) to 1.0 (fastest)."""
    return round(float(defaults.read(defaults.GLOBAL, "com.apple.trackpad.scaling", default=1.0)) / _SPEED_MAX, 3)


def set_tracking_speed(speed: float) -> None:
    """
    Set the pointer speed with the trackpad, from 0.0 to 1.0, like the slider in System Settings.

    Takes effect at the next login.
    """
    if not 0.0 <= speed <= 1.0:
        raise ValueError("speed must be from 0.0 to 1.0, not {}".format(speed))
    defaults.write(defaults.GLOBAL, "com.apple.trackpad.scaling", round(speed * _SPEED_MAX, 3))
    apply_input_settings()
