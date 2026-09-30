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
import math
import os
import shutil
import tempfile
from contextlib import contextmanager
from functools import lru_cache
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, Union

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
    "watermark",
    "ocr",
    "compress",
    "grayscale",
    "render",
    "from_images",
    "Metadata",
    "FormField",
    "form_fields",
    "fill_form",
    "sign",
    "add_text",
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


@lru_cache(maxsize=None)
def _core_text() -> ctypes.CDLL:
    text_library = framework("CoreText")
    pointer = ctypes.c_void_p
    text_library.CTFontCreateWithName.argtypes = (pointer, ctypes.c_double, pointer)
    text_library.CTFontCreateWithName.restype = pointer
    text_library.CTLineCreateWithAttributedString.argtypes = (pointer,)
    text_library.CTLineCreateWithAttributedString.restype = pointer
    text_library.CTLineGetTypographicBounds.argtypes = (
        pointer,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    )
    text_library.CTLineGetTypographicBounds.restype = ctypes.c_double
    text_library.CTLineDraw.argtypes = (pointer, pointer)
    text_library.CTLineDraw.restype = None
    return text_library


def _line(text: str, size: float) -> Tuple[int, float, float]:
    """An owned Core Text line of ``text`` in bold Helvetica, its width and its height (ascent + descent)."""
    from . import _cf

    core_text = _core_text()
    with _cf.owned(_cf.string("Helvetica-Bold")) as name:
        font = core_text.CTFontCreateWithName(name, size, None)
    true = _cf.constant(_cf.lib(), "kCFBooleanTrue")
    attributes = _cf.dictionary(
        {
            _cf.constant(core_text, "kCTFontAttributeName"): font,
            # Take the color (and transparency) from the drawing context.
            _cf.constant(core_text, "kCTForegroundColorFromContextAttributeName"): true,
        }
    )
    cf = _cf.lib()
    cf.CFAttributedStringCreate.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    cf.CFAttributedStringCreate.restype = ctypes.c_void_p
    with _cf.owned(font), _cf.owned(attributes), _cf.owned(_cf.string(text)) as string:
        with _cf.owned(cf.CFAttributedStringCreate(None, string, attributes)) as attributed:
            line = core_text.CTLineCreateWithAttributedString(attributed)
    ascent, descent, leading = ctypes.c_double(), ctypes.c_double(), ctypes.c_double()
    width = core_text.CTLineGetTypographicBounds(line, ctypes.byref(ascent), ctypes.byref(descent), ctypes.byref(leading))
    return line, float(width), ascent.value + descent.value


def _color(text: str) -> Tuple[float, float, float]:
    value = text.strip().lstrip("#")
    if len(value) != 6 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise ValueError("color must be a hex color such as '#ff0000', not {!r}".format(text))
    return (int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255)


def _open_for_drawing(source: Path, password: Optional[str]) -> int:
    """An owned, unlocked ``CGPDFDocument``, to draw its pages elsewhere; release it with ``CGPDFDocumentRelease``."""
    from . import _cf

    graphics = _graphics()
    with _cf.owned(_cf.file_url(str(source))) as url:
        document = graphics.CGPDFDocumentCreateWithURL(url)
    if not document:
        raise ValueError("{} is not a PDF".format(source))
    if graphics.CGPDFDocumentIsEncrypted(document) and not graphics.CGPDFDocumentIsUnlocked(document):
        unlocked = password is not None and graphics.CGPDFDocumentUnlockWithPassword(document, password.encode("utf-8"))
        if not unlocked:
            graphics.CGPDFDocumentRelease(document)
            raise PermissionDeniedError(
                "{} is encrypted: {}".format(source, "wrong password" if password else "pass its password")
            )
    return int(document)


_INVISIBLE = 3  # kCGTextInvisible: text that selection and search find, but that doesn't show


