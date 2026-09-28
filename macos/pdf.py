# -*- coding: utf-8 -*-

"""
Read, merge, split, rotate and encrypt PDFs, or make them from images.

::

    macos.pdf.page_count("report.pdf")              # 12
    macos.pdf.text("report.pdf")                    # all the text
    macos.pdf.text("report.pdf", pages=[1])         # just the first page
    macos.pdf.merge(["a.pdf", "b.pdf"], "both.pdf")
    macos.pdf.extract("report.pdf", [1, 3], "summary.pdf")
    macos.pdf.encrypt("report.pdf", "locked.pdf", password="1234")

Uses PDFKit, the framework behind Preview. Page numbers start at 1, like in
Preview.
"""

import ctypes
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Union

from . import _objc
from ._objc import BOOL, NSUInteger
from ._system import framework
from .errors import MacOSError, PermissionDeniedError

__all__ = [
    "page_count",
    "text",
    "metadata",
    "merge",
    "extract",
    "rotate",
    "encrypt",
    "render",
    "from_images",
    "Metadata",
]

PathLike = Union[str, "os.PathLike[str]"]

_MAX_RENDER = 4096
_MEDIA_BOX = 0  # kPDFDisplayBoxMediaBox


@dataclass(frozen=True)
class Metadata:
    """The information a PDF records about itself, as in Preview's *Tools › Show Inspector*."""

    title: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    keywords: List[str]
    creator: Optional[str]
    """The app the document was made in, such as ``'Microsoft Word'``."""
    producer: Optional[str]
    """The software that wrote the PDF, such as ``'macOS Version 15.6 Quartz PDFContext'``."""
    created: Optional[datetime]
    """In the local time zone."""
    modified: Optional[datetime]


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


def _attribute_text(attributes: int, key: str) -> Optional[str]:
    value = _objc.send(attributes, "objectForKey:", _objc.nsstring(key), argtypes=(_objc.id,))
    if not value or not _objc.send(value, "isKindOfClass:", _objc.cls("NSString"), argtypes=(_objc.id,), restype=BOOL):
        return None
    return (_objc.pystring(value) or "").strip() or None


def _attribute_date(attributes: int, key: str) -> Optional[datetime]:
    value = _objc.send(attributes, "objectForKey:", _objc.nsstring(key), argtypes=(_objc.id,))
    if not value or not _objc.send(value, "isKindOfClass:", _objc.cls("NSDate"), argtypes=(_objc.id,), restype=BOOL):
        return None
    return datetime.fromtimestamp(_objc.send(value, "timeIntervalSince1970", restype=ctypes.c_double)).astimezone()


def metadata(path: PathLike, *, password: Optional[str] = None) -> Metadata:
    """Return the title, author, keywords, dates and the apps that made a PDF."""
    with _open(path, password) as document:
        attributes = _objc.send(document, "documentAttributes")
        if not attributes:
            return Metadata(None, None, None, [], None, None, None, None)
        words = _objc.send(attributes, "objectForKey:", _objc.nsstring("Keywords"), argtypes=(_objc.id,))
        keywords: List[str] = []
        if words and _objc.send(words, "isKindOfClass:", _objc.cls("NSArray"), argtypes=(_objc.id,), restype=BOOL):
            keywords = [text for text in (_objc.pystring(word) for word in _objc.nsarray(words)) if text]
        elif words:
            # Some PDFs store the keywords as a single string.
            keywords = [word.strip() for word in (_objc.pystring(words) or "").split(",") if word.strip()]
        return Metadata(
            title=_attribute_text(attributes, "Title"),
            author=_attribute_text(attributes, "Author"),
            subject=_attribute_text(attributes, "Subject"),
            keywords=keywords,
            creator=_attribute_text(attributes, "Creator"),
            producer=_attribute_text(attributes, "Producer"),
            created=_attribute_date(attributes, "CreationDate"),
            modified=_attribute_date(attributes, "ModDate"),
        )


