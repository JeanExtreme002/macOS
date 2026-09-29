"""Tests of :mod:`macos.pdf` against the real system. Skipped outside macOS."""


import pytest

import macos
from macos import _objc
from tests.helpers import rgb_png, small_png


def _text_pdf(folder, pages):
    """A PDF with real text on each page, made by CUPS (every Mac has it)."""
    import subprocess

    source = folder / "pages.txt"
    source.write_text("\f".join(pages) + "\n")
    target = folder / "doc.pdf"
    with open(target, "wb") as output:
        result = subprocess.run(["cupsfilter", str(source)], stdout=output, stderr=subprocess.DEVNULL)
    if result.returncode != 0 or not target.stat().st_size:
        pytest.skip("cupsfilter can't make PDFs here")
    return target


def test_pdf_read_merge_extract_and_render(tmp_path):
    document = _text_pdf(tmp_path, ["Page one says hello", "Page two says ola"])

    assert macos.pdf.page_count(document) == 2
    assert macos.pdf.text(document, pages=[2]) == "Page two says ola"
    assert "Page one says hello" in macos.pdf.text(document)

    merged = macos.pdf.merge([document, document], tmp_path / "merged.pdf")
    assert macos.pdf.page_count(merged) == 4
    reordered = macos.pdf.extract(document, [2, 1], tmp_path / "reordered.pdf")
    assert macos.pdf.text(reordered).startswith("Page two")

    with pytest.raises(ValueError, match="out of range"):
        macos.pdf.text(document, pages=[3])

    page = macos.pdf.render(document, 1, size=2048)
    assert page.startswith(b"\x89PNG")
    assert "Page one says hello" in macos.vision.text(page)


def test_pdf_render_is_exact_and_follows_rotation(tmp_path):
    import ctypes
    import struct

    from macos import _objc

    document = _text_pdf(tmp_path, ["A portrait page"])
    for size in (1024, 2048):
        width, height = struct.unpack(">II", macos.pdf.render(document, size=size)[16:24])
        assert max(width, height) == size and height > width

    rotated = tmp_path / "rotated.pdf"
    with macos.pdf._open(document) as opened:
        _objc.send(macos.pdf._page(opened, 1), "setRotation:", 90, argtypes=(ctypes.c_long,), restype=None)
        macos.pdf._save(opened, rotated)
    width, height = struct.unpack(">II", macos.pdf.render(rotated, size=1024)[16:24])
    assert (max(width, height), width > height) == (1024, True)


def test_pdf_passwords(tmp_path):
    from macos import _objc

    document = _text_pdf(tmp_path, ["Secret page"])
    locked = tmp_path / "locked.pdf"
    with macos.pdf._open(document) as opened:
        # PDFKit only encrypts when both a user and an owner password are set.
        options = _objc.send(
            _objc.cls("NSDictionary"),
            "dictionaryWithObjects:forKeys:",
            _objc.nsarray_of([_objc.nsstring("1234"), _objc.nsstring("owner")]),
            _objc.nsarray_of(
                [_objc.nsstring("PDFDocumentUserPasswordOption"), _objc.nsstring("PDFDocumentOwnerPasswordOption")]
            ),
            argtypes=(_objc.id, _objc.id),
        )
        _objc.send(
            opened,
            "writeToFile:withOptions:",
            _objc.nsstring(str(locked)),
            options,
            argtypes=(_objc.id, _objc.id),
            restype=_objc.BOOL,
        )

    with pytest.raises(macos.PermissionDeniedError):
        macos.pdf.text(locked)
    with pytest.raises(macos.PermissionDeniedError, match="wrong password"):
        macos.pdf.text(locked, password="nope")
    assert macos.pdf.text(locked, password="1234") == "Secret page"

    merged = macos.pdf.merge([locked, document], tmp_path / "merged.pdf", password="1234")
    assert macos.pdf.page_count(merged) == 2
    assert macos.pdf.text(merged).startswith("Secret page")  # the result isn't encrypted