def ocr(
    path: PathLike,
    output: PathLike,
    *,
    languages: Optional[Sequence[str]] = None,
    redo: bool = False,
    password: Optional[str] = None,
) -> Path:
    """
    Make a scanned PDF searchable: add the text Vision reads on each page, invisibly, and save it to ``output``.

    ::

        macos.pdf.ocr("scan.pdf", "scan-searchable.pdf")
        macos.pdf.text("scan-searchable.pdf")   # the text of the scan

    The pages look the same, and their text can now be selected, copied and
    searched, in Preview, Spotlight or :func:`text`. Pages that already have
    text aren't read again, unless ``redo=True``. As with :func:`watermark`,
    every page is redrawn into the new PDF, so links and form fields aren't kept. ``languages`` works as in
    :func:`macos.vision.lines` (``["pt-BR", "en-US"]``). ``password`` opens an
    encrypted PDF; the result isn't encrypted.
    """
    from . import _cf, vision

    source = Path(path).expanduser().absolute()
    if not source.exists():
        raise FileNotFoundError(str(source))
    graphics, core_text = _graphics(), _core_text()
    document = _open_for_drawing(source, password)
    try:
        pages = graphics.CGPDFDocumentGetNumberOfPages(document)
        # Read every page first: rendering and OCR use the file, not the context being written.
        found: Dict[int, List[Any]] = {}
        for number in range(1, pages + 1):
            if not redo and text(source, [number], password=password).strip():
                continue
            page = graphics.CGPDFDocumentGetPage(document, number)
            box = graphics.CGPDFPageGetBoxRect(page, _MEDIA_BOX)
            longest = max(box.size.width, box.size.height)
            image = render(source, number, size=int(min(4096, max(1024, longest * 3))), password=password)
            # Word by word: one stretched line would space its words wrong for search and copy.
            found[number] = vision._words(image, languages=languages)

        def write(name: str) -> bool:
            with _cf.owned(_cf.file_url(name)) as url:
                context = graphics.CGPDFContextCreateWithURL(url, None, None)
            if not context:
                return False
            try:
                for number in range(1, pages + 1):
                    page = graphics.CGPDFDocumentGetPage(document, number)
                    box = graphics.CGPDFPageGetBoxRect(page, _MEDIA_BOX)
                    width, height = box.size.width, box.size.height
                    if graphics.CGPDFPageGetRotationAngle(page) % 180:
                        width, height = height, width  # drawn as it shows, turned, like render() reads it
                    frame = _objc.CGRect(_objc.CGPoint(0, 0), _objc.CGSize(width, height))
                    graphics.CGContextBeginPage(context, ctypes.byref(frame))
                    graphics.CGContextSaveGState(context)
                    graphics.CGContextConcatCTM(
                        context, graphics.CGPDFPageGetDrawingTransform(page, _MEDIA_BOX, frame, 0, True)
                    )
                    graphics.CGContextDrawPDFPage(context, page)
                    graphics.CGContextRestoreGState(context)
                    for word, word_box in found.get(number, []):
                        _draw_invisible(graphics, core_text, context, word, word_box, width, height)
                    graphics.CGContextEndPage(context)
                graphics.CGPDFContextClose(context)
            finally:
                graphics.CGContextRelease(context)
            return True

        return _write_atomically(output, write)
    finally:
        graphics.CGPDFDocumentRelease(document)


def _draw_invisible(
    graphics: ctypes.CDLL,
    core_text: ctypes.CDLL,
    context: int,
    words: str,
    box: Tuple[float, float, float, float],
    width: float,
    height: float,
) -> None:
    """Write ``words`` invisibly over ``box`` (fractions of the page from its top-left), stretched to its width."""
    from . import _cf

    if not words.strip():
        return
    left, top, wide, tall = box[0] * width, box[1] * height, box[2] * width, box[3] * height
    size = max(tall, 1.0)
    probe, natural_width, _ = _line(words, size)
    _cf.release(probe)
    # A real space after the word: text extraction spaces words by their space characters.
    line, _, _ = _line(words + " ", size)
    try:
        graphics.CGContextSaveGState(context)
        graphics.CGContextSetTextDrawingMode(context, _INVISIBLE)
        # PDF pages measure from their bottom-left corner, going up.
        graphics.CGContextTranslateCTM(context, left, height - top - tall + tall * 0.2)
        graphics.CGContextScaleCTM(context, wide / max(natural_width, 1.0), 1.0)
        graphics.CGContextSetTextPosition(context, 0, 0)
        core_text.CTLineDraw(line, context)
        graphics.CGContextRestoreGState(context)
    finally:
        _cf.release(line)


