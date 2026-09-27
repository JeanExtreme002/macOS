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

import os
import time
from pathlib import Path
from typing import Iterable, List, Optional, Union

from . import _objc
from ._objc import BOOL, NSInteger
from ._system import framework
from .errors import MacOSError

__all__ = [
    "copy",
    "paste",
    "clear",
    "change_count",
    "wait_for_change",
    "copy_image",
    "paste_image",
    "has_image",
    "copy_files",
    "paste_files",
]

_TYPE_STRING = "public.utf8-plain-text"  # NSPasteboardTypeString
_TYPE_PNG = "public.png"  # NSPasteboardTypePNG
_TYPE_TIFF = "public.tiff"  # NSPasteboardTypeTIFF


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


def wait_for_change(*, timeout: Optional[float] = None, interval: float = 0.2) -> Optional[str]:
    """
    Wait until something new is copied, and return it as text.

    Returns ``None`` if the new content isn't text (an image, files...).
    Raises :class:`TimeoutError` if nothing changes within ``timeout`` seconds.
    ``interval`` is how often to check, in seconds.
    """
    if interval <= 0:
        raise ValueError("interval must be positive, not {}".format(interval))
    start = change_count()
    deadline = None if timeout is None else time.monotonic() + timeout
    while change_count() == start:
        if deadline is None:
            time.sleep(interval)
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("the clipboard didn't change within {}s".format(timeout))
        # Never sleep past the deadline, even with a long interval.
        time.sleep(min(interval, remaining))
    return paste()


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

        array = _objc.nsarray_of([picture])
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
        return _objc.png(rep) if rep else None


def has_image() -> bool:
    """Whether the clipboard holds an image, without converting it."""
    with _objc.autorelease_pool():
        types = _objc.nsarray_of([_objc.nsstring(_TYPE_PNG), _objc.nsstring(_TYPE_TIFF)])
        return bool(_objc.send(_pasteboard(), "availableTypeFromArray:", types, argtypes=(_objc.id,)))


def copy_files(paths: Iterable[Union[str, "os.PathLike[str]"]]) -> None:
    """
    Put files on the clipboard, as if they were copied in Finder.

    Pasting in Finder then copies the files there, and apps like Mail or Slack
    attach them.
    """
    resolved = [Path(path).expanduser().absolute() for path in paths]
    if not resolved:
        raise ValueError("copy_files() needs at least one path")
    for path in resolved:
        if not os.path.lexists(path):
            raise FileNotFoundError(str(path))

    with _objc.autorelease_pool():
        urls = [_objc.file_url(path) for path in resolved]
        pasteboard = _pasteboard()
        _objc.send(pasteboard, "clearContents", restype=NSInteger)
        if not _objc.send(pasteboard, "writeObjects:", _objc.nsarray_of(urls), argtypes=(_objc.id,), restype=BOOL):
            raise MacOSError("the pasteboard refused the files")


def paste_files() -> List[Path]:
    """Return the files on the clipboard (e.g. copied in Finder), or ``[]`` if there are none."""
    with _objc.autorelease_pool():
        pasteboard = _pasteboard()
        only_files = _objc.send(
            _objc.cls("NSDictionary"),
            "dictionaryWithObject:forKey:",
            _objc.send(_objc.cls("NSNumber"), "numberWithBool:", True, argtypes=(BOOL,)),
            _objc.nsstring("NSPasteboardURLReadingFileURLsOnlyKey"),
            argtypes=(_objc.id, _objc.id),
        )
        urls = _objc.send(
            pasteboard,
            "readObjectsForClasses:options:",
            _objc.nsarray_of([_objc.cls("NSURL")]),
            only_files,
            argtypes=(_objc.id, _objc.id),
        )
        paths = (_objc.pystring(_objc.send(url, "path")) for url in _objc.nsarray(urls))
        return [Path(path) for path in paths if path]
