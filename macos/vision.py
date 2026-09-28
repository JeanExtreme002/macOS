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
from .errors import MacOSError, NotSupportedError

__all__ = [
    "text",
    "lines",
    "languages",
    "barcodes",
    "classify",
    "faces",
    "animals",
    "remove_background",
    "scan_document",
    "image_distance",
    "duplicates",
    "smart_crop",
    "TextLine",
    "Barcode",
    "Animal",
]

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


@dataclass(frozen=True)
class Animal:
    """A cat or dog found in an image."""

    kind: str
    """``'cat'`` or ``'dog'``."""
    confidence: float
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


def animals(image: Image) -> List[Animal]:
    """Find cats and dogs in an image. (Those are the only animals Vision recognizes.)"""
    _load()
    found = []
    with _objc.autorelease_pool():
        for observation in _perform(image, _objc.new("VNRecognizeAnimalsRequest")):
            for label in _objc.nsarray(_objc.send(observation, "labels")):
                found.append(
                    Animal(
                        kind=(_objc.pystring(_objc.send(label, "identifier")) or "").lower(),
                        confidence=_confidence(label),
                        box=_box(observation),
                    )
                )
    return found


def remove_background(image: Image, *, crop: bool = False) -> Optional[bytes]:
    """
    Cut out the subject of a photo (a person, an animal, an object) and return it as a PNG with a transparent background.

    It's the "lift subject from background" of Photos and Preview. ``crop=True``
    trims the result to the subject; by default it keeps the image's size.
    Returns ``None`` when no subject stands out. Needs macOS 14 or later::

        Path("cutout.png").write_bytes(macos.vision.remove_background("dog.jpg"))
    """
    _load()
    framework("AppKit")
    framework("CoreImage")
    with _objc.autorelease_pool():
        handler = _handler(image)
        try:
            request = _objc.new("VNGenerateForegroundInstanceMaskRequest")
        except LookupError:
            raise NotSupportedError("removing backgrounds needs macOS 14 or later") from None
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
        results = list(_objc.nsarray(_objc.send(request, "results")))
        if not results:
            return None
        observation = results[0]
        instances = _objc.send(observation, "allInstances")
        if not instances or not _objc.send(instances, "count", restype=NSUInteger):
            return None

        buffer = _objc.send(
            observation,
            "generateMaskedImageOfInstances:fromRequestHandler:croppedToInstancesExtent:error:",
            instances,
            handler,
            crop,
            ctypes.byref(error),
            argtypes=(_objc.id, _objc.id, BOOL, ctypes.c_void_p),
            restype=ctypes.c_void_p,
        )
        if not buffer:
            raise _error(error, "the background could not be removed")

        # Pixel buffer -> Core Image -> PNG.
        picture = _objc.send(_objc.cls("CIImage"), "imageWithCVPixelBuffer:", buffer, argtypes=(ctypes.c_void_p,))
        return _objc.ciimage_png(picture)


def _upright(image: Image) -> int:
    """A ``CIImage`` of ``image`` with its EXIF orientation applied (autoreleased)."""
    framework("AppKit")
    framework("CoreImage")
    options = _objc.send(
        _objc.cls("NSDictionary"),
        "dictionaryWithObject:forKey:",
        _objc.send(_objc.cls("NSNumber"), "numberWithBool:", True, argtypes=(BOOL,)),
        _objc.nsstring("kCIImageApplyOrientationProperty"),
        argtypes=(_objc.id, _objc.id),
    )
    if isinstance(image, (bytes, bytearray)):
        picture = _objc.send(
            _objc.cls("CIImage"), "imageWithData:options:", _objc.nsdata(bytes(image)), options, argtypes=(_objc.id, _objc.id)
        )
    else:
        path = Path(image).expanduser().absolute()
        if not path.exists():
            raise FileNotFoundError(str(path))
        picture = _objc.send(
            _objc.cls("CIImage"), "imageWithContentsOfURL:options:", _objc.file_url(path), options, argtypes=(_objc.id, _objc.id)
        )
    if not picture:
        raise MacOSError("the image could not be read")
    return picture