def watermark(
    path: PathLike,
    text: str,
    output: PathLike,
    *,
    color: str = "#808080",
    opacity: float = 0.25,
    password: Optional[str] = None,
) -> Path:
    """
    Write ``text`` across every page, diagonally and see-through, and save the result to ``output``.

    For drafts and copies you share: ``"CONFIDENTIAL"``, ``"DRAFT"``, a
    name... ``color`` is a hex color and ``opacity`` goes from 0.0
    (invisible) to 1.0. The text is sized to fit each page::

        macos.pdf.watermark("contract.pdf", "DRAFT", "contract-draft.pdf")
        macos.pdf.watermark("id.pdf", "Only for Acme Inc.", "id-acme.pdf", color="#d00000", opacity=0.3)

    The pages keep their look and their text, but not their links or form
    fields, which are redrawn as they appear. ``password`` opens an
    encrypted PDF; the result isn't encrypted.
    """
    if not text.strip():
        raise ValueError("the watermark text can't be empty")
    if not 0.0 < opacity <= 1.0:
        raise ValueError("opacity must be above 0.0 and at most 1.0, not {}".format(opacity))
    red, green, blue = _color(color)
    source = Path(path).expanduser().absolute()
    if not source.exists():
        raise FileNotFoundError(str(source))
    from . import _cf

    graphics, core_text = _graphics(), _core_text()
    document = _open_for_drawing(source, password)
    try:
        pages = graphics.CGPDFDocumentGetNumberOfPages(document)

        def write(name: str) -> bool:
            with _cf.owned(_cf.file_url(name)) as url:
                context = graphics.CGPDFContextCreateWithURL(url, None, None)
            if not context:
                return False
            try:
                for number in range(1, pages + 1):
                    page = graphics.CGPDFDocumentGetPage(document, number)
                    box = graphics.CGPDFPageGetBoxRect(page, _MEDIA_BOX)
                    width, height = box.size.width, box.size.height
                    if graphics.CGPDFPageGetRotationAngle(page) % 180:
                        width, height = height, width  # draw it as it shows, turned
                    frame = _objc.CGRect(_objc.CGPoint(0, 0), _objc.CGSize(width, height))
                    graphics.CGContextBeginPage(context, ctypes.byref(frame))
                    graphics.CGContextSaveGState(context)
                    graphics.CGContextConcatCTM(
                        context, graphics.CGPDFPageGetDrawingTransform(page, _MEDIA_BOX, frame, 0, True)
                    )
                    graphics.CGContextDrawPDFPage(context, page)
                    graphics.CGContextRestoreGState(context)
                    # The text along the page's diagonal, over 70% of its length.
                    angle = math.atan2(height, width)
                    probe, natural, _ = _line(text, 100)
                    _cf.release(probe)
                    size = 100 * 0.7 * math.hypot(width, height) / max(natural, 1.0)
                    line, line_width, line_height = _line(text, size)
                    try:
                        graphics.CGContextSaveGState(context)
                        graphics.CGContextSetRGBFillColor(context, red, green, blue, opacity)
                        graphics.CGContextTranslateCTM(context, width / 2, height / 2)
                        graphics.CGContextRotateCTM(context, angle)
                        graphics.CGContextSetTextPosition(context, -line_width / 2, -line_height / 3)
                        core_text.CTLineDraw(line, context)
                        graphics.CGContextRestoreGState(context)
                    finally:
                        _cf.release(line)
                    graphics.CGContextEndPage(context)
                graphics.CGPDFContextClose(context)
            finally:
                graphics.CGContextRelease(context)
            return True

        return _write_atomically(output, write)
    finally:
        graphics.CGPDFDocumentRelease(document)


