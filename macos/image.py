# -*- coding: utf-8 -*-

"""
Read, convert and resize images, HEIC included.

::

    macos.image.info("IMG_0042.heic")          # ImageInfo(width=4032, height=3024, format='heic', ...)
    macos.image.convert("IMG_0042.heic", "IMG_0042.jpg")
    macos.image.resize("photo.jpg", "small.jpg", width=800)

Uses ImageIO, the framework Preview and Photos use, so every format macOS can
open is supported, iPhone photos (HEIC) and WebP included, with no Pillow or C
library to install.
"""

import ctypes
import os
from datetime import datetime
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

from . import _cf, _objc
from ._system import framework
from .errors import MacOSError

__all__ = [
    "info",
    "metadata",
    "taken_at",
    "location",
    "strip_metadata",
    "convert",
    "resize",
    "qr_code",
    "ImageInfo",
]

PathLike = Union[str, "os.PathLike[str]"]

# What each output extension is written as. Reading supports more (WebP,
# AVIF, RAW photos...): ImageIO can open them but not write them.
_WRITE_TYPES = {
    ".jpg": "public.jpeg",
    ".jpeg": "public.jpeg",
    ".png": "public.png",
    ".heic": "public.heic",
    ".tiff": "public.tiff",
    ".tif": "public.tiff",
    ".gif": "com.compuserve.gif",
    ".bmp": "com.microsoft.bmp",
}

# The output formats that hold several images (animation frames, pages).
_MULTI_FRAME = {"com.compuserve.gif", "public.tiff"}

# Short names for the type identifiers ImageIO reports.
_FORMAT_NAMES = {
    "public.jpeg": "jpeg",
    "public.png": "png",
    "public.heic": "heic",
    "public.heif": "heif",
    "public.tiff": "tiff",
    "com.compuserve.gif": "gif",
    "com.microsoft.bmp": "bmp",
    "org.webmproject.webp": "webp",
    "public.avif": "avif",
    "com.adobe.pdf": "pdf",
}


@dataclass(frozen=True)
class ImageInfo:
    """What an image file contains."""

    width: int
    """In pixels, as stored (before applying ``orientation``)."""
    height: int
    format: str
    """A short name such as ``'jpeg'``, ``'png'`` or ``'heic'``, or the type identifier for others."""
    has_alpha: bool
    """Whether it has transparency."""
    orientation: int
    """The EXIF orientation, 1 to 8. 1 is upright; 6 and 8 are rotated 90°, as for portrait photos."""
    dpi: Optional[float]
    """Dots per inch, when the file records it."""


