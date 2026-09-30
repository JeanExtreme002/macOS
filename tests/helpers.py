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


SETTINGS = pytest.mark.skipif(
    not (os.environ.get("CI") or os.environ.get("PYMACOS_SETTINGS_TESTS")),
    reason="changes (then restores) a setting of this Mac: set PYMACOS_SETTINGS_TESTS=1 to run",
)

CAPTURE = pytest.mark.skipif(
    not os.environ.get("PYMACOS_CAPTURE_TESTS"),
    reason="turns the camera or the microphone on: set PYMACOS_CAPTURE_TESTS=1 to run",
)


def pdf_form(path):
    """Write a one-page PDF form to ``path``: a text field, a checkbox, a choice and two radio buttons."""
    import ctypes

    from macos import _objc, pdf
    from macos._objc import CGPoint, CGRect, CGSize

    blank = str(path) + ".png"
    with open(blank, "wb") as file:
        file.write(small_png(612, 792))
    pdf.from_images([blank], path)
    with pdf._open(path) as document:
        page = pdf._page(document, 1)

        def widget(name, field_type, x, y, control=None, on=None, choices=None):
            annotation = _objc.send(
                _objc.send(_objc.cls("PDFAnnotation"), "alloc"),
                "initWithBounds:forType:withProperties:",
                CGRect(CGPoint(x, y), CGSize(160, 24)),
                _objc.nsstring("Widget"),
                None,
                argtypes=(CGRect, _objc.id, _objc.id),
            )
            _objc.send(annotation, "setWidgetFieldType:", _objc.nsstring(field_type), argtypes=(_objc.id,), restype=None)
            if control is not None:
                _objc.send(annotation, "setWidgetControlType:", control, argtypes=(ctypes.c_long,), restype=None)
            if on is not None:
                _objc.send(annotation, "setButtonWidgetStateString:", _objc.nsstring(on), argtypes=(_objc.id,), restype=None)
            if choices is not None:
                array = _objc.send(_objc.cls("NSMutableArray"), "array")
                for choice in choices:
                    _objc.send(array, "addObject:", _objc.nsstring(choice), argtypes=(_objc.id,), restype=None)
                _objc.send(annotation, "setChoices:", array, argtypes=(_objc.id,), restype=None)
            _objc.send(annotation, "setFieldName:", _objc.nsstring(name), argtypes=(_objc.id,), restype=None)
            _objc.send(page, "addAnnotation:", annotation, argtypes=(_objc.id,), restype=None)
            _objc.send(annotation, "release", restype=None)

        widget("Full name", "/Tx", 72, 700)
        widget("Agree", "/Btn", 72, 650, control=2)
        widget("Plan", "/Ch", 72, 600, choices=["Free", "Pro"])
        widget("Size", "/Btn", 72, 550, control=1, on="Small")
        widget("Size", "/Btn", 250, 550, control=1, on="Large")
        pdf._save(document, path)
    return path
