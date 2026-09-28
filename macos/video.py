# -*- coding: utf-8 -*-

"""
Read, grab frames from and convert videos.

::

    macos.video.info("clip.mov")                 # VideoInfo(duration=12.5, width=1920, height=1080, ...)
    Path("cover.png").write_bytes(macos.video.frame("clip.mov", at=3.0))
    macos.video.convert("clip.mov", "small.mp4", quality="medium")
    macos.video.to_gif("screen.mov", "demo.gif", fps=10, width=480)

Uses AVFoundation, the framework behind QuickTime Player, and the
``avconvert`` command that ships with macOS: every format QuickTime opens
(MOV, MP4, M4V, HEVC, ProRes...) works, with no ffmpeg to install.
"""

import ctypes
import os
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple, Union

from . import _cf, _objc
from ._system import framework, run
from .errors import MacOSError

__all__ = ["VideoInfo", "info", "frame", "convert", "to_gif"]

PathLike = Union[str, "os.PathLike[str]"]

_CODECS = {
    "avc1": "h264",
    "hvc1": "hevc",
    "hev1": "hevc",
    "ap4h": "prores",
    "ap4x": "prores",
    "apch": "prores",
    "apcn": "prores",
    "apcs": "prores",
    "apco": "prores",
    "jpeg": "mjpeg",
}

# What convert() writes for each output extension.
_EXTENSIONS = {".mov", ".mp4", ".m4v", ".m4a"}

# avconvert's presets: by quality, and by height for resizing.
_QUALITY = {"high": "PresetHighestQuality", "medium": "PresetMediumQuality", "low": "PresetLowQuality"}
_HEIGHTS = {480: "Preset640x480", 540: "Preset960x540", 720: "Preset1280x720", 1080: "Preset1920x1080", 2160: "Preset3840x2160"}
_HEVC_HEIGHTS = {1080: "PresetHEVC1920x1080", 2160: "PresetHEVC3840x2160"}


class _CMTime(ctypes.Structure):
    _fields_ = [("value", ctypes.c_int64), ("timescale", ctypes.c_int32), ("flags", ctypes.c_uint32), ("epoch", ctypes.c_int64)]


_VALID = 1  # kCMTimeFlags_Valid
_TIMESCALE = 600  # the usual movie timescale: exact for 24, 25, 30 and 60 fps


@dataclass(frozen=True)
class VideoInfo:
    """What a video file contains."""

    duration: float
    """In seconds."""
    width: int
    """In pixels, as it plays (turned upright, like a portrait phone video)."""
    height: int
    fps: Optional[float]
    """Frames per second, as the file declares it."""
    codec: Optional[str]
    """``'h264'``, ``'hevc'``, ``'prores'``... or the codec's four-character code for others."""
    has_audio: bool


def _load() -> None:
    framework("AVFoundation")
    framework("AppKit")


def _existing(path: PathLike) -> Path:
    resolved = Path(path).expanduser().absolute()
    if not resolved.exists():
        raise FileNotFoundError(str(resolved))
    return resolved


def _asset(path: Path) -> int:
    """An autoreleased ``AVURLAsset``. Call inside an autorelease pool."""
    asset = _objc.send(
        _objc.cls("AVURLAsset"), "URLAssetWithURL:options:", _objc.file_url(path), None, argtypes=(_objc.id, _objc.id)
    )
    if not asset or not _objc.send(asset, "isPlayable", restype=_objc.BOOL):
        raise ValueError("{} is not a video macOS can play".format(path))
    return asset


def _tracks(asset: int, kind: str) -> List[int]:
    return list(_objc.nsarray(_objc.send(asset, "tracksWithMediaType:", _objc.nsstring(kind), argtypes=(_objc.id,))))


def _seconds(time: _CMTime) -> float:
    return time.value / time.timescale if time.flags & _VALID and time.timescale else 0.0


@lru_cache(maxsize=None)
def _media() -> ctypes.CDLL:
    media = framework("CoreMedia")
    media.CMFormatDescriptionGetMediaSubType.argtypes = (ctypes.c_void_p,)
    media.CMFormatDescriptionGetMediaSubType.restype = ctypes.c_uint32
    return media


def _upright_size(track: int) -> Tuple[int, int]:
    size = _objc.send(track, "naturalSize", restype=_objc.CGSize)
    transform = _objc.send(track, "preferredTransform", restype=_objc.CGAffineTransform)
    width, height = abs(round(size.width)), abs(round(size.height))
    # A quarter turn (a portrait phone video) swaps the sides.
    return (height, width) if abs(transform.b) > 0.5 and abs(transform.c) > 0.5 else (width, height)


