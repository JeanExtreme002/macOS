"""Unit tests for :mod:`macos.auth`. They run on any platform."""

import pytest

import macos


def test_auth_argument_checks():
    with pytest.raises(ValueError, match="reason must not be empty"):
        macos.auth.confirm("  ")
