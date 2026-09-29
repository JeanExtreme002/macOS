"""Tests of :mod:`macos.windows` against the real system. Skipped outside macOS."""

import os
import time

import pytest

import macos


def test_windows(test_window):
    window = test_window

    window.set_frame(60, 80, 420, 300)
    time.sleep(0.2)
    assert window.frame == (60, 80, 420, 300)
    window.move(100, 120)
    window.resize(360, 260)
    time.sleep(0.2)
    assert (window.position, window.size) == ((100, 120), (360, 260))

    window.center()
    time.sleep(0.2)
    display = macos.screen.displays()[0]
    x, y, width, height = window.frame
    assert (width, height) == (360, 260)  # the same size
    assert abs(x + width / 2 - (display.x + display.width / 2)) <= 1
    assert abs(y + height / 2 - (display.y + display.height / 2)) <= 1

    assert window.fullscreen is False
    if os.environ.get("CI"):  # it switches to a Space of its own: not on the user's Mac
        window.set_fullscreen()  # returns once the animation is done
        assert window.fullscreen
        window.set_fullscreen(False)
        assert not window.fullscreen

    window.minimize()
    time.sleep(0.8)
    assert window.minimized
    window.restore()
    time.sleep(0.8)
    assert not window.minimized

    window.focus()
    for _ in range(20):
        if macos.windows.focused() == window:
            break
        time.sleep(0.1)
    else:
        # The user (or another app) may have taken the focus meanwhile: the
        # window must at least be its app's main one.
        from macos import _cf

        main = window._read("AXMain")
        with _cf.owned(main):
            assert _cf.to_bool(main)
    assert window in macos.windows.list()

    window.close()
    time.sleep(0.5)
    with pytest.raises(macos.MacOSError):
        window.title


def test_window_screenshot_and_wait_for(test_window):
    if not macos.screen.has_permission():
        pytest.skip("no Screen Recording permission")
    test_window.set_frame(100, 100, 400, 250)
    time.sleep(0.5)

    shot = test_window.screenshot()
    try:
        details = macos.image.info(shot)
        scale = macos.screen.displays()[0].scale
        assert (details.width, details.height) == (round(400 * scale), round(250 * scale))  # no shadow
    finally:
        shot.unlink()
    assert macos.windows.wait_for(title=test_window.title, timeout=5) == test_window
    assert macos.windows.wait_for(title="no such window, surely", timeout=0.3) is None


def test_window_snap(test_window):
    from macos.windows import _usable_areas

    area_x, area_y, area_width, area_height = _usable_areas()[0]
    test_window.snap("left", display=1)
    time.sleep(0.3)
    x, y, width, height = test_window.frame
    assert (x, y) == (round(area_x), round(area_y)) and abs(width - area_width / 2) <= 2
    test_window.snap("bottom_right")
    time.sleep(0.3)
    x, y, width, height = test_window.frame
    assert abs(x - (area_x + area_width / 2)) <= 2 and abs(y + height - (area_y + area_height)) <= 2
    with pytest.raises(ValueError, match="layout must be one of"):
        test_window.snap("diagonal")