def scan_document(image: Image) -> Optional[bytes]:
    """
    Turn a photo of a document (a page, a receipt, a card) into a flat, straight scan, as PNG bytes.

    Finds the document's edges, crops the rest of the photo away and corrects
    the perspective, like the scanner in Notes. Returns ``None`` when no
    document is found::

        scan = macos.vision.scan_document("receipt_photo.jpg")
        macos.vision.text(scan)                          # read it
        macos.pdf.from_images([scan], "receipt.pdf")     # or file it
    """
    _load()
    with _objc.autorelease_pool():
        picture = _upright(image)
        extent = _objc.send(picture, "extent", restype=_objc.CGRect)
        width, height = extent.size.width, extent.size.height

        # Detect on the upright pixels, so the corners match `picture`.
        png = _objc.ciimage_png(picture)
        request = _objc.new("VNDetectDocumentSegmentationRequest")
        observations = _perform(png, request)
        # The detector always returns a quadrilateral; on anything but a
        # document its confidence is 0 (measured: 0.99 for a photographed page).
        if not observations or _objc.send(observations[0], "confidence", restype=ctypes.c_float) < 0.5:
            return None
        document = observations[0]

        correction = _objc.send(
            _objc.cls("CIFilter"), "filterWithName:", _objc.nsstring("CIPerspectiveCorrection"), argtypes=(_objc.id,)
        )
        _objc.send(
            correction, "setValue:forKey:", picture, _objc.nsstring("inputImage"), argtypes=(_objc.id, _objc.id), restype=None
        )
        for corner, key in (
            ("topLeft", "inputTopLeft"),
            ("topRight", "inputTopRight"),
            ("bottomLeft", "inputBottomLeft"),
            ("bottomRight", "inputBottomRight"),
        ):
            # Vision and Core Image both measure from the bottom-left corner;
            # Vision in fractions, Core Image in pixels.
            point = _objc.send(document, corner, restype=_objc.CGPoint)
            vector = _objc.send(
                _objc.cls("CIVector"),
                "vectorWithX:Y:",
                point.x * width,
                point.y * height,
                argtypes=(ctypes.c_double, ctypes.c_double),
            )
            _objc.send(correction, "setValue:forKey:", vector, _objc.nsstring(key), argtypes=(_objc.id, _objc.id), restype=None)
        flat = _objc.send(correction, "valueForKey:", _objc.nsstring("outputImage"), argtypes=(_objc.id,))
        if not flat:
            raise MacOSError("the perspective could not be corrected")
        return _objc.ciimage_png(flat)


def _feature_print(image: Image) -> int:
    """A retained ``VNFeaturePrintObservation`` (+1) for ``image``."""
    with _objc.autorelease_pool():
        observations = _perform(image, _objc.new("VNGenerateImageFeaturePrintRequest"))
        if not observations:
            raise MacOSError("no feature print for this image")
        return _objc.send(observations[0], "retain")


def _distance(first: int, second: int) -> float:
    value = ctypes.c_float()
    error = ctypes.c_void_p()
    ok = _objc.send(
        first,
        "computeDistance:toFeaturePrintObservation:error:",
        ctypes.byref(value),
        second,
        ctypes.byref(error),
        argtypes=(ctypes.c_void_p, _objc.id, ctypes.c_void_p),
        restype=BOOL,
    )
    if not ok:
        raise _error(error, "the images could not be compared")
    return round(float(value.value), 4)


def image_distance(first: Image, second: Image) -> float:
    """
    How different two images look: 0.0 for the same picture, growing as they differ.

    Measured on photos, a resized or re-compressed copy scores below 0.15 and
    unrelated photos around 0.7 to 0.9. Very small images (a few hundred
    pixels) score less reliably. See :func:`duplicates` to group a whole folder.
    """
    _load()
    one, two = _feature_print(first), _feature_print(second)
    try:
        return _distance(one, two)
    finally:
        _objc.send(one, "release", restype=None)
        _objc.send(two, "release", restype=None)