def info(path: PathLike) -> VideoInfo:
    """Return the duration, size, frame rate and codec of a video file, and whether it has sound."""
    _load()
    source = _existing(path)
    with _objc.autorelease_pool():
        asset = _asset(source)
        duration = _seconds(_objc.send(asset, "duration", restype=_CMTime))
        videos = _tracks(asset, "vide")
        width = height = 0
        fps: Optional[float] = None
        codec: Optional[str] = None
        if videos:
            width, height = _upright_size(videos[0])
            rate = float(_objc.send(videos[0], "nominalFrameRate", restype=ctypes.c_float))
            fps = round(rate, 3) if rate > 0 else None
            formats = list(_objc.nsarray(_objc.send(videos[0], "formatDescriptions")))
            if formats:
                code = struct.pack(">I", _media().CMFormatDescriptionGetMediaSubType(formats[0])).decode("latin-1")
                codec = _CODECS.get(code, code.strip())
        return VideoInfo(
            duration=round(duration, 3),
            width=width,
            height=height,
            fps=fps,
            codec=codec,
            has_audio=bool(_tracks(asset, "soun")),
        )


def frame(path: PathLike, at: float = 0.0, *, size: Optional[int] = None) -> bytes:
    """
    Return the frame shown ``at`` seconds into a video, as PNG bytes.

    ``size`` limits the longest side, in pixels, for thumbnails::

        Path("thumb.png").write_bytes(macos.video.frame("clip.mov", at=5, size=320))

    The frame is turned upright, like the video plays.
    """
    if at < 0:
        raise ValueError("at must not be negative, not {}".format(at))
    if size is not None and size <= 0:
        raise ValueError("size must be positive, not {}".format(size))
    _load()
    source = _existing(path)
    with _objc.autorelease_pool():
        asset = _asset(source)
        duration = _seconds(_objc.send(asset, "duration", restype=_CMTime))
        if at > duration:
            raise ValueError("at={} is past the end of the {:.3f}-second video".format(at, duration))
        generator = _objc.send(
            _objc.cls("AVAssetImageGenerator"), "assetImageGeneratorWithAsset:", asset, argtypes=(_objc.id,)
        )
        _objc.send(generator, "setAppliesPreferredTrackTransform:", True, argtypes=(_objc.BOOL,), restype=None)
        # The exact frame, not the nearest keyframe.
        exact = _CMTime(0, 1, _VALID, 0)
        for selector in ("setRequestedTimeToleranceBefore:", "setRequestedTimeToleranceAfter:"):
            _objc.send(generator, selector, exact, argtypes=(_CMTime,), restype=None)
        if size is not None:
            _objc.send(
                generator, "setMaximumSize:", _objc.CGSize(size, size), argtypes=(_objc.CGSize,), restype=None
            )
        actual = _CMTime()
        error = ctypes.c_void_p()
        image = _objc.send(
            generator,
            "copyCGImageAtTime:actualTime:error:",
            _CMTime(round(at * _TIMESCALE), _TIMESCALE, _VALID, 0),
            ctypes.byref(actual),
            ctypes.byref(error),
            argtypes=(_CMTime, ctypes.c_void_p, ctypes.c_void_p),
            restype=ctypes.c_void_p,
        )
        if not image:
            raise MacOSError("could not read the frame at {}s: {}".format(at, _objc.error_message(error) or "no image"))
        return _objc.cgimage_png(image)


def convert(
    source: PathLike,
    output: PathLike,
    *,
    quality: str = "high",
    hevc: bool = False,
    height: Optional[int] = None,
    start: Optional[float] = None,
    duration: Optional[float] = None,
) -> Path:
    """
    Convert, compress, resize or trim a video, and return ``output``.

    ``output``'s extension sets the container: ``.mp4``, ``.mov`` or ``.m4v``;
    ``.m4a`` keeps only the sound. ``quality`` is ``"high"``, ``"medium"`` or
    ``"low"`` (a small preview, about 224 pixels wide). ``hevc=True`` encodes
    in HEVC (H.265), smaller than H.264 at the same quality. ``height``
    resizes it to fit 640×480, 960×540, 1280×720, 1920×1080 or 3840×2160
    (``height=480`` to ``2160``; only 1080 and 2160 with HEVC), keeping its
    proportions: a 16:9 video at ``height=480`` becomes 640×360. ``start``
    and ``duration``, in seconds, keep only part of it::

        macos.video.convert("screen.mov", "share.mp4", quality="medium")
        macos.video.convert("talk.mov", "talk.m4a")                        # the sound only
        macos.video.convert("clip.mov", "intro.mp4", start=0, duration=10)

    Replaces ``output`` if it exists. Uses ``avconvert``, which ships with macOS.
    """
    original = _existing(source)
    target = Path(output).expanduser().absolute()
    extension = target.suffix.lower()
    if extension not in _EXTENSIONS:
        raise ValueError("can't write {!r} videos; use one of {}".format(target.suffix, ", ".join(sorted(_EXTENSIONS))))
    if quality not in _QUALITY:
        raise ValueError("quality must be 'high', 'medium' or 'low', not {!r}".format(quality))
    for label, value in (("start", start), ("duration", duration)):
        if value is not None and (value < 0 or (label == "duration" and value == 0)):
            raise ValueError("{} must be positive, not {}".format(label, value))
    if extension == ".m4a":
        if not info(original).has_audio:
            raise ValueError("{} has no sound to keep".format(original))
        preset = "PresetAppleM4A"
    elif height is not None:
        heights = _HEVC_HEIGHTS if hevc else _HEIGHTS
        if height not in heights:
            raise ValueError(
                "height must be one of {}{}, not {}".format(
                    ", ".join(str(value) for value in sorted(heights)), " with hevc=True" if hevc else "", height
                )
            )
        preset = heights[height]
    else:
        preset = "PresetHEVCHighestQuality" if hevc and quality == "high" else _QUALITY[quality]
        if hevc and quality != "high":
            raise ValueError("hevc=True only has the 'high' quality; pass height= to make it smaller")
    target.parent.mkdir(parents=True, exist_ok=True)
    args = ["avconvert", "--source", str(original), "--output", str(target), "--preset", preset, "--replace"]
    if start is not None:
        args += ["--start", str(start)]
    if duration is not None:
        args += ["--duration", str(duration)]
    run(args)
    return target


