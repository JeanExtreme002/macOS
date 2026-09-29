"""Helpers shared by several test modules: small images and markers."""

import os
from pathlib import Path

import pytest


def rgb_png(width, height, pixel):
    """A PNG whose color at (x, y) is ``pixel(x, y)``."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def small_png(width=4, height=4):
    """A small valid PNG, so the image tests don't depend on screen access."""
    return rgb_png(width, height, lambda x, y: (255, 0, 0))


def png_size(png):
    import struct

    return struct.unpack(">II", png[16:24])


WALLPAPER_MOVIE = Path("/System/Library/Desktop Pictures/.wallpapers/Sequoia Sunrise/Sequoia Sunrise.mov")


CAPTURE = pytest.mark.skipif(
    not os.environ.get("PYMACOS_CAPTURE_TESTS"),
    reason="turns the camera or the microphone on: set PYMACOS_CAPTURE_TESTS=1 to run",
)
