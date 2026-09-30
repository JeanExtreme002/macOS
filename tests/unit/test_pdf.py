"""Unit tests for :mod:`macos.pdf`. They run on any platform."""

import sys

import pytest

import macos


def test_pdf_argument_checks(tmp_path):
    with pytest.raises(ValueError, match="multiple of 90"):
        macos.pdf.rotate(__file__, 45, tmp_path / "out.pdf")
    with pytest.raises(ValueError, match="empty"):
        macos.pdf.encrypt(__file__, tmp_path / "out.pdf", "")
    with pytest.raises(ValueError, match="at least one"):
        macos.pdf.from_images([], "out.pdf")
    with pytest.raises(ValueError, match="empty"):
        macos.pdf.watermark(__file__, " ", tmp_path / "out.pdf")
    with pytest.raises(ValueError, match="opacity"):
        macos.pdf.watermark(__file__, "DRAFT", tmp_path / "out.pdf", opacity=0)
    with pytest.raises(ValueError, match="hex color"):
        macos.pdf.watermark(__file__, "DRAFT", tmp_path / "out.pdf", color="red")


@pytest.mark.skipif(sys.platform != "darwin", reason="reads and writes PDF forms with PDFKit")
def test_forms(tmp_path):
    from tests.helpers import pdf_form

    form = pdf_form(tmp_path / "form.pdf")
    fields = {field.name: field for field in macos.pdf.form_fields(form)}
    assert {name: (field.kind, field.value, field.options) for name, field in fields.items()} == {
        "Full name": ("text", None, ()),
        "Agree": ("checkbox", False, ()),
        "Plan": ("choice", None, ("Free", "Pro")),
        "Size": ("radio", None, ("Small", "Large")),
    }
    values = {"Full name": "Ana Souza", "Agree": True, "Plan": "Pro", "Size": "Large"}
    filled = macos.pdf.fill_form(form, values, tmp_path / "filled.pdf")
    assert {field.name: field.value for field in macos.pdf.form_fields(filled)} == {
        "Full name": "Ana Souza", "Agree": True, "Plan": "Pro", "Size": "Large"
    }
    refused = (
        ({"Nope": "x"}, "no field named 'Nope'"),
        ({"Agree": "yes"}, "pass True or False"),
        ({"Plan": "Gold"}, "offers Free, Pro"),
        ({"Full name": True}, "takes text"),
    )
    for wrong, message in refused:
        with pytest.raises(ValueError, match=message):
            macos.pdf.fill_form(form, wrong, tmp_path / "never.pdf")
    assert not (tmp_path / "never.pdf").exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="draws PDF pages with PDFKit")
def test_sign(tmp_path):
    from tests.helpers import pdf_form, rgb_png

    form = macos.pdf.fill_form(pdf_form(tmp_path / "form.pdf"), {"Full name": "Ana Souza"}, tmp_path / "filled.pdf")
    signature = tmp_path / "signature.png"
    signature.write_bytes(rgb_png(300, 100, lambda x, y: (20, 40, 160)))
    signed = macos.pdf.sign(form, signature, tmp_path / "signed.pdf", width=150)
    assert macos.pdf.page_count(signed) == 1 and macos.pdf.form_fields(signed) == []  # flattened
    assert "Ana Souza" in macos.pdf.text(signed)  # the filled-in value is drawn in the page
    # The image is drawn where asked, at the size asked: look at the rendered page.
    assert _color_at(signed, tmp_path, (400, 632, 70, 28)) == "signature"   # bottom right, 36 points in
    assert _color_at(signed, tmp_path, (100, 400, 60, 60)) == "page"
    rotated = macos.pdf.sign(
        macos.pdf.rotate(form, 90, tmp_path / "rotated.pdf"), signature, tmp_path / "rotated-signed.pdf",
        position="top_left", width=120,
    )
    assert _color_at(rotated, tmp_path, (50, 40, 60, 20)) == "signature"      # upright, top left as it's seen
    assert _color_at(rotated, tmp_path, (560, 450, 60, 60)) == "page"
    with pytest.raises(ValueError, match="out of range"):
        macos.pdf.sign(form, signature, tmp_path / "never.pdf", page=2)
    with pytest.raises(ValueError, match="position must be one of"):
        macos.pdf.sign(form, signature, tmp_path / "never.pdf", position="middle")
    with pytest.raises(ValueError, match="width must be positive"):
        macos.pdf.sign(form, signature, tmp_path / "never.pdf", width=0)


