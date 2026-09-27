# -*- coding: utf-8 -*-

"""
Read, merge and split PDFs.

::

    macos.pdf.page_count("report.pdf")              # 12
    macos.pdf.text("report.pdf")                    # all the text
    macos.pdf.text("report.pdf", pages=[1])         # just the first page
    macos.pdf.merge(["a.pdf", "b.pdf"], "both.pdf")
    macos.pdf.extract("report.pdf", [1, 3], "summary.pdf")

Uses PDFKit, the framework behind Preview. Page numbers start at 1, like in
Preview.
"""

import ctypes
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence, Union

from . import _objc
from ._objc import BOOL, NSUInteger
from ._system import framework
from .errors import MacOSError, PermissionDeniedError

__all__ = ["page_count", "text", "merge", "extract", "render"]

PathLike = Union[str, "os.PathLike[str]"]

_MAX_RENDER = 4096
_MEDIA_BOX = 0  # kPDFDisplayBoxMediaBox


@contextmanager
def _open(path: PathLike, password: Optional[str] = None) -> Iterator[int]:
    """Yield a ``PDFDocument`` for ``path``, inside an autorelease pool."""
    resolved = Path(path).expanduser().absolute()
    if not resolved.exists():
        raise FileNotFoundError(str(resolved))
    framework("PDFKit")
    with _objc.autorelease_pool():
        document = _objc.send(_objc.cls("PDFDocument"), "alloc")
        document = _objc.send(document, "initWithURL:", _objc.file_url(resolved), argtypes=(_objc.id,))
        if not document:
            raise ValueError("{} is not a PDF".format(resolved))
        _objc.send(document, "autorelease")
        if _objc.send(document, "isLocked", restype=BOOL):
            unlocked = password is not None and _objc.send(
                document, "unlockWithPassword:", _objc.nsstring(password), argtypes=(_objc.id,), restype=BOOL
            )
            if not unlocked:
                raise PermissionDeniedError(
                    "{} is encrypted: {}".format(resolved, "wrong password" if password else "pass its password")
                )
        yield document


def _count(document: int) -> int:
    return int(_objc.send(document, "pageCount", restype=NSUInteger))


def _page(document: int, number: int) -> int:
    count = _count(document)
    if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= count:
        raise ValueError("page {!r} is out of range: the PDF has {} page(s), numbered from 1".format(number, count))
    return _objc.send(document, "pageAtIndex:", number - 1, argtypes=(NSUInteger,))


def page_count(path: PathLike, *, password: Optional[str] = None) -> int:
    """Return the number of pages."""
    with _open(path, password) as document:
        return _count(document)


def text(path: PathLike, pages: Optional[Iterable[int]] = None, *, password: Optional[str] = None) -> str:
    """
    Return the text of a PDF, or only of ``pages`` (numbered from 1), one page after another.

    Scanned pages have no text layer and give ``""``: read those with
    :func:`render` and :func:`macos.vision.text`.
    """
    with _open(path, password) as document:
        numbers = list(pages) if pages is not None else range(1, _count(document) + 1)
        parts = [_objc.pystring(_objc.send(_page(document, number), "string")) or "" for number in numbers]
        return "\n".join(part.rstrip("\n") for part in parts)


def _save(document: int, output: PathLike) -> Path:
    target = Path(output).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not _objc.send(document, "writeToFile:", _objc.nsstring(str(target)), argtypes=(_objc.id,), restype=BOOL):
        raise MacOSError("could not write {}".format(target))
    return target


def _new_document() -> int:
    return _objc.new("PDFDocument")


def _append(target: int, page: int) -> None:
    # Copy the page: inserting the original would move it out of its document.
    copy = _objc.send(_objc.send(page, "copy"), "autorelease")
    _objc.send(target, "insertPage:atIndex:", copy, _count(target), argtypes=(_objc.id, NSUInteger), restype=None)


def merge(inputs: Sequence[PathLike], output: PathLike, *, password: Optional[str] = None) -> Path:
    """
    Join PDFs, one after another, into ``output``, and return its path.

    ``password`` unlocks any encrypted input (they must share it); the
    merged PDF itself is not encrypted.
    """
    if not inputs:
        raise ValueError("merge() needs at least one PDF")
    framework("PDFKit")
    with _objc.autorelease_pool():
        merged = _new_document()
        for path in inputs:
            with _open(path, password) as document:
                for number in range(1, _count(document) + 1):
                    _append(merged, _page(document, number))
        return _save(merged, output)


def extract(path: PathLike, pages: Iterable[int], output: PathLike, *, password: Optional[str] = None) -> Path:
    """
    Save the chosen ``pages`` (numbered from 1, in the order given) as a new PDF, and return its path.

    Use it to split a PDF (``extract(path, [1], "first.pdf")``) or reorder its pages.
    """
    numbers = list(pages)
    if not numbers:
        raise ValueError("extract() needs at least one page")
    with _open(path, password) as document:
        result = _new_document()
        for number in numbers:
            _append(result, _page(document, number))
        return _save(result, output)


def render(path: PathLike, page: int = 1, *, size: int = 1024, password: Optional[str] = None) -> bytes:
    """
    Draw a page as a PNG image and return its bytes. ``size`` is the longest side, in pixels (up to 4096).

    Combine it with :func:`macos.vision.text` to read scanned PDFs::

        macos.vision.text(macos.pdf.render("scan.pdf", page=1, size=2048))
    """
    if not 0 < size <= _MAX_RENDER:
        raise ValueError("size must be from 1 to {}, not {}".format(_MAX_RENDER, size))
    framework("AppKit")
    with _open(path, password) as document:
        target = _page(document, page)
        bounds = _objc.send(target, "boundsForBox:", _MEDIA_BOX, argtypes=(ctypes.c_long,), restype=_objc.CGRect)
        width, height = bounds.size.width, bounds.size.height
        # A page with /Rotate 90 or 270 is drawn turned: fit the turned shape.
        if _objc.send(target, "rotation", restype=ctypes.c_long) % 180:
            width, height = height, width
        scale = size / (max(width, height) or 1.0)
        # PDFKit rounds the image size down: the extra half pixel makes the
        # longest side come out at exactly `size`.
        box = _objc.CGSize(width * scale + 0.5, height * scale + 0.5)
        image = _objc.send(
            target, "thumbnailOfSize:forBox:", box, _MEDIA_BOX, argtypes=(_objc.CGSize, ctypes.c_long)
        )
        tiff = _objc.send(image, "TIFFRepresentation")
        rep = _objc.send(_objc.cls("NSBitmapImageRep"), "imageRepWithData:", tiff, argtypes=(_objc.id,))
        if not rep:
            raise MacOSError("page {} could not be drawn".format(page))
        return _objc.png(rep)
