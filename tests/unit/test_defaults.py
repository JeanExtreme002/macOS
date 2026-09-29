"""Unit tests for :mod:`macos.defaults`. They run on any platform."""

import pytest

import macos


def test_defaults_argument_checks():
    with pytest.raises(ValueError, match="domain must not be empty"):
        macos.defaults.read(" ", "key")
    with pytest.raises(ValueError, match="domain must not be empty"):
        macos.defaults.keys("")
    with pytest.raises(ValueError, match="use delete"):
        macos.defaults.write("com.example.app", "key", None)
