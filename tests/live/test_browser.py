"""Tests of :mod:`macos.browser` against the real system. Skipped outside macOS."""

import os

import pytest

import macos


@pytest.mark.skipif(
    not os.environ.get("PYMACOS_BROWSER_TESTS"),
    reason="reads the tabs of your browser, which macOS asks permission for: set PYMACOS_BROWSER_TESTS=1 to run",
)
def test_browser_reads_the_running_browser():
    tabs = macos.browser.tabs()
    if not tabs:
        pytest.skip("no scriptable browser (Safari, Chrome...) is running")

    assert all(tab.app in macos.browser.BROWSERS and tab.index >= 1 for tab in tabs)
    current = macos.browser.current_tab()
    assert current is not None and current.active and current in tabs
