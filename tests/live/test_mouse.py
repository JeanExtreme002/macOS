"""Tests of :mod:`macos.mouse` against the real system. Skipped outside macOS."""

import time

import pytest

import macos


def test_mouse_position_is_on_a_display():
    x, y = macos.mouse.position()

    assert isinstance(x, float) and isinstance(y, float)
    left = min(display.x for display in macos.screen.displays())
    top = min(display.y for display in macos.screen.displays())
    right = max(display.x + display.width for display in macos.screen.displays())
    bottom = max(display.y + display.height for display in macos.screen.displays())
    assert left <= x <= right and top <= y <= bottom


def test_click_text_and_watch_clicks(test_window):
    import threading

    if not (macos.screen.has_permission() and macos.mouse.has_permission()):
        pytest.skip("needs the Screen Recording and Accessibility permissions")
    test_window.set_frame(300, 300, 500, 300)
    test_window.focus()
    time.sleep(0.8)
    before = macos.mouse.position()
    try:
        match = macos.mouse.click_text(test_window.title)
        assert 300 <= match.center[0] <= 800 and 300 <= match.center[1] <= 340
        with pytest.raises(macos.MacOSError, match="isn't on the screen"):
            macos.mouse.click_text("no such text, surely")

        def clicks():
            time.sleep(0.5)
            macos.mouse.click(550, 450)
            macos.mouse.click(560, 460, count=2)

        threading.Thread(target=clicks).start()
        seen = [(round(c.x), round(c.y), c.button, c.count) for c in macos.mouse.watch(timeout=3)]
        assert (550, 450, "left", 1) in seen and (560, 460, "left", 2) in seen
    finally:
        macos.mouse.move(*before)
