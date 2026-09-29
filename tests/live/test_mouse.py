"""Tests of :mod:`macos.mouse` against the real system. Skipped outside macOS."""

import macos


def test_mouse_position_is_on_a_display():
    x, y = macos.mouse.position()

    assert isinstance(x, float) and isinstance(y, float)
    left = min(display.x for display in macos.screen.displays())
    top = min(display.y for display in macos.screen.displays())
    right = max(display.x + display.width for display in macos.screen.displays())
    bottom = max(display.y + display.height for display in macos.screen.displays())
    assert left <= x <= right and top <= y <= bottom
