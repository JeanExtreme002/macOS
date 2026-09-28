# -*- coding: utf-8 -*-

"""
Read, convert, resize and edit images, HEIC included, and their metadata.

::

    macos.image.info("IMG_0042.heic")          # ImageInfo(width=4032, height=3024, format='heic', ...)
    macos.image.convert("IMG_0042.heic", "IMG_0042.jpg")
    macos.image.resize("photo.jpg", "small.jpg", width=800)
    macos.image.rotate("photo.jpg", "turned.jpg", 90)
    macos.image.location("IMG_0042.heic")      # (-22.9519, -43.2105)

Uses ImageIO, the framework Preview and Photos use, so every format macOS can
open is supported, iPhone photos (HEIC) and WebP included, with no Pillow or C
library to install.
"""

import ctypes
import math
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from . import _cf, _objc
from ._system import framework
from .errors import MacOSError

__all__ = [
    "info",
    "metadata",
    "taken_at",
    "location",
    "strip_metadata",
    "set_taken_at",
    "set_location",
    "convert",
    "resize",
    "crop",
    "rotate",
    "flip",
    "straighten",
    "blur_faces",
    "dominant_colors",
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
        "CGImageSourceCreateWithData": ((pointer, pointer), pointer),
        "CGImageSourceGetType": ((pointer,), pointer),
        "CGImageSourceGetCount": ((pointer,), ctypes.c_size_t),
        "CGImageSourceCopyPropertiesAtIndex": ((pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageSourceCreateThumbnailAtIndex": ((pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageSourceCreateImageAtIndex": ((pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageDestinationCreateWithURL": ((pointer, pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageDestinationAddImageFromSource": ((pointer, pointer, ctypes.c_size_t, pointer), None),
        "CGImageDestinationAddImage": ((pointer, pointer, pointer), None),
        "CGImageDestinationFinalize": ((pointer,), ctypes.c_bool),
        "CGImageDestinationCopyImageSource": ((pointer, pointer, pointer, pointer), ctypes.c_bool),
        "CGImageSourceCopyMetadataAtIndex": ((pointer, ctypes.c_size_t, pointer), pointer),
        "CGImageMetadataCreateMutableCopy": ((pointer,), pointer),
        "CGImageMetadataCreateMutable": ((), pointer),
        "CGImageMetadataSetValueMatchingImageProperty": ((pointer, pointer, pointer, pointer), ctypes.c_bool),
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


_EXIF_DATE = "%Y:%m:%d %H:%M:%S"


def _offset(text: Any) -> Optional[timezone]:
    """An EXIF time zone offset such as ``'-03:00'``."""
    if not isinstance(text, str) or len(text.strip()) != 6:
        return None
    try:
        sign = -1 if text.strip()[0] == "-" else 1
        hours, minutes = int(text.strip()[1:3]), int(text.strip()[4:6])
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    except ValueError:
        return None


def taken_at(path: PathLike) -> Optional[datetime]:
    """
    When the photo was taken, from its EXIF data, or ``None`` if it doesn't say.

    The date is the camera's clock. When the photo also records its time zone
    (iPhones do), the ``datetime`` carries it; otherwise it has no time zone.
    """
    data = metadata(path)
    exif, tiff = data.get("{Exif}", {}), data.get("{TIFF}", {})
    candidates = (
        (exif.get("DateTimeOriginal"), exif.get("OffsetTimeOriginal")),
        (exif.get("DateTimeDigitized"), exif.get("OffsetTimeDigitized")),
        (tiff.get("DateTime"), exif.get("OffsetTime")),
    )
    for value, offset in candidates:
        if isinstance(value, str):
            try:
                when = datetime.strptime(value.strip(), _EXIF_DATE)
            except ValueError:
                continue
            zone = _offset(offset)
            return when.replace(tzinfo=zone) if zone else when
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


def _matches(written: Dict[str, Any], changes: Dict[str, Dict[str, Any]]) -> bool:
    for group, values in changes.items():
        for key, value in values.items():
            found = written.get(group, {}).get(key)
            if isinstance(value, float):
                if not isinstance(found, (int, float)) or abs(found - value) > 1e-6:
                    return False
            elif found != value:
                return False
    return True


def _set_properties(path: PathLike, changes: Dict[str, Dict[str, Any]], output: Optional[PathLike]) -> Path:
    """
    Write ``changes`` (``{"{Exif}": {"DateTimeOriginal": ...}}``) into a copy of an image, or into the image itself.

    The metadata is rewritten without touching the pixels when the format
    allows it (JPEG, PNG, TIFF...). Otherwise, the image is saved again.
    """
    original = Path(path).expanduser().absolute()
    target = Path(output).expanduser().absolute() if output is not None else original
    io = _io()
    cf = _cf.lib()
    with _cf.owned(_source(original)) as image_source:
        kind = _cf.to_str(io.CGImageSourceGetType(image_source)) or "public.jpeg"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write next to the target and move it in place at the end, so a
        # failure never leaves a half-written photo behind.
        handle, name = tempfile.mkstemp(dir=str(target.parent), suffix=target.suffix or original.suffix)
        os.close(handle)
        temporary = Path(name)
        try:
            current = io.CGImageSourceCopyMetadataAtIndex(image_source, 0, None)
            tags = io.CGImageMetadataCreateMutableCopy(current) if current else io.CGImageMetadataCreateMutable()
            _cf.release(current)
            with _cf.owned(tags):
                for group, values in changes.items():
                    with _cf.owned(_cf.string(group)) as group_ref:
                        for key, value in values.items():
                            with _cf.owned(_cf.string(key)) as key_ref, _cf.owned(_cf.from_python(value)) as value_ref:
                                io.CGImageMetadataSetValueMatchingImageProperty(tags, group_ref, key_ref, value_ref)
                options = _cf.dictionary(
                    {
                        _cf.constant(io, "kCGImageDestinationMetadata"): tags,
                        _cf.constant(io, "kCGImageDestinationMergeMetadata"): _cf.constant(cf, "kCFBooleanTrue"),
                    }
                )
                with _cf.owned(options), _cf.owned(_cf.file_url(str(temporary))) as url, _cf.owned(
                    _cf.string(kind)
                ) as type_ref:
                    destination = io.CGImageDestinationCreateWithURL(url, type_ref, 1, None)
                    if not destination:
                        raise MacOSError("could not create {}".format(temporary))
                    with _cf.owned(destination):
                        copied = io.CGImageDestinationCopyImageSource(destination, image_source, options, None)
            # Some formats (HEIC) drop part of the changes when copied that
            # way: save the image again with them instead.
            if not copied or not _matches(metadata(temporary), changes):
                with _cf.owned(_cf.from_python(changes)) as properties:
                    _write(
                        temporary,
                        kind,
                        lambda destination: io.CGImageDestinationAddImageFromSource(
                            destination, image_source, 0, properties
                        ),
                    )
            os.replace(str(temporary), str(target))
        finally:
            if temporary.exists():
                temporary.unlink()
    return target


def set_taken_at(path: PathLike, when: datetime, *, output: Optional[PathLike] = None) -> Path:
    """
    Set when a photo was taken (its EXIF date), and return the path written.

    Changes ``path`` itself, or saves a changed copy to ``output``. Apps such
    as Photos sort by this date, so it fixes photos from a camera with the
    wrong clock::

        from datetime import timedelta

        for photo in Path("~/Pictures/Trip").expanduser().glob("*.jpg"):
            macos.image.set_taken_at(photo, macos.image.taken_at(photo) + timedelta(hours=3))

    When ``when`` has a time zone, it's recorded too. JPEG, PNG and TIFF keep
    their pixels untouched; other formats (HEIC) may be saved again.
    """
    stamp = when.strftime(_EXIF_DATE)
    exif: Dict[str, Any] = {"DateTimeOriginal": stamp, "DateTimeDigitized": stamp}
    offset = when.utcoffset()
    if offset is not None:
        minutes = int(offset.total_seconds() // 60)
        text = "{}{:02d}:{:02d}".format("-" if minutes < 0 else "+", abs(minutes) // 60, abs(minutes) % 60)
        exif.update(OffsetTimeOriginal=text, OffsetTimeDigitized=text)
    return _set_properties(path, {"{Exif}": exif}, output)


def set_location(path: PathLike, latitude: float, longitude: float, *, output: Optional[PathLike] = None) -> Path:
    """
    Set where a photo was taken (its GPS position, in degrees), and return the path written.

    Changes ``path`` itself, or saves a changed copy to ``output``. South
    latitudes and west longitudes are negative, as :func:`location` returns
    them. JPEG, PNG and TIFF keep their pixels untouched; other formats (HEIC)
    may be saved again.
    """
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude must be from -90 to 90, not {}".format(latitude))
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude must be from -180 to 180, not {}".format(longitude))
    gps = {
        "Latitude": float(abs(latitude)),
        "LatitudeRef": "S" if latitude < 0 else "N",
        "Longitude": float(abs(longitude)),
        "LongitudeRef": "W" if longitude < 0 else "E",
    }
    return _set_properties(path, {"{GPS}": gps}, output)


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


def _edit(source: PathLike, output: PathLike, change: Callable[[int], int], quality: Optional[float] = None) -> Path:
    """
    Apply ``change`` to the upright ``CIImage`` of ``source`` and save the result to ``output``.

    The metadata (date, camera, location...) is kept, with the orientation
    reset to upright, since the pixels already are.
    """
    target, kind = _output(output)
    if quality is not None and not 0.0 <= quality <= 1.0:
        raise ValueError("quality must be from 0.0 to 1.0, not {}".format(quality))
    io = _io()
    with _cf.owned(_source(source)) as image_source:
        with _objc.autorelease_pool():
            pixels = _objc.ciimage_cgimage(change(_objc.ciimage(Path(source).expanduser().absolute())))
        with _cf.owned(pixels), _cf.owned(_metadata(image_source, quality)) as save:
            return _write(target, kind, lambda destination: io.CGImageDestinationAddImage(destination, pixels, save))


def _extent(image: int) -> Any:
    return _objc.send(image, "extent", restype=_objc.CGRect)


def _transform(image: int, a: float, b: float, c: float, d: float, tx: float = 0.0, ty: float = 0.0) -> int:
    return _objc.send(
        image,
        "imageByApplyingTransform:",
        _objc.CGAffineTransform(a, b, c, d, tx, ty),
        argtypes=(_objc.CGAffineTransform,),
    )


def _to_origin(image: int) -> int:
    """Move an image so its extent starts at (0, 0)."""
    extent = _extent(image)
    return _transform(image, 1, 0, 0, 1, -extent.origin.x, -extent.origin.y)


def crop(
    source: PathLike, output: PathLike, box: Tuple[int, int, int, int], *, quality: Optional[float] = None
) -> Path:
    """
    Save the part of an image inside ``box``, ``(x, y, width, height)`` in pixels from the top-left corner.

    The box is measured on the upright picture, as it shows on screen. Like
    :func:`resize`, the metadata is kept and ``output``'s extension sets the
    format::

        macos.image.crop("screenshot.png", "button.png", (40, 120, 200, 60))
    """
    x, y, width, height = box
    if width <= 0 or height <= 0:
        raise ValueError("the box's width and height must be positive, not {} x {}".format(width, height))

    def change(picture: int) -> int:
        picture = _to_origin(picture)
        extent = _extent(picture)
        if x < 0 or y < 0 or x + width > extent.size.width or y + height > extent.size.height:
            raise ValueError(
                "the box {} doesn't fit in the {:g} x {:g} image".format(box, extent.size.width, extent.size.height)
            )
        # Core Image measures from the bottom-left corner.
        rect = _objc.CGRect(_objc.CGPoint(x, extent.size.height - y - height), _objc.CGSize(width, height))
        return _objc.send(picture, "imageByCroppingToRect:", rect, argtypes=(_objc.CGRect,))

    return _edit(source, output, change, quality)


def rotate(source: PathLike, output: PathLike, degrees: int, *, quality: Optional[float] = None) -> Path:
    """
    Turn an image clockwise by ``degrees`` (90, 180 or 270; negative turns counter-clockwise).

    The metadata is kept and ``output``'s extension sets the format.
    """
    if degrees % 90:
        raise ValueError("degrees must be a multiple of 90, not {}".format(degrees))
    turns = (degrees // 90) % 4
    # Clockwise on screen is a negative angle in Core Image, whose y axis points up.
    cos, sin = [(1, 0), (0, -1), (-1, 0), (0, 1)][turns]
    return _edit(source, output, lambda picture: _to_origin(_transform(picture, cos, sin, -sin, cos)), quality)


def flip(
    source: PathLike, output: PathLike, *, direction: str = "horizontal", quality: Optional[float] = None
) -> Path:
    """
    Mirror an image: ``direction="horizontal"`` swaps left and right, ``"vertical"`` turns it upside down.

    The metadata is kept and ``output``'s extension sets the format.
    """
    if direction not in ("horizontal", "vertical"):
        raise ValueError("direction must be 'horizontal' or 'vertical', not {!r}".format(direction))
    horizontal = direction == "horizontal"
    scale_x, scale_y = (-1, 1) if horizontal else (1, -1)
    return _edit(source, output, lambda picture: _to_origin(_transform(picture, scale_x, 0, 0, scale_y)), quality)


def straighten(source: PathLike, output: PathLike, *, quality: Optional[float] = None) -> Path:
    """
    Level a photo whose horizon is tilted, and return ``output``.

    The tilt comes from :func:`macos.vision.horizon`. The photo is turned
    and cropped to the largest part with the same proportions, so no empty
    corners show. A photo without a tilted horizon is saved unchanged. The
    metadata is kept and ``output``'s extension sets the format.
    """
    from . import vision

    tilt = vision.horizon(source)

    def change(picture: int) -> int:
        if not tilt:
            return picture
        picture = _to_origin(picture)
        extent = _extent(picture)
        width, height = extent.size.width, extent.size.height
        # Turn it back by the tilt (Core Image turns counter-clockwise for positive angles).
        angle = math.radians(-tilt)
        cos, sin = math.cos(angle), math.sin(angle)
        turned = _to_origin(_transform(picture, cos, sin, -sin, cos))
        # The largest rectangle with the photo's proportions inside the turned photo.
        cos, sin = abs(cos), abs(sin)
        scale = min(width / (width * cos + height * sin), height / (width * sin + height * cos))
        bounds = _extent(turned)
        crop_width, crop_height = width * scale, height * scale
        rect = _objc.CGRect(
            _objc.CGPoint((bounds.size.width - crop_width) / 2, (bounds.size.height - crop_height) / 2),
            _objc.CGSize(crop_width, crop_height),
        )
        return _objc.send(turned, "imageByCroppingToRect:", rect, argtypes=(_objc.CGRect,))

    return _edit(source, output, change, quality)


def _filter(name: str, image: int, **values: Any) -> int:
    """Apply the Core Image filter ``name`` to ``image``; ``values`` are its other inputs, as Objective-C objects."""
    ci_filter = _objc.send(_objc.cls("CIFilter"), "filterWithName:", _objc.nsstring(name), argtypes=(_objc.id,))
    inputs = dict(inputImage=image, **values)
    for key, value in inputs.items():
        _objc.send(
            ci_filter, "setValue:forKey:", value, _objc.nsstring(key), argtypes=(_objc.id, _objc.id), restype=None
        )
    result = _objc.send(ci_filter, "valueForKey:", _objc.nsstring("outputImage"), argtypes=(_objc.id,))
    if not result:
        raise MacOSError("the {} filter failed".format(name))
    return result


def _number_object(value: float) -> int:
    return _objc.send(_objc.cls("NSNumber"), "numberWithDouble:", float(value), argtypes=(ctypes.c_double,))


def blur_faces(source: PathLike, output: PathLike, *, quality: Optional[float] = None) -> Path:
    """
    Save a copy of a photo with every face pixelated, and return ``output``.

    Use it with :func:`strip_metadata` before sharing a photo of other people.
    Faces are found with :func:`macos.vision.faces`; a photo without faces is
    saved unchanged. The metadata is kept and ``output``'s extension sets the
    format.
    """
    from . import vision

    boxes = vision.faces(source)

    def change(picture: int) -> int:
        picture = _to_origin(picture)
        extent = _extent(picture)
        width, height = extent.size.width, extent.size.height
        result = picture
        for left, top, box_width, box_height in boxes:
            # Grow the box a little to cover the hair and the chin, and turn
            # it into Core Image's pixels, measured from the bottom-left.
            margin_x, margin_y = box_width * 0.15, box_height * 0.15
            face = _objc.CGRect(
                _objc.CGPoint((left - margin_x) * width, (1.0 - top - box_height - margin_y) * height),
                _objc.CGSize((box_width + 2 * margin_x) * width, (box_height + 2 * margin_y) * height),
            )
            # About ten blocks across the face: too coarse to recognize anyone.
            block = max(face.size.width, face.size.height) / 10
            center = _objc.send(
                _objc.cls("CIVector"),
                "vectorWithX:Y:",
                face.origin.x + face.size.width / 2,
                face.origin.y + face.size.height / 2,
                argtypes=(ctypes.c_double, ctypes.c_double),
            )
            blocks = _filter("CIPixellate", picture, inputScale=_number_object(block), inputCenter=center)
            blocks = _objc.send(blocks, "imageByCroppingToRect:", face, argtypes=(_objc.CGRect,))
            result = _objc.send(blocks, "imageByCompositingOverImage:", result, argtypes=(_objc.id,))
        return _objc.send(result, "imageByCroppingToRect:", extent, argtypes=(_objc.CGRect,))

    return _edit(source, output, change, quality)


@lru_cache(maxsize=None)
def _srgb() -> int:
    graphics = framework("CoreGraphics")
    graphics.CGColorSpaceCreateWithName.argtypes = (ctypes.c_void_p,)
    graphics.CGColorSpaceCreateWithName.restype = ctypes.c_void_p
    return int(graphics.CGColorSpaceCreateWithName(ctypes.c_void_p.in_dll(graphics, "kCGColorSpaceSRGB")))


def _sample(path: PathLike, longest: int = 100) -> List[Tuple[int, int, int]]:
    """The sRGB colors of an image scaled down to ``longest`` pixels, without the transparent ones."""
    framework("CoreImage")
    with _objc.autorelease_pool():
        picture = _to_origin(_objc.ciimage(Path(path).expanduser().absolute()))
        extent = _extent(picture)
        scale = min(1.0, longest / max(extent.size.width, extent.size.height, 1.0))
        width = max(1, int(extent.size.width * scale))
        height = max(1, int(extent.size.height * scale))
        small = _transform(picture, scale, 0, 0, scale)
        buffer = ctypes.create_string_buffer(width * height * 4)
        context = _objc.send(_objc.cls("CIContext"), "contextWithOptions:", None, argtypes=(_objc.id,))
        rgba8 = ctypes.c_int.in_dll(framework("CoreImage"), "kCIFormatRGBA8").value
        _objc.send(
            context,
            "render:toBitmap:rowBytes:bounds:format:colorSpace:",
            small,
            buffer,
            width * 4,
            _objc.CGRect(_objc.CGPoint(0, 0), _objc.CGSize(width, height)),
            rgba8,
            _srgb(),
            argtypes=(_objc.id, ctypes.c_void_p, ctypes.c_long, _objc.CGRect, ctypes.c_int, ctypes.c_void_p),
            restype=None,
        )
    raw = buffer.raw
    colors = []
    for index in range(0, len(raw), 4):
        red, green, blue, alpha = raw[index : index + 4]
        if alpha >= 128:  # the colors are premultiplied by alpha
            colors.append((red * 255 // alpha, green * 255 // alpha, blue * 255 // alpha))
    return colors


def _kmeans(colors: List[Tuple[int, int, int]], count: int) -> List[Tuple[Tuple[float, ...], int]]:
    """Group ``colors`` into up to ``count`` clusters; return (mean color, size) pairs, largest first."""
    # Close colors share a bin (8 levels per channel step), which keeps the
    # clustering fast and deterministic.
    sums: Dict[Tuple[int, int, int], List[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for red, green, blue in colors:
        entry = sums[(red >> 3, green >> 3, blue >> 3)]
        entry[0] += red
        entry[1] += green
        entry[2] += blue
        entry[3] += 1
    points: List[Tuple[Tuple[float, ...], int]] = [((r / n, g / n, b / n), n) for r, g, b, n in sums.values()]
    if not points:
        return []

    def distance(one: Tuple[float, ...], two: Tuple[float, ...]) -> float:
        return sum((a - b) ** 2 for a, b in zip(one, two))

    # Seed with the most common color, then, one by one, the color that is
    # both common and far from the seeds so far (a deterministic k-means++).
    centers: List[Tuple[float, ...]] = [max(points, key=lambda point: point[1])[0]]
    while len(centers) < min(count, len(points)):
        score, color = max(
            (weight * min(distance(color, center) for center in centers), color) for color, weight in points
        )
        if score == 0:
            break
        centers.append(color)

    sizes = [0] * len(centers)
    for _ in range(20):
        totals = [[0.0, 0.0, 0.0] for _ in centers]
        sizes = [0] * len(centers)
        for color, weight in points:
            nearest = min(range(len(centers)), key=lambda index: distance(color, centers[index]))
            for channel in range(3):
                totals[nearest][channel] += color[channel] * weight
            sizes[nearest] += weight
        moved = [
            tuple(total / sizes[index] for total in totals[index]) if sizes[index] else centers[index]
            for index in range(len(centers))
        ]
        if all(math.isclose(distance(new, old), 0.0, abs_tol=1e-6) for new, old in zip(moved, centers)):
            break
        centers = moved
    clusters = [(centers[index], sizes[index]) for index in range(len(centers)) if sizes[index]]
    return sorted(clusters, key=lambda cluster: -cluster[1])


def dominant_colors(path: PathLike, count: int = 5) -> List[str]:
    """
    Return the main colors of an image as hex strings, the most present first: ``['#1d3557', '#f1faee', ...]``.

    Returns up to ``count`` colors (fewer for images with fewer colors).
    Transparent pixels are left out. Handy to theme a page after a cover
    image or to sort pictures by color.
    """
    if count < 1:
        raise ValueError("count must be at least 1, not {}".format(count))
    clusters = _kmeans(_sample(path), count)
    return ["#" + "".join("{:02x}".format(int(round(channel))) for channel in color) for color, _ in clusters]


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
            _objc.CGAffineTransform(scale, 0, 0, scale, 0, 0),
            argtypes=(_objc.CGAffineTransform,),
        )
        return _objc.ciimage_png(scaled)
