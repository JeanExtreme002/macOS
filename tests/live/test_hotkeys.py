"""Tests of :mod:`macos.hotkeys` against the real system. Skipped outside macOS."""

import time

import pytest

import macos


def test_hotkeys():
    import threading

    if not (macos.hotkeys.has_permission() and macos.keyboard.has_permission()):
        pytest.skip("needs the Input Monitoring and Accessibility permissions")
    combination = "ctrl+option+cmd+f19"  # no app uses it
    calls = []

    def press_twice():
        for _ in range(2):
            macos.keyboard.press(combination)
            time.sleep(0.2)

    macos.hotkeys.register(combination, lambda: calls.append(1))
    try:
        threading.Timer(0.3, press_twice).start()
        macos.hotkeys.run(timeout=1.5)
        assert calls == [1, 1]
    finally:
        macos.hotkeys.unregister(combination)

    threading.Timer(0.3, lambda: macos.keyboard.press(combination)).start()
    assert macos.hotkeys.wait(combination, timeout=3) is True
    assert macos.hotkeys.wait(combination, timeout=0.3) is False
