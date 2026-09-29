"""Tests of :mod:`macos.volume` against the real system. Skipped outside macOS."""

import pytest

import macos


def test_volume_round_trip():
    level, muted = macos.volume.get(), macos.volume.is_muted()
    if level is None:
        pytest.skip("the output device has no volume control")
    try:
        macos.volume.set(level)
        assert macos.volume.get() == level
        macos.volume.mute()
        assert macos.volume.is_muted() is True
        assert macos.volume.get() == level  # muting keeps the level
    finally:
        macos.volume.set(level)
        (macos.volume.mute if muted else macos.volume.unmute)()
    assert macos.volume.is_muted() is muted