def compress(path: PathLike, output: PathLike, *, password: Optional[str] = None) -> Path:
    """
    Save a smaller copy of a PDF, like Preview's *Export › Reduce File Size*, and return ``output``.

    Images are scaled down and compressed again, which makes PDFs of scans
    and photos several times smaller; text and drawings stay sharp. Photos
    lose detail, so keep the original. A PDF with no images to shrink (only
    text) can't get smaller: then ``output`` is a copy of it, never a bigger
    file. ``password`` opens an encrypted PDF; the result isn't encrypted.
    """
    return _filtered(path, output, "Reduce File Size", password, keep_smaller=True)


def grayscale(path: PathLike, output: PathLike, *, password: Optional[str] = None) -> Path:
    """
    Save a copy of a PDF in shades of gray, for printing without color, and return ``output``.

    Uses the *Gray Tone* filter that ships with macOS, like Preview's
    *Export › Quartz Filter*. ``password`` opens an encrypted PDF; the result
    isn't encrypted.
    """
    return _filtered(path, output, "Gray Tone", password)


def _filtered(path: PathLike, output: PathLike, name: str, password: Optional[str], keep_smaller: bool = False) -> Path:
    """Write ``path`` through the Quartz filter ``name`` (from /System/Library/Filters) into ``output``."""
    framework("Quartz")
    location = "/System/Library/Filters/{}.qfilter".format(name)
    with _open(path, password) as document:
        quartz_filter = _objc.send(
            _objc.cls("QuartzFilter"), "quartzFilterWithURL:", _objc.file_url(location), argtypes=(_objc.id,)
        )
        if not quartz_filter:
            raise MacOSError("this macOS has no {} filter".format(name))
        options = _objc.send(
            _objc.cls("NSDictionary"),
            "dictionaryWithObject:forKey:",
            quartz_filter,
            _objc.nsstring("QuartzFilter"),
            argtypes=(_objc.id, _objc.id),
        )
        encrypted = bool(_objc.send(document, "isEncrypted", restype=BOOL))
        source = Path(path).expanduser().absolute()
        target = Path(output).expanduser().absolute()
        if encrypted:
            # PDFKit keeps the encryption when it writes an unlocked
            # document: copy its pages into a new, unencrypted one.
            plain = _new_document()
            for number in range(1, _count(document) + 1):
                _append(plain, _page(document, number))
            document = plain
        if not keep_smaller or encrypted:
            return _save(document, output, options)
        # Rewriting a PDF can make it bigger (PDFKit writes less compactly
        # than some tools do), and the filter only shrinks images: write it
        # aside first, and keep the original when it isn't smaller. That also
        # protects the original when the output is the input itself.
        handle, name = tempfile.mkstemp(dir=str(target.parent) if target.parent.is_dir() else None, suffix=".pdf")
        os.close(handle)
        candidate = Path(name)
        try:
            _save(document, candidate, options)
            smaller = candidate.stat().st_size < source.stat().st_size
        except BaseException:
            candidate.unlink(missing_ok=True)
            raise
    try:
        if smaller:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(candidate), str(target))
        elif target != source:
            _write_atomically(target, lambda name: bool(shutil.copyfile(str(source), name)))
    finally:
        candidate.unlink(missing_ok=True)
    return target


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
        "CGPDFDocumentCreateWithURL": ((pointer,), pointer),
        "CGPDFDocumentIsEncrypted": ((pointer,), ctypes.c_bool),
        "CGPDFDocumentIsUnlocked": ((pointer,), ctypes.c_bool),
        "CGPDFDocumentUnlockWithPassword": ((pointer, ctypes.c_char_p), ctypes.c_bool),
        "CGPDFDocumentGetNumberOfPages": ((pointer,), ctypes.c_size_t),
        "CGPDFDocumentGetPage": ((pointer, ctypes.c_size_t), pointer),
        "CGPDFDocumentRelease": ((pointer,), None),
        "CGPDFPageGetBoxRect": ((pointer, ctypes.c_int), _objc.CGRect),
        "CGPDFPageGetRotationAngle": ((pointer,), ctypes.c_int),
        "CGPDFPageGetDrawingTransform": (
            (pointer, ctypes.c_int, _objc.CGRect, ctypes.c_int, ctypes.c_bool),
            _objc.CGAffineTransform,
        ),
        "CGContextDrawPDFPage": ((pointer, pointer), None),
        "CGContextSetRGBFillColor": ((pointer, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double), None),
        "CGContextTranslateCTM": ((pointer, ctypes.c_double, ctypes.c_double), None),
        "CGContextRotateCTM": ((pointer, ctypes.c_double), None),
        "CGContextSetTextPosition": ((pointer, ctypes.c_double, ctypes.c_double), None),
        "CGContextSetTextDrawingMode": ((pointer, ctypes.c_int32), None),
        "CGContextScaleCTM": ((pointer, ctypes.c_double, ctypes.c_double), None),
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