def to_gif(
    source: PathLike,
    output: PathLike,
    *,
    fps: float = 10.0,
    width: int = 480,
    start: Optional[float] = None,
    duration: Optional[float] = None,
) -> Path:
    """
    Turn a video (or part of it) into an animated GIF that loops, and return ``output``.

    Made for screen recordings you put in a README, an issue or a chat::

        macos.screen.record("demo.mov", 8, region=(0, 0, 1280, 800))
        macos.video.to_gif("demo.mov", "demo.gif", fps=10, width=640)

    ``fps`` is the frames per second of the GIF and ``width`` its width in
    pixels (never wider than the video), keeping the proportions. ``start``
    and ``duration``, in seconds, keep only part of the video. GIFs get big
    fast: a few seconds at 10 fps and 480 pixels is a good size.
    """
    from . import image

    if not 0 < fps <= 50:
        raise ValueError("fps must be above 0 and at most 50, not {}".format(fps))
    if width <= 0:
        raise ValueError("width must be positive, not {}".format(width))
    for label, value in (("start", start), ("duration", duration)):
        if value is not None and (value < 0 or (label == "duration" and value == 0)):
            raise ValueError("{} must be positive, not {}".format(label, value))
    target = Path(output).expanduser().absolute()
    if target.suffix.lower() != ".gif":
        raise ValueError("the output must be a .gif, not {!r}".format(target.suffix))
    details = info(source)
    begin = start or 0.0
    if begin >= details.duration:
        raise ValueError("start={} is past the end of the {:.3f}-second video".format(begin, details.duration))
    end = min(details.duration, begin + duration) if duration is not None else details.duration
    step = 1.0 / fps
    times = [begin + index * step for index in range(max(1, int((end - begin) * fps)))]

    original = _existing(source)
    io = image._io()
    pictures: List[int] = []
    try:
        with _objc.autorelease_pool():
            generator = _objc.send(
                _objc.cls("AVAssetImageGenerator"), "assetImageGeneratorWithAsset:", _asset(original), argtypes=(_objc.id,)
            )
            _objc.send(generator, "setAppliesPreferredTrackTransform:", True, argtypes=(_objc.BOOL,), restype=None)
            # Half a frame either way: close enough, and much faster than exact frames.
            tolerance = _CMTime(round(step / 2 * _TIMESCALE), _TIMESCALE, _VALID, 0)
            for selector in ("setRequestedTimeToleranceBefore:", "setRequestedTimeToleranceAfter:"):
                _objc.send(generator, selector, tolerance, argtypes=(_CMTime,), restype=None)
            if width < details.width and details.width:
                size = _objc.CGSize(width, round(width * details.height / details.width))
                _objc.send(generator, "setMaximumSize:", size, argtypes=(_objc.CGSize,), restype=None)
            for moment in times:
                error = ctypes.c_void_p()
                picture = _objc.send(
                    generator,
                    "copyCGImageAtTime:actualTime:error:",
                    _CMTime(round(moment * _TIMESCALE), _TIMESCALE, _VALID, 0),
                    None,
                    ctypes.byref(error),
                    argtypes=(_CMTime, ctypes.c_void_p, ctypes.c_void_p),
                    restype=ctypes.c_void_p,
                )
                if not picture:
                    raise MacOSError(
                        "could not read the frame at {:.2f}s: {}".format(moment, _objc.error_message(error) or "no image")
                    )
                pictures.append(picture)

        delay = round(step, 2)  # GIF delays are in hundredths of a second
        loop = _cf.from_python({"{GIF}": {"LoopCount": 0}})  # 0: loop forever
        timing = _cf.from_python({"{GIF}": {"DelayTime": delay, "UnclampedDelayTime": delay}})

        def add(destination: int) -> None:
            io.CGImageDestinationSetProperties(destination, loop)
            for picture in pictures:
                io.CGImageDestinationAddImage(destination, picture, timing)

        with _cf.owned(loop), _cf.owned(timing):
            target.parent.mkdir(parents=True, exist_ok=True)
            return image._write(target, "com.compuserve.gif", add, len(pictures))
    finally:
        for picture in pictures:
            _cf.release(picture)
