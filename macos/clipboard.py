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

import ctypes
import os
from typing import Optional, Union

from . import _objc
from ._objc import BOOL, NSInteger, NSUInteger
from ._system import framework
from .errors import MacOSError

__all__ = ["copy", "paste", "clear", "change_count", "copy_image", "paste_image", "has_image"]

_TYPE_STRING = "public.utf8-plain-text"  # NSPasteboardTypeString
_TYPE_PNG = "public.png"  # NSPasteboardTypePNG
_TYPE_TIFF = "public.tiff"  # NSPasteboardTypeTIFF
_BITMAP_PNG = 4  # NSBitmapImageFileTypePNG


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
        raise MacOSError("the pasteboard refused the text")


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


def copy_image(image: Union[bytes, str, "os.PathLike[str]"]) -> None:
    """
    Put an image on the clipboard, from a file path or the file's bytes.

    Any format macOS can open works (PNG, JPEG, HEIC, GIF, TIFF, PDF...).
    Other apps receive it the same way as an image copied in Preview.
    """
    data = bytes(image) if isinstance(image, (bytes, bytearray)) else open(os.fspath(image), "rb").read()
    framework("AppKit")  # defines NSImage
    with _objc.autorelease_pool():
        picture = _objc.send(_objc.cls("NSImage"), "alloc")
        picture = _objc.send(picture, "initWithData:", _objc.nsdata(data), argtypes=(_objc.id,))
        if not picture:
            raise ValueError("not an image format macOS can read")
        _objc.send(picture, "autorelease")

        objects = (ctypes.c_void_p * 1)(picture)
        array = _objc.send(
            _objc.cls("NSArray"), "arrayWithObjects:count:", objects, 1, argtypes=(ctypes.c_void_p, NSUInteger)
        )
        pasteboard = _pasteboard()
        _objc.send(pasteboard, "clearContents", restype=NSInteger)
        if not _objc.send(pasteboard, "writeObjects:", array, argtypes=(_objc.id,), restype=BOOL):
            raise MacOSError("the pasteboard refused the image")


def paste_image() -> Optional[bytes]:
    """
    Return the image on the clipboard as PNG bytes, or ``None`` if it holds no image.

    Save it with ``Path("pasted.png").write_bytes(macos.clipboard.paste_image())``.
    """
    with _objc.autorelease_pool():
        pasteboard = _pasteboard()
        png = _objc.send(pasteboard, "dataForType:", _objc.nsstring(_TYPE_PNG), argtypes=(_objc.id,))
        if png:
            return _objc.pybytes(png)

        # Screenshots and most apps put TIFF on the clipboard: convert it.
        tiff = _objc.send(pasteboard, "dataForType:", _objc.nsstring(_TYPE_TIFF), argtypes=(_objc.id,))
        if not tiff:
            return None
        rep = _objc.send(_objc.cls("NSBitmapImageRep"), "imageRepWithData:", tiff, argtypes=(_objc.id,))
        if not rep:
            return None
        png = _objc.send(
            rep,
            "representationUsingType:properties:",
            _BITMAP_PNG,
            _objc.send(_objc.cls("NSDictionary"), "dictionary"),
            argtypes=(NSUInteger, _objc.id),
        )
        return _objc.pybytes(png)


def has_image() -> bool:
    """Whether the clipboard holds an image, without converting it."""
    with _objc.autorelease_pool():
        objects = (ctypes.c_void_p * 2)(_objc.nsstring(_TYPE_PNG), _objc.nsstring(_TYPE_TIFF))
        types = _objc.send(
            _objc.cls("NSArray"), "arrayWithObjects:count:", objects, 2, argtypes=(ctypes.c_void_p, NSUInteger)
        )
        return bool(_objc.send(_pasteboard(), "availableTypeFromArray:", types, argtypes=(_objc.id,)))