# --- Forms ----------------------------------------------------------------------

_FIELD_KINDS = {"/Tx": "text", "/Ch": "choice", "/Sig": "signature"}
_BUTTON_KINDS = {0: "button", 1: "radio", 2: "checkbox"}  # PDFWidgetControlType


@dataclass(frozen=True)
class FormField:
    """A field of a PDF form."""

    name: str
    kind: str
    """``'text'``, ``'checkbox'``, ``'radio'``, ``'choice'`` (a list or a menu), ``'button'`` or ``'signature'``."""
    value: Union[str, bool, None]
    """The text or choice filled in, whether a checkbox is ticked, the radio button chosen; ``None`` when empty."""
    options: Tuple[str, ...]
    """What a choice or a group of radio buttons offers; ``()`` for the others."""
    page: int
    """The page it's on, from 1."""


def _widgets(document: int) -> Iterator[Tuple[int, int]]:
    """``(page number, widget annotation)`` for every form field's widget, in page order."""
    for number in range(1, _count(document) + 1):
        page = _page(document, number)
        for annotation in _objc.nsarray(_objc.send(page, "annotations")):
            kind = _objc.pystring(_objc.send(annotation, "type")) or ""
            name = _objc.pystring(_objc.send(annotation, "fieldName"))
            if kind == "Widget" and name:
                yield number, annotation


def _kind(widget: int) -> str:
    field_type = _objc.pystring(_objc.send(widget, "widgetFieldType")) or ""
    if field_type == "/Btn":
        return _BUTTON_KINDS.get(int(_objc.send(widget, "widgetControlType", restype=ctypes.c_long)), "button")
    return _FIELD_KINDS.get(field_type, "text")


def _state(widget: int) -> bool:
    return bool(_objc.send(widget, "buttonWidgetState", restype=ctypes.c_long))


def _on_value(widget: int) -> str:
    """The value a radio button stands for (its "on" state's name)."""
    return _objc.pystring(_objc.send(widget, "buttonWidgetStateString")) or ""


def form_fields(path: PathLike, *, password: Optional[str] = None) -> List[FormField]:
    """
    The fields of a PDF form, in page order, with what's filled in.

    ::

        for field in macos.pdf.form_fields("application.pdf"):
            print(field.name, field.kind, field.value)   # "Full name" text None, "Agree" checkbox False, ...

    Fill them with :func:`fill_form`.
    """
    fields: Dict[str, FormField] = {}
    with _open(path, password) as document:
        for number, widget in _widgets(document):
            name = _objc.pystring(_objc.send(widget, "fieldName")) or ""
            kind = _kind(widget)
            if kind == "radio":
                # The buttons of a group share its name: the field's value is the one chosen.
                known = fields.get(name)
                group = (known.options if known else ()) + (_on_value(widget),)
                chosen = _on_value(widget) if _state(widget) else (known.value if known else None)
                fields[name] = FormField(name, kind, chosen, group, known.page if known else number)
                continue
            if name in fields:
                continue  # the same field shown again, on another page
            if kind == "checkbox":
                value: Union[str, bool, None] = _state(widget)
            elif kind in ("button", "signature"):
                value = None
            else:
                value = _objc.pystring(_objc.send(widget, "widgetStringValue")) or None
            options: Tuple[str, ...] = ()
            if kind == "choice":
                options = tuple(_objc.pystring(item) or "" for item in _objc.nsarray(_objc.send(widget, "choices")))
            fields[name] = FormField(name, kind, value, options, number)
    return list(fields.values())


