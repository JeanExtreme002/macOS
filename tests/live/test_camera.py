"""Tests of :mod:`macos.camera` against the real system. Skipped outside macOS."""

import pytest

import macos
from tests.helpers import CAPTURE


def test_camera_devices():
    cameras = macos.camera.devices()  # no permission needed, and the camera stays off

    assert all(camera.name and camera.id for camera in cameras)
    assert sum(camera.is_default for camera in cameras) <= 1
    if cameras:
        assert cameras[0].is_default


@CAPTURE
def test_camera_photo_and_record(tmp_path):
    if not macos.camera.devices():
        pytest.skip("no camera")
    shots = [macos.camera.photo(tmp_path / "shot.jpg"), macos.camera.photo(tmp_path / "shot.png"), macos.camera.photo()]
    movie = macos.camera.record(tmp_path / "clip.mov", 2, audio=False)
    try:
        assert [macos.image.info(shot).format for shot in shots] == ["jpeg", "png", "jpeg"]
        details = macos.video.info(movie)
        assert details.width > 0 and 1.5 < details.duration < 3 and not details.has_audio
    finally:
        for made in shots + [movie]:
            made.unlink()  # don't keep pictures of the room
