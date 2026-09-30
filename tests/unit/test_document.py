"""Unit tests for :mod:`macos.document`. They run on any platform."""

import pytest

import macos


def test_convert_checks_the_output_format(fake_run, tmp_path):
    source = tmp_path / "notes.rtf"
    source.write_text("{\\rtf1 hi}")
    with pytest.raises(ValueError, match="can't write '.pages' files; the formats are .doc, .docx"):
        macos.document.convert(source, tmp_path / "notes.pages")
    with pytest.raises(ValueError, match="can't write 'notes' files"):
        macos.document.convert(source, tmp_path / "notes")
    with pytest.raises(FileNotFoundError):
        macos.document.convert(tmp_path / "missing.docx", tmp_path / "out.pdf")


def test_text_points_pdfs_to_the_pdf_module(fake_run, tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError, match="macos.pdf.text"):
        macos.document.text(source)
