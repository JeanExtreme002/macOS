# -*- coding: utf-8 -*-

"""
Read and write the system clipboard (the general pasteboard).

::

    macos.clipboard.copy("hello")
    macos.clipboard.paste()      # 'hello'
    macos.clipboard.clear()

Uses ``NSPasteboard`` directly, so non-ASCII text round-trips correctly
regardless of the terminal's locale (``pbcopy``/``pbpaste`` mangle it unless
``LANG`` is a UTF-8 locale).
"""

from typing import Optional

from . import _objc
from ._objc import BOOL, NSInteger
from ._system import framework

__all__ = ["copy", "paste", "clear", "change_count"]

_TYPE_STRING = "public.utf8-plain-text"  # NSPasteboardTypeString


def _pasteboard() -> int:
    framework("AppKit")
    return _objc.send(_objc.cls("NSPasteboard"), "generalPasteboard")


def copy(text: str) -> None:
    """Replace the clipboard contents with ``text``."""
    with _objc.autorelease_pool():
        pasteboard = _pasteboard()
        _objc.send(pasteboard, "clearContents", restype=NSInteger)
        ok = _objc.send(
            pasteboard,
            "setString:forType:",
            _objc.nsstring(text),
            _objc.nsstring(_TYPE_STRING),
            argtypes=(_objc.id, _objc.id),
            restype=BOOL,
        )
    if not ok:
        raise RuntimeError("the pasteboard refused the text")


def paste() -> Optional[str]:
    """Return the text on the clipboard, or ``None`` if it holds no text (e.g. an image)."""
    with _objc.autorelease_pool():
        value = _objc.send(_pasteboard(), "stringForType:", _objc.nsstring(_TYPE_STRING), argtypes=(_objc.id,))
        return _objc.pystring(value)


def clear() -> None:
    """Empty the clipboard."""
    with _objc.autorelease_pool():
        _objc.send(_pasteboard(), "clearContents", restype=NSInteger)


def change_count() -> int:
    """
    A counter that increases every time any app changes the clipboard.

    Compare two readings to detect a change without reading the contents.
    """
    with _objc.autorelease_pool():
        return _objc.send(_pasteboard(), "changeCount", restype=NSInteger)