def test_pdf_from_images(tmp_path, capfd):
    import ctypes

    from macos import _cf

    photo = tmp_path / "photo.png"
    photo.write_bytes(small_png(40, 20))
    # The same picture, stored sideways with EXIF orientation 6, as phones do.
    portrait = tmp_path / "portrait.jpg"
    io = macos.image._io()
    with _cf.owned(macos.image._source(photo)) as source, _cf.owned(_cf.from_python({"Orientation": 6})) as options:
        macos.image._write(portrait, "public.jpeg", lambda d: io.CGImageDestinationAddImageFromSource(d, source, 0, options))
    url = "https://github.com/JeanExtreme002/pymacos"

    document = macos.pdf.from_images([photo, portrait, macos.image.qr_code(url, size=300)], tmp_path / "scan.pdf")

    assert macos.pdf.page_count(document) == 3
    with macos.pdf._open(document) as opened:
        sizes = []
        for number in (1, 2):
            bounds = _objc.send(
                macos.pdf._page(opened, number), "boundsForBox:", 0, argtypes=(ctypes.c_long,), restype=_objc.CGRect
            )
            sizes.append((bounds.size.width, bounds.size.height))
    assert sizes == [(40, 20), (20, 40)]  # each page is its picture, upright
    found = macos.vision.barcodes(macos.pdf.render(document, page=3))
    assert [code.payload for code in found] == [url]
    # PDFKit logged "CoreGraphics PDF has logged an error" for images without an orientation.
    assert "CoreGraphics" not in capfd.readouterr().err
    with pytest.raises(ValueError):
        macos.pdf.from_images([b"not an image"], tmp_path / "junk.pdf")
    assert not (tmp_path / "junk.pdf").exists()


def test_pdf_metadata_rotate_and_encrypt(tmp_path):
    import ctypes

    document = _text_pdf(tmp_path, ["Page one says hello", "Page two says ola"])

    details = macos.pdf.metadata(document)
    assert details.created is not None and details.created.tzinfo is not None
    assert details.keywords == []

    # Rotating in place is safe: the output replaces the input only once written.
    assert macos.pdf.rotate(document, 90, document, pages=[2]) == document
    macos.pdf.rotate(document, -180, document)
    with macos.pdf._open(document) as opened:
        rotations = [_objc.send(macos.pdf._page(opened, n), "rotation", restype=ctypes.c_long) for n in (1, 2)]
    assert rotations == [180, 270]

    locked = macos.pdf.encrypt(document, tmp_path / "locked.pdf", "s3cret")
    with pytest.raises(macos.PermissionDeniedError):
        macos.pdf.text(locked)
    assert macos.pdf.text(locked, password="s3cret", pages=[1]) == "Page one says hello"
    changed = macos.pdf.encrypt(locked, tmp_path / "changed.pdf", "other", current_password="s3cret")
    assert macos.pdf.page_count(changed, password="other") == 2


def test_pdf_watermark_and_compress(tmp_path):
    document = _text_pdf(tmp_path, ["Page one says hello", "Page two says ola"])
    macos.pdf.rotate(document, 90, document, pages=[2])

    marked = macos.pdf.watermark(document, "CONFIDENTIAL", tmp_path / "marked.pdf", color="#d00000")

    assert macos.pdf.page_count(marked) == 2
    assert macos.pdf.text(marked, pages=[1]).split("\n") == ["Page one says hello", "CONFIDENTIAL"]
    import struct

    width, height = struct.unpack(">II", macos.pdf.render(marked, page=2, size=400)[16:24])
    assert width > height  # the turned page still shows turned

    # Noise: what a scan or photo looks like to a compressor.
    noisy = tmp_path / "noise.png"
    noisy.write_bytes(rgb_png(800, 600, lambda x, y: ((x * 7919 + y * 104729) % 251, (x * y) % 247, (x + y * 31) % 241)))
    photos = macos.pdf.from_images([noisy], tmp_path / "photo.pdf")
    smaller = macos.pdf.compress(photos, tmp_path / "small.pdf")
    assert smaller.stat().st_size < photos.stat().st_size / 2
    assert macos.pdf.page_count(smaller) == 1

    # Only text: nothing to shrink, and rewriting it would make it bigger.
    original = document.read_bytes()
    text_only = macos.pdf.compress(document, tmp_path / "text.pdf")
    assert text_only.read_bytes() == original
    assert macos.pdf.compress(document, document).read_bytes() == original  # in place too
    in_place = tmp_path / "in-place.pdf"
    in_place.write_bytes(photos.read_bytes())
    macos.pdf.compress(in_place, in_place)
    assert in_place.stat().st_size < photos.stat().st_size / 2

    locked = macos.pdf.encrypt(photos, tmp_path / "locked.pdf", "s3cret")
    opened = macos.pdf.compress(locked, tmp_path / "opened.pdf", password="s3cret")
    assert macos.pdf.page_count(opened) == 1  # no password needed any more


def test_pdf_grayscale(tmp_path):
    colorful = tmp_path / "colorful.png"
    colorful.write_bytes(rgb_png(120, 80, lambda x, y: (230, 60, 30) if x < 60 else (20, 90, 220)))
    document = macos.pdf.from_images([colorful], tmp_path / "colorful.pdf")

    gray = macos.pdf.grayscale(document, tmp_path / "gray.pdf")

    page = tmp_path / "page.png"
    page.write_bytes(macos.pdf.render(gray, size=120))
    for color in macos.image.dominant_colors(page, count=3):
        red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
        assert max(red, green, blue) - min(red, green, blue) <= 3  # no color left
