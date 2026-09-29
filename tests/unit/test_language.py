"""Unit tests for :mod:`macos.language`. They run on any platform."""

import pytest

import macos


def test_language_argument_checks():
    with pytest.raises(ValueError):
        macos.language.guess("x", limit=0)
