"""Tests of :mod:`macos.finder` against the real system. Skipped outside macOS."""

import os
import uuid
from pathlib import Path

import pytest

import macos


def test_finder_tags(tmp_path):
    path = tmp_path / "tagged.txt"
    path.write_text("hi")

    assert macos.finder.tags(path) == []
    assert macos.finder.add_tags(path, "pymacos-a", "pymacos-b", "pymacos-a") == ["pymacos-a", "pymacos-b"]
    assert macos.finder.remove_tags(path, "pymacos-a", "missing") == ["pymacos-b"]
    macos.finder.set_tags(path, [])
    assert macos.finder.tags(path) == []


def test_finder_trash(tmp_path):
    path = tmp_path / "trash me {}.txt".format(uuid.uuid4())
    path.write_text("bye")

    trashed = macos.finder.trash(path)
    try:
        assert not path.exists()
        assert trashed.exists()
        assert ".Trash" in trashed.parts
    finally:
        trashed.unlink(missing_ok=True)


def test_finder_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        macos.finder.tags(tmp_path / "missing")


def test_thumbnail_rejects_huge_sizes():
    with pytest.raises(ValueError):
        macos.finder.thumbnail("/System/Library/CoreServices/Finder.app", size=100000)


def test_thumbnail_of_an_app_is_its_icon_at_the_requested_size():
    import struct

    image = macos.finder.thumbnail("/System/Library/CoreServices/Finder.app", size=64)
    width, height = struct.unpack(">II", image[16:24])  # the PNG header
    assert max(width, height) == 64


def test_finder_aliases(tmp_path):
    original = tmp_path / "report.pdf"
    original.write_text("x")
    folder = tmp_path / "Folder"
    folder.mkdir()

    alias = macos.finder.make_alias(original)
    assert alias == tmp_path / "report.pdf alias"
    assert macos.finder.is_alias(alias) and not macos.finder.is_alias(original)
    assert macos.finder.resolve_alias(alias).name == "report.pdf"
    assert macos.finder.resolve_alias(original) == original  # not an alias: as it is
    # Python itself sees a plain file.
    assert Path(os.path.realpath(alias)).name == "report.pdf alias"

    inside = macos.finder.make_alias(original, folder)
    assert inside == folder / "report.pdf alias"
    assert macos.finder.resolve_alias(macos.finder.make_alias(folder, tmp_path / "To folder")).name == "Folder"
    assert macos.finder.resolve_alias(macos.finder.make_alias(alias, tmp_path / "Alias of alias")).name == "report.pdf"
    link = tmp_path / "link"
    link.symlink_to(alias)
    assert not macos.finder.is_alias(link)
    assert macos.finder.resolve_alias(link).name == "report.pdf"

    # A disk has no name of its own: the alias takes the one Finder shows.
    disk = macos.finder.make_alias("/", tmp_path)
    assert disk.name.endswith(" alias") and disk.name != " alias"
    assert macos.finder.resolve_alias(disk) == Path("/")

    # An alias follows its original when it's moved and renamed...
    original.rename(folder / "moved.pdf")
    assert macos.finder.resolve_alias(alias).name == "moved.pdf"
    # ...but not when it's deleted.
    (folder / "moved.pdf").unlink()
    with pytest.raises(FileNotFoundError, match="original of the alias"):
        macos.finder.resolve_alias(alias)
