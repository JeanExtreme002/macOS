"""Tests of :mod:`macos.spotlight` against the real system. Skipped outside macOS."""

from pathlib import Path

import pytest

import macos


def test_spotlight_finds_an_app_by_file_name():
    found = macos.spotlight.search_name("Calculator.app", folder="/System/Applications")
    if not found:
        pytest.skip("Spotlight indexing is off")
    assert Path("/System/Applications/Calculator.app") in found


def test_spotlight_limit_and_invalid_query():
    assert len(macos.spotlight.search("kind:app", folder="/System/Applications", limit=1)) <= 1
    with pytest.raises(ValueError):
        macos.spotlight.search("kMDItemFoo ==")


def test_spotlight_metadata():
    data = macos.spotlight.metadata("/System/Applications/Calculator.app")

    assert data["kMDItemFSName"] == "Calculator.app"
