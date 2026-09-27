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

__all__ = ["text", "lines", "languages", "TextLine"]

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
        handler = _handler(image)
        request = _request(languages, fast)
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

        for observation in _objc.nsarray(_objc.send(request, "results")):
            candidates = _objc.send(observation, "topCandidates:", 1, argtypes=(NSUInteger,))
            for candidate in _objc.nsarray(candidates):
                box = _objc.send(observation, "boundingBox", restype=_objc.CGRect)
                found.append(
                    TextLine(
                        text=_objc.pystring(_objc.send(candidate, "string")) or "",
                        confidence=round(float(_objc.send(candidate, "confidence", restype=ctypes.c_float)), 3),
                        # Vision measures from the bottom-left corner.
                        box=(
                            box.origin.x,
                            1.0 - box.origin.y - box.size.height,
                            box.size.width,
                            box.size.height,
                        ),
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
