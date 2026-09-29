"""Unit tests for :mod:`macos.sound`. They run on any platform."""

import pytest

import macos


def test_sound_argument_checks():
    with pytest.raises(ValueError):
        macos.sound.play("Glass", volume=2)
