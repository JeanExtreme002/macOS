"""Unit tests for :mod:`macos.pdf`. They run on any platform."""

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
