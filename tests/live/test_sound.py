"""Tests of :mod:`macos.sound` against the real system. Skipped outside macOS."""


import pytest

import macos


def test_sound():
    import time

    assert "Glass" in macos.sound.names()
    start = time.monotonic()
    macos.sound.play("Tink", volume=0.0)  # silent
    assert time.monotonic() - start > 0.1  # waited for the sound to end
    with pytest.raises(ValueError):
        macos.sound.play("Definitely Not A Sound")
