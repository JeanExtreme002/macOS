# -*- coding: utf-8 -*-

"""
Read text in images (OCR) with Apple's Vision framework.

::

    macos.vision.text("receipt.png")                    # 'Total: R$ 42,00\\n...'
    macos.vision.text("scan.jpg", languages=["pt-BR"])
    for line in macos.vision.lines("slide.png"):
        print(line.text, line.confidence)

Recognition runs on the Mac, offline, with the same engine as Live Text in
Photos and Preview: nothing to install and no permission needed.
"""

import ctypes
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple, Union

from . import _objc
from ._objc import BOOL, NSInteger, NSUInteger
from ._system import framework
from .errors import MacOSError

__all__ = ["text", "lines", "languages", "barcodes", "classify", "faces", "TextLine", "Barcode"]

Image = Union[bytes, str, "os.PathLike[str]"]

# VNRequestTextRecognitionLevel
_ACCURATE = 0
_FAST = 1


@dataclass(frozen=True)
class TextLine:
    """A line of text found in an image."""

    text: str
    confidence: float
    """From 0.0 to 1.0."""
    box: Tuple[float, float, float, float]
    """``(x, y, width, height)`` as fractions of the image size, from its top-left corner."""


@dataclass(frozen=True)
class Barcode:
    """A barcode or QR code found in an image."""

    payload: Optional[str]
    """What it encodes, e.g. a URL (``None`` for binary content)."""
    kind: str
    """The symbology, e.g. ``'QR'``, ``'EAN13'``, ``'Code128'``, ``'PDF417'``."""
    box: Tuple[float, float, float, float]
    """``(x, y, width, height)`` as fractions of the image size, from its top-left corner."""


@lru_cache(maxsize=None)
def _load() -> None:
    framework("Foundation")
    framework("Vision")


def _handler(image: Image) -> int:
    """An autoreleased ``VNImageRequestHandler`` for a path or image bytes."""
    options = _objc.send(_objc.cls("NSDictionary"), "dictionary")
    handler = _objc.send(_objc.cls("VNImageRequestHandler"), "alloc")
    if isinstance(image, (bytes, bytearray)):
        handler = _objc.send(
            handler, "initWithData:options:", _objc.nsdata(bytes(image)), options, argtypes=(_objc.id, _objc.id)
        )
    else:
        path = Path(image).expanduser().absolute()
        if not path.exists():
            raise FileNotFoundError(str(path))
        handler = _objc.send(
            handler, "initWithURL:options:", _objc.file_url(path), options, argtypes=(_objc.id, _objc.id)
        )
    return _objc.send(handler, "autorelease")


def _request(languages: Optional[Sequence[str]], fast: bool) -> int:
    request = _objc.send(_objc.send(_objc.cls("VNRecognizeTextRequest"), "alloc"), "init")
    request = _objc.send(request, "autorelease")
    _objc.send(request, "setRecognitionLevel:", _FAST if fast else _ACCURATE, argtypes=(NSInteger,), restype=None)
    _objc.send(request, "setUsesLanguageCorrection:", not fast, argtypes=(BOOL,), restype=None)
    if languages:
        codes = _objc.nsarray_of([_objc.nsstring(code) for code in languages])
        _objc.send(request, "setRecognitionLanguages:", codes, argtypes=(_objc.id,), restype=None)
    return request


def _perform(image: Image, request: int) -> List[int]:
    """Run a Vision request on an image and return its result observations (autoreleased)."""
    handler = _handler(image)
    error = ctypes.c_void_p()
    ok = _objc.send(
        handler,
        "performRequests:error:",
        _objc.nsarray_of([request]),
        ctypes.byref(error),
        argtypes=(_objc.id, ctypes.c_void_p),
        restype=BOOL,
    )
    if not ok:
        raise _error(error, "the image could not be read", prefix="the image could not be read: ")
    return list(_objc.nsarray(_objc.send(request, "results")))


def _box(observation: int) -> Tuple[float, float, float, float]:
    box = _objc.send(observation, "boundingBox", restype=_objc.CGRect)
    # Vision measures from the bottom-left corner.
    return (box.origin.x, 1.0 - box.origin.y - box.size.height, box.size.width, box.size.height)


def _confidence(observation: int) -> float:
    return round(float(_objc.send(observation, "confidence", restype=ctypes.c_float)), 3)