def fill_form(
    path: PathLike,
    values: Mapping[str, Union[str, bool]],
    output: PathLike,
    *,
    password: Optional[str] = None,
) -> Path:
    """
    Fill in a PDF form's fields by name, and save it to ``output``; the fields stay editable.

    ::

        macos.pdf.fill_form("application.pdf", {"Full name": "Ana Souza", "Agree": True, "Plan": "Pro"}, "filled.pdf")

    Text fields and choices take text; checkboxes ``True`` or ``False``; a
    group of radio buttons the option to choose. The names are those
    :func:`form_fields` gives; an unknown one, or an option a field doesn't
    offer, raises :class:`ValueError` before anything is written.
    """
    known = {field.name: field for field in form_fields(path, password=password)}
    for name, value in values.items():
        field = known.get(name)
        if field is None:
            raise ValueError("the form has no field named {!r}; see macos.pdf.form_fields()".format(name))
        if field.kind == "checkbox" and not isinstance(value, bool):
            raise ValueError("{!r} is a checkbox: pass True or False, not {!r}".format(name, value))
        if field.kind in ("text", "choice", "radio") and not isinstance(value, str):
            raise ValueError("{!r} takes text, not {!r}".format(name, value))
        if field.kind in ("radio", "choice") and field.options and value not in field.options:
            raise ValueError("{!r} offers {}, not {!r}".format(name, ", ".join(field.options), value))
        if field.kind in ("button", "signature"):
            raise ValueError("{!r} is a {} field: it can't be filled in".format(name, field.kind))
    with _open(path, password) as document:
        for _, widget in _widgets(document):
            name = _objc.pystring(_objc.send(widget, "fieldName")) or ""
            if name not in values:
                continue
            value, kind = values[name], known[name].kind
            if kind == "checkbox":
                _objc.send(widget, "setButtonWidgetState:", 1 if value else 0, argtypes=(ctypes.c_long,), restype=None)
            elif kind == "radio":
                chosen = 1 if _on_value(widget) == value else 0
                _objc.send(widget, "setButtonWidgetState:", chosen, argtypes=(ctypes.c_long,), restype=None)
            else:
                _objc.send(widget, "setWidgetStringValue:", _objc.nsstring(str(value)), argtypes=(_objc.id,), restype=None)
        return _save(document, output)


# --- Signing --------------------------------------------------------------------

_CORNERS = ("bottom_right", "bottom_left", "top_right", "top_left")
Position = Union[str, Tuple[float, float]]


def _check_position(position: Position) -> None:
    if isinstance(position, str) and position not in _CORNERS:
        raise ValueError("position must be one of {} or (x, y), not {!r}".format(", ".join(_CORNERS), position))


def _origin(
    position: Position, width: float, height: float, page_width: float, page_height: float, margin: float
) -> Tuple[float, float]:
    """Where a box of ``width`` × ``height`` goes: its bottom-left corner, in points from the page's bottom-left."""
    if isinstance(position, tuple):
        return float(position[0]), float(position[1])
    x = margin if position.endswith("left") else page_width - margin - width
    y = margin if position.startswith("bottom") else page_height - margin - height
    return x, y