@lru_cache(maxsize=None)
def _io() -> ctypes.CDLL:
    io = framework("ImageIO")
    pointer = ctypes.c_void_p
    signatures = {
        "CGImageSourceCreateWithURL": ((pointer, pointer), pointer),
        "CGImageSourceGetType": ((pointer,), pointer),
        "CGImageSourceGetCount": ((pointer,), ctypes.c_size_t),
        "CGImageSourceCopyPropertiesAtIndex": ((pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageSourceCreateThumbnailAtIndex": ((pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageSourceCreateImageAtIndex": ((pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageDestinationCreateWithURL": ((pointer, pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageDestinationAddImageFromSource": ((pointer, pointer, ctypes.c_size_t, pointer), None),
        "CGImageDestinationAddImage": ((pointer, pointer, pointer), None),
        "CGImageDestinationFinalize": ((pointer,), ctypes.c_bool),
    }
    for name, (argtypes, restype) in signatures.items():
        function = getattr(io, name)
        function.argtypes = argtypes
        function.restype = restype
    return io


def _source(path: PathLike) -> int:
    """An owned ``CGImageSource`` for ``path``."""
    resolved = Path(path).expanduser().absolute()
    if not resolved.exists():
        raise FileNotFoundError(str(resolved))
    with _cf.owned(_cf.file_url(str(resolved))) as url:
        source = _io().CGImageSourceCreateWithURL(url, None)
    if not source or not _io().CGImageSourceGetCount(source):
        _cf.release(source)
        raise ValueError("{} is not an image macOS can read".format(resolved))
    return source


def _output(path: PathLike) -> Tuple[Path, str]:
    target = Path(path).expanduser().absolute()
    kind = _WRITE_TYPES.get(target.suffix.lower())
    if kind is None:
        raise ValueError(
            "can't write {!r} images; use one of {}".format(target.suffix, ", ".join(sorted(_WRITE_TYPES)))
        )
    return target, kind


def _options(values: Dict[str, Union[bool, float]]) -> int:
    """An owned ``CFDictionary`` of ImageIO options, keyed by constant name."""
    io = _io()
    cf = _cf.lib()
    true, false = _cf.constant(cf, "kCFBooleanTrue"), _cf.constant(cf, "kCFBooleanFalse")
    owned = []
    items = {}
    try:
        for key, value in values.items():
            if isinstance(value, bool):
                ref = true if value else false
            else:
                ref = _cf.number(value)
                owned.append(ref)
            items[_cf.constant(io, key)] = ref
        return _cf.dictionary(items)
    finally:
        for ref in owned:
            _cf.release(ref)


def _write(target: Path, kind: str, add: Callable[[int], None], frames: int = 1) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    io = _io()
    with _cf.owned(_cf.file_url(str(target))) as url, _cf.owned(_cf.string(kind)) as type_ref:
        destination = io.CGImageDestinationCreateWithURL(url, type_ref, frames, None)
    if not destination:
        raise MacOSError("could not create {}".format(target))
    try:
        add(destination)
        if not io.CGImageDestinationFinalize(destination):
            raise MacOSError("could not write {}".format(target))
    finally:
        _cf.release(destination)
    return target


def _number(properties: Optional[int], key: str) -> Optional[float]:
    """A numeric image property, integer or not."""
    value = _cf.lookup(properties, key)
    if not value:
        return None
    cf = _cf.lib()
    real = ctypes.c_double()
    if not _cf.is_type(value, cf.CFNumberGetTypeID()):
        return None
    cf.CFNumberGetValue(value, _cf.kCFNumberDoubleType, ctypes.byref(real))
    return real.value


def _metadata(source: Optional[int], quality: Optional[float]) -> Optional[int]:
    """
    The source's metadata (date, camera, GPS, DPI...) for the resized copy, owned.

    Its pixels are already upright, so the orientation becomes 1 (upright).
    """
    io = _io()
    cf = _cf.lib()
    with _cf.owned(io.CGImageSourceCopyPropertiesAtIndex(source, 0, None)) as properties:
        if not properties:
            return _options({"kCGImageDestinationLossyCompressionQuality": quality}) if quality is not None else None
        copy = cf.CFDictionaryCreateMutableCopy(None, 0, properties)
    with _cf.owned(_cf.number(1)) as upright:
        cf.CFDictionarySetValue(copy, _cf.constant(io, "kCGImagePropertyOrientation"), upright)
    if quality is not None:
        with _cf.owned(_cf.number(float(quality))) as value:
            cf.CFDictionarySetValue(copy, _cf.constant(io, "kCGImageDestinationLossyCompressionQuality"), value)
    return copy


def _describe(source: Optional[int]) -> ImageInfo:
    io = _io()
    with _cf.owned(io.CGImageSourceCopyPropertiesAtIndex(source, 0, None)) as properties:
        kind = _cf.to_str(io.CGImageSourceGetType(source)) or ""
        return ImageInfo(
            width=int(_number(properties, "PixelWidth") or 0),
            height=int(_number(properties, "PixelHeight") or 0),
            format=_FORMAT_NAMES.get(kind, kind),
            has_alpha=_cf.to_bool(_cf.lookup(properties, "HasAlpha")),
            orientation=int(_number(properties, "Orientation") or 1),
            dpi=_number(properties, "DPIWidth"),
        )


def info(path: PathLike) -> ImageInfo:
    """Return the size, format, transparency, orientation and DPI of an image file."""
    with _cf.owned(_source(path)) as source:
        return _describe(source)


def metadata(path: PathLike) -> Dict[str, Any]:
    """
    Return all the metadata of an image file as a dict, as ImageIO reports it.

    Top-level keys include ``PixelWidth``, ``Orientation`` and ``DPIWidth``;
    nested dicts hold the standards, such as ``"{Exif}"`` (date, exposure,
    lens), ``"{TIFF}"`` (camera ``Make`` and ``Model``) and ``"{GPS}"``
    (location). For the common questions, see :func:`taken_at` and
    :func:`location`.
    """
    with _cf.owned(_source(path)) as source:
        with _cf.owned(_io().CGImageSourceCopyPropertiesAtIndex(source, 0, None)) as properties:
            return dict(_cf.to_python(properties) or {})


def taken_at(path: PathLike) -> Optional[datetime]:
    """When the photo was taken, from its EXIF data, or ``None`` if it doesn't say (local time, no time zone)."""
    data = metadata(path)
    exif, tiff = data.get("{Exif}", {}), data.get("{TIFF}", {})
    for value in (exif.get("DateTimeOriginal"), exif.get("DateTimeDigitized"), tiff.get("DateTime")):
        if isinstance(value, str):
            try:
                return datetime.strptime(value.strip(), "%Y:%m:%d %H:%M:%S")
            except ValueError:
                continue
    return None


def location(path: PathLike) -> Optional[Tuple[float, float]]:
    """
    Where the photo was taken, as ``(latitude, longitude)`` in degrees, or ``None`` if it has no GPS data.

    South latitudes and west longitudes are negative, as maps expect::

        lat, lon = macos.image.location("IMG_0042.heic")
        macos.open("https://maps.apple.com/?ll={},{}".format(lat, lon))
    """
    gps = metadata(path).get("{GPS}", {})
    latitude, longitude = gps.get("Latitude"), gps.get("Longitude")
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return None
    if str(gps.get("LatitudeRef", "N")).upper() == "S":
        latitude = -latitude
    if str(gps.get("LongitudeRef", "E")).upper() == "W":
        longitude = -longitude
    return (float(latitude), float(longitude))


def strip_metadata(source: PathLike, output: PathLike) -> Path:
    """
    Save a copy of an image without its metadata (location, date, camera, editing software...).

    Use it before sharing photos: iPhone pictures record where they were
    taken. Only the orientation is kept, so the picture still shows upright.
    ``output``'s extension sets the format.
    """
    target, kind = _output(output)
    io = _io()
    with _cf.owned(_source(source)) as image_source:
        orientation = _describe(image_source).orientation
        pixels = io.CGImageSourceCreateImageAtIndex(image_source, 0, None)
    if not pixels:
        raise MacOSError("could not read {}".format(source))
    value = _cf.number(orientation)
    with _cf.owned(pixels), _cf.owned(value):
        keep = _cf.dictionary({_cf.constant(io, "kCGImagePropertyOrientation"): value})
        with _cf.owned(keep):
            return _write(target, kind, lambda destination: io.CGImageDestinationAddImage(destination, pixels, keep))


def convert(source: PathLike, output: PathLike, *, quality: Optional[float] = None) -> Path:
    """
    Convert an image to the format of ``output``'s extension, and return ``output``.

    Writes ``.jpg``, ``.png``, ``.heic``, ``.tiff``, ``.gif`` and ``.bmp``;
    reads anything macOS opens. Metadata such as the orientation, camera and
    date is kept. ``quality`` (0.0 to 1.0) applies to JPEG and HEIC.

    Animated GIFs and multi-page TIFFs keep every frame when converted to GIF
    or TIFF; the other formats hold a single image and get the first one.
    """
    target, kind = _output(output)
    if quality is not None and not 0.0 <= quality <= 1.0:
        raise ValueError("quality must be from 0.0 to 1.0, not {}".format(quality))
    io = _io()
    with _cf.owned(_source(source)) as image_source:
        frames = io.CGImageSourceGetCount(image_source) if kind in _MULTI_FRAME else 1
        options = _options({"kCGImageDestinationLossyCompressionQuality": quality}) if quality is not None else None

        def add(destination: int) -> None:
            for index in range(frames):
                io.CGImageDestinationAddImageFromSource(destination, image_source, index, options)

        with _cf.owned(options):
            return _write(target, kind, add, frames)


def resize(
    source: PathLike,
    output: PathLike,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    quality: Optional[float] = None,
) -> Path:
    """
    Scale an image to fit ``width`` and/or ``height`` (in pixels), keeping its proportions.

    The result is saved to ``output`` (its extension sets the format) and
    ``output`` is returned. Photos are turned upright first, following their
    EXIF orientation, and their metadata (date, camera, location...) is kept.
    Images are only scaled down: a larger size keeps the original size.
    """
    for label, value in (("width", width), ("height", height)):
        if value is not None and value <= 0:
            raise ValueError("{} must be positive, not {}".format(label, value))
    if width is None and height is None:
        raise ValueError("resize() needs a width, a height or both")
    target, kind = _output(output)
    if quality is not None and not 0.0 <= quality <= 1.0:
        raise ValueError("quality must be from 0.0 to 1.0, not {}".format(quality))

    io = _io()
    with _cf.owned(_source(source)) as image_source:
        current = _describe(image_source)
        if not current.width or not current.height:
            raise ValueError("{} doesn't report its size".format(source))
        upright_width, upright_height = current.width, current.height
        if current.orientation in (5, 6, 7, 8):  # rotated a quarter turn
            upright_width, upright_height = upright_height, upright_width
        scale = min(
            (width / upright_width) if width else 1.0,
            (height / upright_height) if height else 1.0,
            1.0,
        )
        longest = max(1, round(max(upright_width, upright_height) * scale))

        options = _options(
            {
                "kCGImageSourceCreateThumbnailFromImageAlways": True,
                "kCGImageSourceCreateThumbnailWithTransform": True,  # apply the EXIF orientation
                "kCGImageSourceThumbnailMaxPixelSize": longest,
            }
        )
        with _cf.owned(options):
            scaled = io.CGImageSourceCreateThumbnailAtIndex(image_source, 0, options)
        if not scaled:
            raise MacOSError("could not scale {}".format(source))
        with _cf.owned(scaled), _cf.owned(_metadata(image_source, quality)) as save:
            return _write(target, kind, lambda destination: io.CGImageDestinationAddImage(destination, scaled, save))


class _CGAffineTransform(ctypes.Structure):
    _fields_ = [(name, ctypes.c_double) for name in ("a", "b", "c", "d", "tx", "ty")]


_CORRECTION_LEVELS = {"L", "M", "Q", "H"}


def qr_code(content: str, *, size: int = 512, correction: str = "M") -> bytes:
    """
    Generate a QR code for ``content`` (a URL, some text...) and return it as PNG bytes.

    ``size`` is the side in pixels (up to 4096). ``correction`` is the error
    correction level, ``"L"``, ``"M"``, ``"Q"`` or ``"H"``: higher levels
    survive more damage but hold less data::

        Path("site.png").write_bytes(macos.image.qr_code("https://python.org"))
    """
    if not 0 < size <= 4096:
        raise ValueError("size must be from 1 to 4096, not {}".format(size))
    if correction not in _CORRECTION_LEVELS:
        raise ValueError("correction must be one of L, M, Q, H, not {!r}".format(correction))
    framework("AppKit")
    framework("CoreImage")
    with _objc.autorelease_pool():
        qr = _objc.send(
            _objc.cls("CIFilter"), "filterWithName:", _objc.nsstring("CIQRCodeGenerator"), argtypes=(_objc.id,)
        )
        _objc.send(
            qr, "setValue:forKey:", _objc.nsdata(content.encode("utf-8")), _objc.nsstring("inputMessage"),
            argtypes=(_objc.id, _objc.id), restype=None,
        )
        _objc.send(
            qr, "setValue:forKey:", _objc.nsstring(correction), _objc.nsstring("inputCorrectionLevel"),
            argtypes=(_objc.id, _objc.id), restype=None,
        )
        code = _objc.send(qr, "valueForKey:", _objc.nsstring("outputImage"), argtypes=(_objc.id,))
        if not code:
            raise ValueError("the content is too long for a QR code")

        # The generator makes one pixel per module: scale it up, without
        # smoothing, to the requested size.
        extent = _objc.send(code, "extent", restype=_objc.CGRect)
        scale = size / extent.size.width
        scaled = _objc.send(
            code,
            "imageByApplyingTransform:",
            _CGAffineTransform(scale, 0, 0, scale, 0, 0),
            argtypes=(_CGAffineTransform,),
        )
        return _objc.ciimage_png(scaled)
