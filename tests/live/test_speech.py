"""Tests of :mod:`macos.speech` against the real system. Skipped outside macOS."""

import macos


def test_voices_are_installed():
    assert any(voice.name for voice in macos.speech.voices())


def test_say_to_a_file(tmp_path):
    for name in ("speech.aiff", "speech.m4a", "speech.wav"):
        target = macos.say("pymacos", output=tmp_path / name)
        assert target.exists() and target.stat().st_size > 0
