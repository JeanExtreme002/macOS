"""Marks the tests under ``tests/live`` as live; the unit tests have their own conftest."""

import sys
from pathlib import Path

import pytest

_LIVE = Path(__file__).parent / "live"


@pytest.hookimpl(tryfirst=True)  # before -m "not live" deselects by marker
def pytest_collection_modifyitems(config, items):
    """Mark the tests under ``tests/live`` as live, and skip them outside macOS."""
    skip = pytest.mark.skip(reason="live tests need macOS")
    for item in items:
        if _LIVE in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.live)
            if sys.platform != "darwin":
                item.add_marker(skip)
