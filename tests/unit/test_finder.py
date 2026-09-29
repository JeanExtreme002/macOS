"""Unit tests for :mod:`macos.finder`. They run on any platform."""

import pytest

import macos


def test_finder_reveal(fake_run, tmp_path):
    macos.finder.reveal(tmp_path)

    assert fake_run.args == ["open", "-R", str(tmp_path)]


def test_thumbnail_rejects_bad_sizes():
    with pytest.raises(ValueError):
        macos.finder.thumbnail(__file__, size=0)


def test_make_alias_checks_its_paths(tmp_path):
    original = tmp_path / "report.pdf"
    original.write_text("x")
    (tmp_path / "report.pdf alias").write_text("already here")

    with pytest.raises(FileNotFoundError):
        macos.finder.make_alias(tmp_path / "missing.pdf")
    with pytest.raises(FileExistsError):
        macos.finder.make_alias(original)  # "report.pdf alias" is taken
    with pytest.raises(FileExistsError):
        macos.finder.make_alias(original, tmp_path)  # the folder's "report.pdf alias" too
    with pytest.raises(FileNotFoundError):
        macos.finder.make_alias(original, tmp_path / "no" / "folder" / "alias")
    with pytest.raises(ValueError, match="no folder around it"):
        macos.finder.make_alias("/")  # a disk has nothing next to it


def test_watch_tells_what_happened(tmp_path):
    from macos.finder import _CREATED, _RENAMED, _kind

    seen = set()
    new = tmp_path / "new.txt"
    new.write_text("x")
    # FSEvents keeps the "created" flag on later changes: only the first sighting is a creation.
    assert _kind(new, _CREATED, seen) == "created"
    assert _kind(new, _CREATED, seen) == "modified"
    assert _kind(tmp_path / "gone.txt", _CREATED | _RENAMED, seen) == "deleted"
    moved = tmp_path / "moved.txt"
    moved.write_text("x")
    assert _kind(moved, _RENAMED, seen) == "renamed"
    new.unlink()
    assert _kind(new, _CREATED, seen) == "deleted"
    new.write_text("again")
    assert _kind(new, _CREATED, seen) == "created"


def test_watch_needs_a_folder(tmp_path):
    with pytest.raises(NotADirectoryError):
        next(macos.finder.watch(tmp_path / "missing"))
    (tmp_path / "file.txt").write_text("x")
    with pytest.raises(NotADirectoryError):
        macos.finder.wait_for_change(tmp_path / "file.txt")
