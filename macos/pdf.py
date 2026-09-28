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
from functools import lru_cache
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from . import _cf, _objc
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


def _write_atomically(output: PathLike, write: Callable[[str], bool]) -> Path:
    """
    Call ``write`` with a temporary path next to ``output``, then move the file in place.

    The output may be one of the inputs, which PDFKit reads lazily while
    writing; and a failure never leaves a half-written file behind.
    """
    target = Path(output).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=str(target.parent), suffix=".pdf")
    os.close(handle)
    try:
        if not write(name):
            raise MacOSError("could not write {}".format(target))
        os.replace(name, str(target))
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return target


def _save(document: int, output: PathLike, options: Optional[int] = None) -> Path:
    def write(name: str) -> bool:
        if options:
            return bool(
                _objc.send(
                    document,
                    "writeToFile:withOptions:",
                    _objc.nsstring(name),
                    options,
                    argtypes=(_objc.id, _objc.id),
                    restype=BOOL,
                )
            )
        return bool(_objc.send(document, "writeToFile:", _objc.nsstring(name), argtypes=(_objc.id,), restype=BOOL))

    return _write_atomically(output, write)


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


@lru_cache(maxsize=None)
def _graphics() -> ctypes.CDLL:
    graphics = framework("CoreGraphics")
    pointer = ctypes.c_void_p
    rect = ctypes.POINTER(_objc.CGRect)
    signatures = {
        "CGPDFContextCreateWithURL": ((pointer, rect, pointer), pointer),
        "CGContextBeginPage": ((pointer, rect), None),
        "CGContextEndPage": ((pointer,), None),
        "CGPDFContextClose": ((pointer,), None),
        "CGContextRelease": ((pointer,), None),
        "CGContextSaveGState": ((pointer,), None),
        "CGContextRestoreGState": ((pointer,), None),
        "CGContextConcatCTM": ((pointer, _objc.CGAffineTransform), None),
        "CGContextDrawImage": ((pointer, _objc.CGRect, pointer), None),
        "CGImageGetWidth": ((pointer,), ctypes.c_size_t),
        "CGImageGetHeight": ((pointer,), ctypes.c_size_t),
    }
    for name, (argtypes, restype) in signatures.items():
        function = getattr(graphics, name)
        function.argtypes = argtypes
        function.restype = restype
    return graphics


def _upright_transform(orientation: int, width: float, height: float) -> Tuple[float, ...]:
    """
    The transform that draws a ``width`` x ``height`` image stored with EXIF ``orientation`` upright.

    Core Graphics measures from the bottom-left corner, with y going up.
    """
    return {
        2: (-1, 0, 0, 1, width, 0),  # mirrored left to right
        3: (-1, 0, 0, -1, width, height),  # upside down
        4: (1, 0, 0, -1, 0, height),  # mirrored top to bottom
        5: (0, -1, -1, 0, height, width),  # transposed
        6: (0, -1, 1, 0, 0, width),  # needs a quarter turn clockwise
        7: (0, 1, 1, 0, 0, 0),  # transversed
        8: (0, 1, -1, 0, height, 0),  # needs a quarter turn counter-clockwise
    }.get(orientation, (1, 0, 0, 1, 0, 0))


def _image_source(image: Union[PathLike, bytes]) -> Tuple[int, str]:
    """An owned ``CGImageSource`` for a path or image bytes, and how to name it in errors."""
    from . import image as images

    if isinstance(image, (bytes, bytearray)):
        with _cf.owned(_cf.data(bytes(image))) as payload:
            source = images._io().CGImageSourceCreateWithData(payload, None)
        if not source or not images._io().CGImageSourceGetCount(source):
            _cf.release(source)
            raise ValueError("the bytes are not an image macOS can read")
        return source, "image bytes"
    return images._source(image), str(Path(image).expanduser().absolute())


def from_images(images: Sequence[Union[PathLike, bytes]], output: PathLike) -> Path:
    """
    Make a PDF with one page per image, in order, and return its path.

    Any format macOS opens works (JPEG, PNG, HEIC...). Each page takes the size
    of its image, turned upright, so photos of documents become the pages of a
    scan::

        pages = [macos.vision.scan_document(photo) for photo in photos]
        macos.pdf.from_images(pages, "scan.pdf")

    ``images`` may also hold PNG/JPEG bytes, such as :func:`macos.vision.scan_document` returns.
    JPEG photos are embedded as they are, without compressing them again.
    """
    if not images:
        raise ValueError("from_images() needs at least one image")
    from . import image as image_module

    io = image_module._io()
    graphics = _graphics()
    # Read every image first, so a bad one fails before anything is written.
    pictures = []
    try:
        for image in images:
            source, label = _image_source(image)
            with _cf.owned(source):
                orientation = image_module._describe(source).orientation
                picture = io.CGImageSourceCreateImageAtIndex(source, 0, None)
            if not picture:
                raise ValueError("{} is not an image macOS can read".format(label))
            pictures.append((picture, orientation))

        def write(name: str) -> bool:
            with _cf.owned(_cf.file_url(name)) as url:
                context = graphics.CGPDFContextCreateWithURL(url, None, None)
            if not context:
                return False
            try:
                for picture, orientation in pictures:
                    width, height = float(graphics.CGImageGetWidth(picture)), float(graphics.CGImageGetHeight(picture))
                    upright = (height, width) if orientation in (5, 6, 7, 8) else (width, height)
                    page = _objc.CGRect(_objc.CGPoint(0, 0), _objc.CGSize(*upright))
                    graphics.CGContextBeginPage(context, ctypes.byref(page))
                    graphics.CGContextSaveGState(context)
                    graphics.CGContextConcatCTM(
                        context, _objc.CGAffineTransform(*_upright_transform(orientation, width, height))
                    )
                    area = _objc.CGRect(_objc.CGPoint(0, 0), _objc.CGSize(width, height))
                    graphics.CGContextDrawImage(context, area, picture)
                    graphics.CGContextRestoreGState(context)
                    graphics.CGContextEndPage(context)
                graphics.CGPDFContextClose(context)
            finally:
                graphics.CGContextRelease(context)
            return True

        return _write_atomically(output, write)
    finally:
        for picture, _ in pictures:
            _cf.release(picture)
