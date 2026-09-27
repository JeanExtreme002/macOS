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
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple, Union

from . import _cf, _objc
from ._system import framework
from .errors import MacOSError

__all__ = ["info", "convert", "resize", "qr_code", "ImageInfo"]

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


def _write(target: Path, kind: str, add: Callable[[int], None]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    io = _io()
    with _cf.owned(_cf.file_url(str(target))) as url, _cf.owned(_cf.string(kind)) as type_ref:
        destination = io.CGImageDestinationCreateWithURL(url, type_ref, 1, None)
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


def info(path: PathLike) -> ImageInfo:
    """Return the size, format, transparency, orientation and DPI of an image file."""
    io = _io()
    with _cf.owned(_source(path)) as source:
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


def convert(source: PathLike, output: PathLike, *, quality: Optional[float] = None) -> Path:
    """
    Convert an image to the format of ``output``'s extension, and return ``output``.

    Writes ``.jpg``, ``.png``, ``.heic``, ``.tiff``, ``.gif`` and ``.bmp``;
    reads anything macOS opens. Metadata such as the orientation, camera and
    date is kept. ``quality`` (0.0 to 1.0) applies to JPEG and HEIC.
    """
    target, kind = _output(output)
    if quality is not None and not 0.0 <= quality <= 1.0:
        raise ValueError("quality must be from 0.0 to 1.0, not {}".format(quality))
    io = _io()
    with _cf.owned(_source(source)) as image_source:
        options = _options({"kCGImageDestinationLossyCompressionQuality": quality}) if quality is not None else None
        with _cf.owned(options):
            return _write(
                target, kind, lambda destination: io.CGImageDestinationAddImageFromSource(destination, image_source, 0, options)
            )


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
    EXIF orientation. Images are only scaled down: a larger size keeps the
    original size.
    """
    for label, value in (("width", width), ("height", height)):
        if value is not None and value <= 0:
            raise ValueError("{} must be positive, not {}".format(label, value))
    if width is None and height is None:
        raise ValueError("resize() needs a width, a height or both")
    target, kind = _output(output)

    current = info(source)
    upright_width, upright_height = current.width, current.height
    if current.orientation in (5, 6, 7, 8):  # rotated a quarter turn
        upright_width, upright_height = upright_height, upright_width
    scale = min(
        (width / upright_width) if width else 1.0,
        (height / upright_height) if height else 1.0,
        1.0,
    )
    longest = max(1, round(max(upright_width, upright_height) * scale))

    io = _io()
    with _cf.owned(_source(source)) as image_source:
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
        with _cf.owned(scaled):
            save = _options({"kCGImageDestinationLossyCompressionQuality": quality}) if quality is not None else None
            with _cf.owned(save):
                return _write(
                    target, kind, lambda destination: io.CGImageDestinationAddImage(destination, scaled, save)
                )


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
        context = _objc.send(_objc.cls("CIContext"), "contextWithOptions:", None, argtypes=(_objc.id,))
        bounds = _objc.send(scaled, "extent", restype=_objc.CGRect)
        rendered = _objc.send(
            context, "createCGImage:fromRect:", scaled, bounds, argtypes=(_objc.id, _objc.CGRect), restype=ctypes.c_void_p
        )
        if not rendered:
            raise MacOSError("the QR code could not be drawn")
        try:
            rep = _objc.send(_objc.cls("NSBitmapImageRep"), "alloc")
            rep = _objc.send(rep, "initWithCGImage:", rendered, argtypes=(ctypes.c_void_p,))
            _objc.send(rep, "autorelease")
            return _objc.png(rep)
        finally:
            _cf.release(rendered)
