# -*- coding: utf-8 -*-

"""
Internal helpers for :mod:`macos.keyboard` and :mod:`macos.mouse`: posting
Quartz events and the Accessibility permission they need.
"""

import ctypes
import time
from functools import lru_cache
from typing import List

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