def _save(document: int, output: PathLike, options: Optional[int] = None) -> Path:
    target = Path(output).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write next to the target, then move it in place: the output may be one
    # of the inputs, which PDFKit reads lazily while writing.
    handle, name = tempfile.mkstemp(dir=str(target.parent), suffix=".pdf")
    os.close(handle)
    try:
        if options:
            written = _objc.send(
                document,
                "writeToFile:withOptions:",
                _objc.nsstring(name),
                options,
                argtypes=(_objc.id, _objc.id),
                restype=BOOL,
            )
        else:
            written = _objc.send(document, "writeToFile:", _objc.nsstring(name), argtypes=(_objc.id,), restype=BOOL)
        if not written:
            raise MacOSError("could not write {}".format(target))
        os.replace(name, str(target))
    finally:
        if os.path.exists(name):
            os.unlink(name)
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


def rotate(
    path: PathLike,
    degrees: int,
    output: PathLike,
    *,
    pages: Optional[Iterable[int]] = None,
    password: Optional[str] = None,
) -> Path:
    """
    Turn pages clockwise by ``degrees`` (90, 180 or 270; negative turns counter-clockwise) and save to ``output``.

    Every page turns, or only ``pages`` (numbered from 1). Handy for scans
    that came out sideways::

        macos.pdf.rotate("scan.pdf", 90, "scan.pdf", pages=[2])
    """
    if degrees % 90:
        raise ValueError("degrees must be a multiple of 90, not {}".format(degrees))
    with _open(path, password) as document:
        numbers = list(pages) if pages is not None else list(range(1, _count(document) + 1))
        for number in numbers:
            page = _page(document, number)
            current = _objc.send(page, "rotation", restype=ctypes.c_long)
            _objc.send(page, "setRotation:", (current + degrees) % 360, argtypes=(ctypes.c_long,), restype=None)
        return _save(document, output)


def _pdfkit_string(name: str) -> int:
    return ctypes.c_void_p.in_dll(framework("PDFKit"), name).value or 0


def encrypt(path: PathLike, output: PathLike, password: str, *, current_password: Optional[str] = None) -> Path:
    """
    Save a copy of a PDF that asks for ``password`` to open, and return its path.

    Preview, Acrobat and browsers all ask for it. ``current_password`` opens a
    PDF that is already encrypted, to change its password. To read or change
    an encrypted PDF with this module, pass ``password=`` to the other
    functions.
    """
    if not password:
        raise ValueError("the password can't be empty")
    with _open(path, current_password) as document:
        secret = _objc.nsstring(password)
        options = _objc.send(_objc.cls("NSMutableDictionary"), "dictionary")
        for key in ("PDFDocumentUserPasswordOption", "PDFDocumentOwnerPasswordOption"):
            _objc.send(
                options, "setObject:forKey:", secret, _pdfkit_string(key), argtypes=(_objc.id, _objc.id), restype=None
            )
        return _save(document, output, options)


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


def from_images(images: Sequence[Union[PathLike, bytes]], output: PathLike) -> Path:
    """
    Make a PDF with one page per image, in order, and return its path.

    Any format macOS opens works (JPEG, PNG, HEIC...). Each page takes the size
    of its image, so photos of documents become the pages of a scan::

        pages = [macos.vision.scan_document(photo) for photo in photos]
        macos.pdf.from_images(pages, "scan.pdf")

    ``images`` may also hold PNG/JPEG bytes, such as :func:`macos.vision.scan_document` returns.
    """
    if not images:
        raise ValueError("from_images() needs at least one image")
    framework("PDFKit")
    framework("AppKit")
    with _objc.autorelease_pool():
        document = _new_document()
        for image in images:
            picture = _objc.send(_objc.cls("NSImage"), "alloc")
            if isinstance(image, (bytes, bytearray)):
                picture = _objc.send(picture, "initWithData:", _objc.nsdata(bytes(image)), argtypes=(_objc.id,))
                label = "image bytes"
            else:
                path = Path(image).expanduser().absolute()
                if not path.exists():
                    raise FileNotFoundError(str(path))
                picture = _objc.send(picture, "initWithContentsOfFile:", _objc.nsstring(str(path)), argtypes=(_objc.id,))
                label = str(path)
            if not picture:
                raise ValueError("{} is not an image macOS can read".format(label))
            _objc.send(picture, "autorelease")
            page = _objc.send(_objc.send(_objc.cls("PDFPage"), "alloc"), "initWithImage:", picture, argtypes=(_objc.id,))
            if not page:
                raise MacOSError("{} could not be turned into a page".format(label))
            _objc.send(page, "autorelease")
            _objc.send(
                document, "insertPage:atIndex:", page, _count(document), argtypes=(_objc.id, NSUInteger), restype=None
            )
        return _save(document, output)