def duplicates(images: Sequence[Image], *, threshold: float = 0.3) -> List[List[Image]]:
    """
    Group images that look like the same picture: copies, resized or re-saved versions, burst shots.

    Returns only the groups with two or more images, each in the order given.
    Two images are grouped when their :func:`image_distance` is below
    ``threshold``; raise it to also group similar (not identical) shots::

        from pathlib import Path

        photos = sorted(Path("~/Pictures/Trip").expanduser().glob("*.jpg"))
        for group in macos.vision.duplicates(photos):
            print("Same picture:", [photo.name for photo in group])

    Every image is compared with every other, so thousands of images take a while.
    """
    if threshold <= 0:
        raise ValueError("threshold must be positive, not {}".format(threshold))
    _load()
    prints: List[int] = []
    try:
        for image in images:
            prints.append(_feature_print(image))
        parent = list(range(len(images)))

        def root(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        for first in range(len(images)):
            for second in range(first + 1, len(images)):
                if _distance(prints[first], prints[second]) < threshold:
                    parent[root(second)] = root(first)
    finally:
        for observation in prints:
            _objc.send(observation, "release", restype=None)

    groups: dict = {}
    for index, image in enumerate(images):
        groups.setdefault(root(index), []).append(image)
    return [group for group in groups.values() if len(group) > 1]


class _CGAffineTransform(ctypes.Structure):
    _fields_ = [(name, ctypes.c_double) for name in ("a", "b", "c", "d", "tx", "ty")]


def smart_crop(image: Image, width: int, height: int) -> bytes:
    """
    Crop and scale an image to ``width`` x ``height`` pixels, keeping its most interesting part.

    Vision finds where the eye goes (a face, an animal, the main object) and the
    crop is centred there, instead of on the middle of the picture. Useful for
    thumbnails and avatars::

        Path("thumb.png").write_bytes(macos.vision.smart_crop("portrait.jpg", 300, 300))

    The image is never scaled up: when the crop is smaller than ``width`` x
    ``height``, the result keeps the crop's own size, with the same proportions.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive, not {} x {}".format(width, height))
    _load()
    with _objc.autorelease_pool():
        picture = _upright(image)
        extent = _objc.send(picture, "extent", restype=_objc.CGRect)
        full_width, full_height = extent.size.width, extent.size.height

        # Where to centre the crop: the salient objects' bounding box, or the
        # middle of the picture when nothing stands out.
        center_x, center_y = 0.5, 0.5
        observations = _perform(_objc.ciimage_png(picture), _objc.new("VNGenerateAttentionBasedSaliencyImageRequest"))
        if observations:
            boxes = [
                _objc.send(item, "boundingBox", restype=_objc.CGRect)
                for item in _objc.nsarray(_objc.send(observations[0], "salientObjects"))
            ]
            if boxes:
                left = min(box.origin.x for box in boxes)
                right = max(box.origin.x + box.size.width for box in boxes)
                bottom = min(box.origin.y for box in boxes)
                top = max(box.origin.y + box.size.height for box in boxes)
                center_x, center_y = (left + right) / 2, (bottom + top) / 2

        # The largest crop with the requested proportions that fits the image.
        ratio = width / height
        crop_width = min(full_width, full_height * ratio)
        crop_height = crop_width / ratio
        x = min(max(center_x * full_width - crop_width / 2, 0.0), full_width - crop_width)
        y = min(max(center_y * full_height - crop_height / 2, 0.0), full_height - crop_height)
        rect = _objc.CGRect(_objc.CGPoint(extent.origin.x + x, extent.origin.y + y), _objc.CGSize(crop_width, crop_height))
        cropped = _objc.send(picture, "imageByCroppingToRect:", rect, argtypes=(_objc.CGRect,))

        scale = min(width / crop_width, 1.0)
        # Move the crop to the origin, then scale it.
        moved = _objc.send(
            cropped,
            "imageByApplyingTransform:",
            _CGAffineTransform(scale, 0, 0, scale, -rect.origin.x * scale, -rect.origin.y * scale),
            argtypes=(_CGAffineTransform,),
        )
        return _objc.ciimage_png(moved)
