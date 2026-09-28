# -*- coding: utf-8 -*-

"""
Read the pointer position, move it, click, drag and scroll.

::

    macos.mouse.position()               # (512.0, 384.0)
    macos.mouse.move(100, 200)
    macos.mouse.click()                  # where the pointer is
    macos.mouse.click(300, 400, button="right")
    macos.mouse.scroll(5)                # 5 lines down

    with macos.keyboard.hold("shift"):   # Shift-click
        macos.mouse.click(300, 400)

Positions are in points from the top-left corner of the main display, like
:func:`macos.screenshot`'s ``region`` and :class:`macos.screen.Display`.

Reading the position needs no permission. Moving, clicking and scrolling need
the *Accessibility* permission for the app running Python (your terminal or
IDE); without it macOS silently drops the events, so these functions raise
:class:`~macos.errors.PermissionDeniedError` instead.
"""

import time
from typing import Optional, Tuple

from . import _events
from ._objc import CGPoint
from .errors import MacOSError

__all__ = ["position", "move", "click", "drag", "scroll", "has_permission", "request_permission"]

has_permission = _events.has_permission
request_permission = _events.request_permission

# CGEventType values and CGMouseButton numbers, per button.
_BUTTONS = {
    #          down, up, dragged, button
    "left": (1, 2, 6, 0),
    "right": (3, 4, 7, 1),
    "middle": (25, 26, 27, 2),
}
_MOVED = 5  # kCGEventMouseMoved
_CLICK_STATE = 1  # kCGMouseEventClickState: 2 for the second click of a double-click
_LINES = 1  # kCGScrollEventUnitLine


def position() -> Tuple[float, float]:
    """Where the pointer is, as ``(x, y)`` in points from the top-left corner of the main display."""
    cg = _events.graphics()
    event = cg.CGEventCreate(None)
    if not event:
        raise MacOSError("could not read the pointer position")
    try:
        point = cg.CGEventGetLocation(event)
    finally:
        cg.CFRelease(event)
    return (round(point.x, 1), round(point.y, 1))


def _button(button: str) -> Tuple[int, int, int, int]:
    if button not in _BUTTONS:
        raise ValueError("button must be 'left', 'right' or 'middle', not {!r}".format(button))
    return _BUTTONS[button]


def _mouse_event(kind: int, x: float, y: float, button: int, clicks: int = 0) -> int:
    cg = _events.graphics()
    event = cg.CGEventCreateMouseEvent(None, kind, CGPoint(x, y), button)
    if not event:
        raise MacOSError("could not create a mouse event")
    if clicks:
        cg.CGEventSetIntegerValueField(event, _CLICK_STATE, clicks)
    if _events.HELD:  # inside macos.keyboard.hold()
        cg.CGEventSetFlags(event, _events.held_flags())
    return event


def _glide(kind: int, x: float, y: float, button: int, duration: float) -> None:
    """Move to ``(x, y)`` in steps over ``duration`` seconds (or at once), posting ``kind`` events."""
    start_x, start_y = position()
    steps = max(1, int(duration * 60))  # about 60 moves a second, like a real mouse
    for step in range(1, steps + 1):
        fraction = step / steps
        _events.post(_mouse_event(kind, start_x + (x - start_x) * fraction, start_y + (y - start_y) * fraction, button))
        if steps > 1:
            time.sleep(duration / steps)


def move(x: float, y: float, *, duration: float = 0.0) -> None:
    """
    Move the pointer to ``(x, y)``, at once or gliding over ``duration`` seconds.

    Apps see it as a real mouse movement (hover effects, tooltips). Needs the
    Accessibility permission.
    """
    if duration < 0:
        raise ValueError("duration must not be negative, not {}".format(duration))
    _events.require_permission()
    _glide(_MOVED, x, y, 0, duration)


def click(x: Optional[float] = None, y: Optional[float] = None, *, button: str = "left", count: int = 1) -> None:
    """
    Click at ``(x, y)``, or where the pointer is.

    ``button`` is ``"left"``, ``"right"`` or ``"middle"``; ``count=2`` is a
    double-click. Needs the Accessibility permission.
    """
    down, up, _, number = _button(button)
    if count < 1:
        raise ValueError("count must be at least 1, not {}".format(count))
    if (x is None) != (y is None):
        raise ValueError("pass both x and y, or neither")
    _events.require_permission()
    if x is not None and y is not None:
        _glide(_MOVED, x, y, 0, 0.0)
    else:
        x, y = position()
    for clicks in range(1, count + 1):
        _events.post(_mouse_event(down, x, y, number, clicks))
        _events.post(_mouse_event(up, x, y, number, clicks))


def drag(x: float, y: float, *, button: str = "left", duration: float = 0.3) -> None:
    """
    Press ``button`` where the pointer is, move to ``(x, y)`` over ``duration`` seconds, and release it.

    Moves windows, selects text, drops files... Use :func:`move` first to
    choose where the drag starts. Needs the Accessibility permission.
    """
    down, up, dragged, number = _button(button)
    if duration < 0:
        raise ValueError("duration must not be negative, not {}".format(duration))
    _events.require_permission()
    start_x, start_y = position()
    _events.post(_mouse_event(down, start_x, start_y, number, 1))
    try:
        _glide(dragged, x, y, number, duration)
    finally:
        # Always let go, or the button stays pressed for the whole system.
        _events.post(_mouse_event(up, x, y, number, 1))


def scroll(lines: int, *, horizontal: bool = False) -> None:
    """
    Scroll by ``lines``: positive scrolls down (towards the end), negative up.

    With ``horizontal=True``, positive scrolls right and negative left. It
    scrolls what is under the pointer. Needs the Accessibility permission.
    """
    if not lines:
        return
    _events.require_permission()
    # A wheel turned "up" is positive for Core Graphics: flip the sign.
    vertical, sideways = (0, -lines) if horizontal else (-lines, 0)
    event = _events.graphics().CGEventCreateScrollWheelEvent2(None, _LINES, 2, vertical, sideways, 0)
    if not event:
        raise MacOSError("could not create a scroll event")
    _events.post(event)
