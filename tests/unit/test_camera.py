"""Unit tests for :mod:`macos.camera`. They run on any platform."""

import pytest

import macos


def test_temporary_photo_is_removed_on_failure(monkeypatch, tmp_path):
    from macos import _capture

    monkeypatch.setattr(macos.camera.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(_capture, "request_permission", lambda media: False)

    with pytest.raises(macos.PermissionDeniedError):
        macos.camera.photo()

    assert list(tmp_path.iterdir()) == []


def test_camera_argument_checks(tmp_path):
    with pytest.raises(ValueError, match="can't save '.gif'"):
        macos.camera.photo(tmp_path / "out.gif")
    with pytest.raises(ValueError, match=".mov"):
        macos.camera.record(tmp_path / "out.mp4", 1)
    with pytest.raises(ValueError, match="positive"):
        macos.camera.record(tmp_path / "out.mov", 0)