def _color_at(pdf_path, folder, box):
    """Whether a box of the page, rendered 700 pixels tall or wide, is mostly the signature's blue or the page."""
    png = folder / "render.png"
    png.write_bytes(macos.pdf.render(pdf_path, 1, size=700))
    crop = macos.image.crop(png, folder / "crop.png", box)
    red, green, blue = (int(macos.image.dominant_colors(crop, 1)[0][index:index + 2], 16) for index in (1, 3, 5))
    return "signature" if blue > 120 and red < 80 else "page"


@pytest.mark.skipif(sys.platform != "darwin", reason="adds annotations with PDFKit")
def test_add_text(tmp_path):
    from macos import _objc
    from tests.helpers import rgb_png

    white = tmp_path / "white.png"
    white.write_bytes(rgb_png(612, 792, lambda x, y: (255, 255, 255)))
    page = macos.pdf.from_images([white], tmp_path / "page.pdf")
    stamped = macos.pdf.add_text(page, "Received", tmp_path / "one.pdf", size=20)
    stamped = macos.pdf.add_text(stamped, "Checked\nby Ana", tmp_path / "two.pdf", position="bottom_right", color="#c00000")

    with macos.pdf._open(stamped) as document:
        notes = _objc.nsarray(_objc.send(macos.pdf._page(document, 1), "annotations"))
        assert [(_objc.pystring(_objc.send(note, "type")), _objc.pystring(_objc.send(note, "contents"))) for note in notes] == [
            ("FreeText", "Received"),
            ("FreeText", "Checked\nby Ana"),
        ]
    assert stamped.read_bytes().count(b"/AP") >= 2  # appearances saved: other viewers show the text too
    assert _dominant(stamped, tmp_path, (36, 38, 60, 14)) != "#ffffff"  # the text, top left, 36 points in
    reddish = [
        (int(color[1:3], 16), int(color[3:5], 16)) for color in _dominant(stamped, tmp_path, (455, 640, 50, 28), count=2)
    ]
    assert any(red > 150 and green < 100 for red, green in reddish)  # the red text, bottom right
    assert _dominant(stamped, tmp_path, (250, 350, 80, 80)) == "#ffffff"  # the rest untouched
    for wrong, message in (({"size": 0}, "size must be positive"), ({"font": "NoSuchFont-Bold"}, "no font is named")):
        with pytest.raises(ValueError, match=message):
            macos.pdf.add_text(page, "x", tmp_path / "never.pdf", **wrong)
    with pytest.raises(ValueError, match="page 2 is out of range"):
        macos.pdf.add_text(page, "x", tmp_path / "never.pdf", page=2)


def _dominant(pdf_path, folder, box, count=1):
    """The main color (or colors) of a box of page 1, rendered 700 pixels tall or wide."""
    png = folder / "render.png"
    png.write_bytes(macos.pdf.render(pdf_path, 1, size=700))
    colors = macos.image.dominant_colors(macos.image.crop(png, folder / "crop.png", box), count)
    return colors if count > 1 else colors[0]


@pytest.mark.parametrize("angle, corner", [(0, "top_left"), (90, "top_left"), (180, "bottom_right"), (270, "top_right")])
@pytest.mark.skipif(sys.platform != "darwin", reason="adds annotations with PDFKit")
def test_add_text_on_a_rotated_page(tmp_path, angle, corner):
    from tests.helpers import rgb_png

    white = tmp_path / "white.png"
    white.write_bytes(rgb_png(612, 792, lambda x, y: (255, 255, 255)))
    page = macos.pdf.from_images([white], tmp_path / "page.pdf")
    if angle:
        page = macos.pdf.rotate(page, angle, tmp_path / "rotated.pdf")
    stamped = macos.pdf.add_text(page, "Received", tmp_path / "stamped.pdf", position=corner, size=24)

    png = tmp_path / "render.png"
    png.write_bytes(macos.pdf.render(stamped, 1, size=700))
    width, height = macos.image.info(png).width, macos.image.info(png).height
    assert (width > height) == (angle % 180 == 90)  # rendered as it's seen

    def inked(horizontal, vertical):
        """Whether the corner of the rendered page has anything but white, as the page is seen."""
        box = (
            0 if horizontal == "left" else width - 180,
            0 if vertical == "top" else height - 70,
            180,
            70,
        )
        colors = macos.image.dominant_colors(macos.image.crop(png, tmp_path / "corner.png", box), 2)
        return any(color != "#ffffff" for color in colors)

    vertical, horizontal = corner.split("_")
    assert inked(horizontal, vertical)  # where asked, upright and whole
    opposite = ("right" if horizontal == "left" else "left", "bottom" if vertical == "top" else "top")
    assert not inked(*opposite)