def sign(
    path: PathLike,
    image: PathLike,
    output: PathLike,
    *,
    page: Optional[int] = None,
    position: Position = "bottom_right",
    width: float = 150,
    margin: float = 36,
    password: Optional[str] = None,
) -> Path:
    """
    Put an image of a signature (or a stamp, a logo) on a page, and save the result to ``output``.

    ::

        macos.pdf.sign("contract.pdf", "signature.png", "signed.pdf")                   # last page, bottom right
        macos.pdf.sign("form.pdf", "signature.png", "signed.pdf", page=1, position=(72, 120), width=180)

    ``page`` is from 1; the last one by default. ``position`` is a corner
    (``"bottom_right"``, ``"bottom_left"``, ``"top_right"``, ``"top_left"``,
    ``margin`` points from the edges) or the ``(x, y)`` of the image's
    bottom-left corner, in points from the page's bottom-left. ``width`` is
    in points (72 per inch); the height keeps the image's proportions. A PNG
    with a transparent background looks best.

    It's an image, not a cryptographic signature. The pages are redrawn
    as they look, filled-in form fields included, so they're no longer
    editable, and links go: fill the form first, with :func:`fill_form`.
    """
    from . import image as images

    if width <= 0:
        raise ValueError("width must be positive, not {}".format(width))
    _check_position(position)
    source, _ = _image_source(image)
    with _cf.owned(source):
        picture = images._io().CGImageSourceCreateImageAtIndex(source, 0, None)
    if not picture:
        raise ValueError("{} is not an image macOS can read".format(image))
    graphics = _graphics()
    try:
        with _open(path, password) as document:
            count = _count(document)
            target = count if page is None else page
            _page(document, target)  # checks the number
            aspect = graphics.CGImageGetHeight(picture) / max(graphics.CGImageGetWidth(picture), 1)

            def write(name: str) -> bool:
                with _cf.owned(_cf.file_url(name)) as url:
                    context = graphics.CGPDFContextCreateWithURL(url, None, None)
                if not context:
                    return False
                try:
                    for number in range(1, count + 1):
                        current = _page(document, number)
                        bounds = _objc.send(
                            current, "boundsForBox:", _MEDIA_BOX, argtypes=(ctypes.c_long,), restype=_objc.CGRect
                        )
                        if _objc.send(current, "rotation", restype=ctypes.c_long) % 180:
                            bounds = _objc.CGRect(bounds.origin, _objc.CGSize(bounds.size.height, bounds.size.width))
                        box = _objc.CGRect(_objc.CGPoint(0, 0), bounds.size)
                        graphics.CGContextBeginPage(context, ctypes.byref(box))
                        # PDFKit draws the page as it looks, rotation and form fields included.
                        _objc.send(
                            current,
                            "drawWithBox:toContext:",
                            _MEDIA_BOX,
                            context,
                            argtypes=(ctypes.c_long, _objc.id),
                            restype=None,
                        )
                        if number == target:
                            size = _objc.CGSize(width, width * aspect)
                            x, y = _origin(position, size.width, size.height, box.size.width, box.size.height, margin)
                            graphics.CGContextDrawImage(context, _objc.CGRect(_objc.CGPoint(x, y), size), picture)
                        graphics.CGContextEndPage(context)
                    graphics.CGPDFContextClose(context)
                finally:
                    graphics.CGContextRelease(context)
                return True

            return _write_atomically(output, write)
    finally:
        _cf.release(picture)


# --- Adding text --------------------------------------------------------------


