"""Tests of :mod:`macos.screen` against the real system. Skipped outside macOS."""

import os
import re

import pytest

import macos


def test_screenshot_writes_an_image(tmp_path):
    target = macos.screenshot(tmp_path / "shot.png", region=(0, 0, 50, 50), check_permission=False)

    assert target.exists()
    assert os.path.getsize(target) > 0
    with open(target, "rb") as image:
        assert image.read(8) == b"\x89PNG\r\n\x1a\n"


def test_displays():
    displays = macos.screen.displays()
    if not displays:
        pytest.skip("no display attached")

    main = displays[0]
    assert main.is_main
    assert main.width > 0 and main.height > 0
    assert main.pixel_width >= main.width
    assert main.scale >= 1


def test_wallpaper_round_trip():
    current = macos.screen.wallpaper()
    if current is None or not current.exists():
        pytest.skip("the desktop picture isn't a file")
    macos.screen.set_wallpaper(current)
    assert macos.screen.wallpaper() == current


def test_display_brightness():
    try:
        current = macos.screen.brightness()
    except macos.NotSupportedError:
        pytest.skip("no display with a brightness macOS controls")
    assert 0.0 <= current <= 1.0
    macos.screen.set_brightness(current)  # the same value: nothing changes
    assert abs(macos.screen.brightness() - current) < 0.01


def test_night_shift():
    try:
        on = macos.screen.night_shift()
    except macos.NotSupportedError:
        pytest.skip("no Night Shift")
    macos.screen.set_night_shift(on)  # the same state: nothing changes
    assert macos.screen.night_shift() == on


def test_true_tone_lock_and_sleep_state():
    try:
        on = macos.screen.true_tone()
    except macos.NotSupportedError:
        on = None
    if on is not None:
        macos.screen.set_true_tone(on)  # the same state: nothing changes
        assert macos.screen.true_tone() == on
    assert isinstance(macos.screen.is_locked(), bool)
    assert macos.screen.is_asleep() is False  # the tests run on a display that is on


def test_screen_record(tmp_path):
    if not macos.screen.has_permission():
        pytest.skip("no Screen Recording permission")
    target = tmp_path / "screen.mov"
    try:
        macos.screen.record(target, 1, region=(0, 0, 160, 100))
        details = macos.video.info(target)
        assert details.duration > 0 and details.width >= 160
    finally:
        target.unlink(missing_ok=True)  # don't keep a picture of the screen around


def test_find_text_on_the_screen(test_window):
    if not macos.screen.has_permission():
        pytest.skip("no Screen Recording permission")
    test_window.set_frame(200, 200, 700, 300)
    test_window.focus()
    # The title's words, not its random part, which OCR may misread (0 and o, 1 and l).
    words = "pymacos test"
    first = macos.screen.wait_for_text(words, region=(200, 200, 700, 300), timeout=10)
    assert first is not None, "the window's title should be readable on the screen"
    x, y = first.center
    assert 200 <= x <= 900 and 200 <= y <= 240  # in the window's title bar
    anywhere = [match.center for match in macos.screen.find_text(words)]
    assert any(abs(mx - x) <= 4 and abs(my - y) <= 4 for mx, my in anywhere)  # the same place, on the whole display
    assert macos.screen.wait_for_text("no such text, surely", timeout=0.5) is None
    assert re.fullmatch(r"#[0-9a-f]{6}", macos.screen.color_at(550, 380))