@pytest.mark.skipif(sys.platform != "darwin", reason="reads and writes outlines with PDFKit")
def test_bookmarks(tmp_path):
    from tests.helpers import small_png

    picture = tmp_path / "page.png"
    picture.write_bytes(small_png(100, 100))
    book = macos.pdf.from_images([picture] * 3, tmp_path / "book.pdf")
    assert macos.pdf.bookmarks(book) == []
    contents = [("Intro", 1), ("Chapter 1", 2), ("1.1", 2, 1), ("1.1.1", 3, 2), ("Chapter 2", 3)]
    marked = macos.pdf.set_bookmarks(book, contents, tmp_path / "marked.pdf")
    assert [(mark.title, mark.page, mark.level) for mark in macos.pdf.bookmarks(marked)] == [
        ("Intro", 1, 0), ("Chapter 1", 2, 0), ("1.1", 2, 1), ("1.1.1", 3, 2), ("Chapter 2", 3, 0)
    ]  # fmt: skip
    assert macos.pdf.bookmarks(macos.pdf.set_bookmarks(marked, [], tmp_path / "cleared.pdf")) == []
    for wrong, message in (([("Deep", 1, 1)], "deeper than"), ([("x", 9)], "out of range"), ([(" ", 1)], "must not be empty")):
        with pytest.raises(ValueError, match=message):
            macos.pdf.set_bookmarks(book, wrong, tmp_path / "never.pdf")


@pytest.mark.skipif(sys.platform != "darwin", reason="reads PDFs with CoreGraphics")
def test_images(tmp_path):
    from tests.helpers import rgb_png

    stripes = tmp_path / "stripes.png"
    stripes.write_bytes(rgb_png(120, 80, lambda x, y: (200, 30, 30) if x < 60 else (30, 30, 200)))
    photo = macos.image.convert(stripes, tmp_path / "photo.jpg")
    document = macos.pdf.from_images([photo, stripes, photo], tmp_path / "pictures.pdf")

    found = macos.pdf.images(document, tmp_path / "out")
    assert [path.name for path in found] == ["page1-1.jpg", "page2-1.png"]  # the photo used twice, saved once
    assert found[0].read_bytes()[:2] == b"\xff\xd8"  # the JPEG as embedded
    for path in found:
        assert (macos.image.info(path).width, macos.image.info(path).height) == (120, 80)
    assert [path.name for path in macos.pdf.images(document, tmp_path / "two", pages=[2])] == ["page2-1.png"]
    with pytest.raises(ValueError, match="out of range"):
        macos.pdf.images(document, tmp_path / "never", pages=[4])


@pytest.mark.skipif(sys.platform != "darwin", reason="reads PDFs with CoreGraphics")
def test_images_in_calibrated_colors_and_inverted(tmp_path):
    from tests.helpers import pdf_with_images

    document = tmp_path / "raw.pdf"
    document.write_bytes(pdf_with_images([
        ("[/CalGray << /WhitePoint [0.95 1 1.09] >>]", "[1 0]", 4, 4, bytes([0]) * 16),   # black, inverted: white
        ("[/CalRGB << /WhitePoint [0.95 1 1.09] >>]", None, 4, 4, bytes([200, 30, 30]) * 16),
        ("/DeviceGray", "[0 0.5]", 4, 4, bytes([128]) * 16),   # a mapping it can't draw: skipped
    ]))  # fmt: skip
    found = macos.pdf.images(document, tmp_path / "out")
    assert [path.name for path in found] == ["page1-1.png", "page1-2.png"]
    assert macos.image.dominant_colors(found[0], 1) == ["#ffffff"]
    assert macos.image.dominant_colors(found[1], 1) == ["#c81e1e"]


