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