def add_text(
    path: PathLike,
    text: str,
    output: PathLike,
    *,
    page: int = 1,
    position: Position = "top_left",
    size: float = 12,
    color: str = "#000000",
    font: Optional[str] = None,
    margin: float = 36,
    password: Optional[str] = None,
) -> Path:
    """
    Write ``text`` on a page, as a text box you can still edit or move in Preview, and save the result to ``output``.

    ::

        macos.pdf.add_text("contract.pdf", "Received on 29/09/2026", "stamped.pdf")            # page 1, top left
        macos.pdf.add_text("form.pdf", "Ana Souza", "filled.pdf", page=2, position=(120, 540), size=14)
        macos.pdf.add_text("draft.pdf", "Checked\\nby Ana", "notes.pdf", position="top_right", color="#c00000")

    ``position`` works as for :func:`sign`: a corner, ``margin`` points from
    the edges, or the ``(x, y)`` of the text's bottom-left corner, in points
    from the page's bottom-left. ``size`` is in points; ``font`` a font's
    name, such as ``"Helvetica-Bold"`` (the system font by default); ``color``
    a hex color. Lines break at ``\\n``. The page's own text is left as it
    is: this adds to it.
    """
    if not text.strip():
        raise ValueError("text must not be empty")
    if size <= 0:
        raise ValueError("size must be positive, not {}".format(size))
    _check_position(position)
    red, green, blue = _color(color)
    framework("AppKit")
    with _open(path, password) as document:
        target = _page(document, page)
        if font is None:
            typeface = _objc.send(_objc.cls("NSFont"), "systemFontOfSize:", float(size), argtypes=(ctypes.c_double,))
        else:
            typeface = _objc.send(
                _objc.cls("NSFont"), "fontWithName:size:", _objc.nsstring(font), float(size), argtypes=(_objc.id, ctypes.c_double)
            )
            if not typeface:
                raise ValueError("no font is named {!r}; see macos.system.fonts()".format(font))
        ink = _objc.send(
            _objc.cls("NSColor"),
            "colorWithSRGBRed:green:blue:alpha:",
            red,
            green,
            blue,
            1.0,
            argtypes=(ctypes.c_double,) * 4,
        )
        # Measure the text as it will be drawn, to size the box around it.
        attributes = _objc.send(
            _objc.cls("NSDictionary"),
            "dictionaryWithObject:forKey:",
            typeface,
            _objc.nsstring("NSFont"),
            argtypes=(_objc.id, _objc.id),
        )
        measured = _objc.send(
            _objc.send(_objc.cls("NSAttributedString"), "alloc"),
            "initWithString:attributes:",
            _objc.nsstring(text),
            attributes,
            argtypes=(_objc.id, _objc.id),
        )
        _objc.send(measured, "autorelease")
        extent = _objc.send(measured, "size", restype=_objc.CGSize)
        width, height = extent.width + 8, extent.height + 4  # a little room: FreeText boxes pad their text
        bounds = _objc.send(target, "boundsForBox:", _MEDIA_BOX, argtypes=(ctypes.c_long,), restype=_objc.CGRect)
        x, y = _origin(position, width, height, bounds.size.width, bounds.size.height, margin)
        box = _objc.CGRect(_objc.CGPoint(bounds.origin.x + x, bounds.origin.y + y), _objc.CGSize(width, height))
        note = _objc.send(
            _objc.send(_objc.cls("PDFAnnotation"), "alloc"),
            "initWithBounds:forType:withProperties:",
            box,
            _objc.nsstring("FreeText"),
            None,
            argtypes=(_objc.CGRect, _objc.id, _objc.id),
        )
        _objc.send(note, "autorelease")
        _objc.send(note, "setContents:", _objc.nsstring(text), argtypes=(_objc.id,), restype=None)
        _objc.send(note, "setFont:", typeface, argtypes=(_objc.id,), restype=None)
        _objc.send(note, "setFontColor:", ink, argtypes=(_objc.id,), restype=None)
        clear = _objc.send(_objc.cls("NSColor"), "clearColor")
        _objc.send(note, "setColor:", clear, argtypes=(_objc.id,), restype=None)  # no background
        border = _objc.send(_objc.send(_objc.cls("PDFBorder"), "alloc"), "init")
        _objc.send(border, "autorelease")
        _objc.send(border, "setLineWidth:", 0.0, argtypes=(ctypes.c_double,), restype=None)
        _objc.send(note, "setBorder:", border, argtypes=(_objc.id,), restype=None)
        _objc.send(target, "addAnnotation:", note, argtypes=(_objc.id,), restype=None)
        return _save(document, output)