def _error(error: ctypes.c_void_p, fallback: str, prefix: str = "") -> MacOSError:
    message = _objc.error_message(error)
    return MacOSError(prefix + message if message else fallback)


def lines(image: Image, *, languages: Optional[Sequence[str]] = None, fast: bool = False) -> List[TextLine]:
    """
    Find the lines of text in an image, top to bottom.

    ``image`` is a path or the image file's bytes, in any format macOS can
    open (PNG, JPEG, HEIC, TIFF, PDF...). ``languages`` lists the languages to
    expect, most likely first (e.g. ``["pt-BR", "en-US"]``; see
    :func:`languages`); by default Vision detects them. ``fast=True`` trades
    accuracy for speed.
    """
    _load()
    found: List[Any] = []
    with _objc.autorelease_pool():
        for observation in _perform(image, _request(languages, fast)):
            candidates = _objc.send(observation, "topCandidates:", 1, argtypes=(NSUInteger,))
            for candidate in _objc.nsarray(candidates):
                found.append(
                    TextLine(
                        text=_objc.pystring(_objc.send(candidate, "string")) or "",
                        confidence=_confidence(candidate),
                        box=_box(observation),
                    )
                )
    # Vision returns lines in detection order: sort them top to bottom (then
    # left to right), as the docs promise.
    return sorted(found, key=lambda line: (round(line.box[1], 2), line.box[0]))


def text(image: Image, *, languages: Optional[Sequence[str]] = None, fast: bool = False) -> str:
    """Return all the text in an image, one line per line found (see :func:`lines`)."""
    return "\n".join(line.text for line in lines(image, languages=languages, fast=fast))


def languages(*, fast: bool = False) -> List[str]:
    """The language codes that text recognition supports, e.g. ``['en-US', 'pt-BR', ...]`` (macOS 12+)."""
    _load()
    with _objc.autorelease_pool():
        request = _request(None, fast)
        error = ctypes.c_void_p()
        codes = _objc.send(
            request, "supportedRecognitionLanguagesAndReturnError:", ctypes.byref(error), argtypes=(ctypes.c_void_p,)
        )
        if not codes:
            raise _error(error, "the supported languages could not be read")
        return [code for code in (_objc.pystring(item) for item in _objc.nsarray(codes)) if code]


def barcodes(image: Image) -> List[Barcode]:
    """
    Find QR codes and barcodes (EAN, UPC, Code 128, PDF417, Aztec, Data Matrix...) in an image.

    ::

        [code.payload for code in macos.vision.barcodes("poster.jpg")]   # ['https://...']
    """
    _load()
    found = []
    with _objc.autorelease_pool():
        for observation in _perform(image, _objc.new("VNDetectBarcodesRequest")):
            kind = _objc.pystring(_objc.send(observation, "symbology")) or ""
            found.append(
                Barcode(
                    payload=_objc.pystring(_objc.send(observation, "payloadStringValue")),
                    kind=kind.replace("VNBarcodeSymbology", ""),
                    box=_box(observation),
                )
            )
    return found


def classify(image: Image, *, limit: int = 5, min_confidence: float = 0.1) -> List[Tuple[str, float]]:
    """
    Say what an image shows, as ``(label, confidence)`` pairs, most likely first.

    ::

        macos.vision.classify("holiday.jpg")   # [('beach', 0.91), ('sky', 0.87), ('ocean', 0.74)]

    Labels are English words from Vision's own taxonomy (over a thousand
    categories, such as ``'dog'``, ``'food'`` or ``'document'``).
    """
    if limit <= 0:
        raise ValueError("limit must be positive, not {}".format(limit))
    _load()
    with _objc.autorelease_pool():
        observations = _perform(image, _objc.new("VNClassifyImageRequest"))
        labels = [
            (_objc.pystring(_objc.send(observation, "identifier")) or "", _confidence(observation))
            for observation in observations
        ]
    ranked = sorted((pair for pair in labels if pair[1] >= min_confidence), key=lambda pair: -pair[1])
    return ranked[:limit]


def faces(image: Image) -> List[Tuple[float, float, float, float]]:
    """
    Find faces in an image, as ``(x, y, width, height)`` boxes (fractions of the image, from the top-left).

    It locates faces; it doesn't tell who they are.
    """
    _load()
    with _objc.autorelease_pool():
        return [_box(observation) for observation in _perform(image, _objc.new("VNDetectFaceRectanglesRequest"))]