@pytest.mark.skipif(sys.platform != "darwin", reason="reads PDFs with CoreGraphics")
def test_images_come_in_name_order(tmp_path):
    from tests.helpers import pdf_with_images

    # Twelve pictures, each redder than the last, named Im0 to Im11: the dictionary's own order isn't fixed.
    document = tmp_path / "twelve.pdf"
    document.write_bytes(pdf_with_images([("/DeviceRGB", None, 2, 2, bytes([index * 20, 0, 0]) * 4) for index in range(12)]))
    found = macos.pdf.images(document, tmp_path / "out")
    assert [path.name for path in found] == ["page1-{}.png".format(number) for number in range(1, 13)]
    assert [int(macos.image.dominant_colors(path, 1)[0][1:3], 16) for path in found] == [index * 20 for index in range(12)]
    assert macos.pdf._natural(b"Im10") > macos.pdf._natural(b"Im2")


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_seen_and_unrotated_are_inverses(rotation):
    box = (72.0, 200.0, 120.0, 40.0)
    assert macos.pdf._unrotated(macos.pdf._seen(box, 612, 792, rotation), 612, 792, rotation) == box


def test_next_to():
    anchor = (72.0, 200.0, 90.0, 20.0)  # a word as the page is seen
    assert macos.pdf._next_to(anchor, 100, 40, "right", 8) == (170.0, 190.0)  # centered on the line
    assert macos.pdf._next_to(anchor, 100, 40, "left", 8) == (-36.0, 190.0)
    assert macos.pdf._next_to(anchor, 100, 40, "above", 8) == (72.0, 228.0)
    assert macos.pdf._next_to(anchor, 100, 40, "below", 8) == (72.0, 152.0)


@pytest.mark.skipif(sys.platform != "darwin", reason="finds text and draws with PDFKit")
def test_sign_and_add_text_near_a_text(tmp_path):
    from macos import _objc
    from tests.helpers import pdf_with_text, rgb_png

    form = tmp_path / "form.pdf"
    form.write_bytes(pdf_with_text([("Name:", 72, 700), ("Signature:", 72, 200)]))
    signature = tmp_path / "signature.png"
    signature.write_bytes(rgb_png(300, 100, lambda x, y: (20, 40, 160)))

    signed = macos.pdf.sign(form, signature, tmp_path / "signed.pdf", near="signature:", width=120)  # any case
    # "Signature:" ends near x=155 points, its line centered near y=206: the picture (120 x 40 points) sits just
    # right of it, which the 700-pixel render (0.884 pixels a point) shows around pixels 145-250 by 500-535.
    assert _color_at(signed, tmp_path, (180, 505, 40, 20)) == "signature"
    assert _color_at(signed, tmp_path, (160, 440, 40, 20)) == "page"  # not on the line above

    named = macos.pdf.add_text(form, "Ana Souza", tmp_path / "named.pdf", near="Name:")
    with macos.pdf._open(named) as document:
        note = list(_objc.nsarray(_objc.send(macos.pdf._page(document, 1), "annotations")))[0]
        bounds = _objc.send(note, "bounds", restype=_objc.CGRect)
    assert 115 < bounds.origin.x < 135 and 690 < bounds.origin.y < 710  # right after "Name:", on its line

    below = macos.pdf.add_text(form, "Ana Souza", tmp_path / "below.pdf", near="Name:", side="below")
    with macos.pdf._open(below) as document:
        note = list(_objc.nsarray(_objc.send(macos.pdf._page(document, 1), "annotations")))[0]
        bounds = _objc.send(note, "bounds", restype=_objc.CGRect)
    assert 70 <= bounds.origin.x < 75 and bounds.origin.y + bounds.size.height < 700  # under it

    with pytest.raises(ValueError, match="isn't on the PDF"):
        macos.pdf.sign(form, signature, tmp_path / "never.pdf", near="Witness:")
    with pytest.raises(ValueError, match="isn't on page 1"):
        macos.pdf.add_text(form, "x", tmp_path / "never.pdf", near="Witness:", page=1)
    with pytest.raises(ValueError, match="position or near, not both"):
        macos.pdf.add_text(form, "x", tmp_path / "never.pdf", near="Name:", position="top_left")
    with pytest.raises(ValueError, match="side must be one of"):
        macos.pdf.sign(form, signature, tmp_path / "never.pdf", near="Name:", side="up")
