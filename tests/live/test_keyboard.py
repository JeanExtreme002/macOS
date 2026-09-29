"""Tests of :mod:`macos.keyboard` against the real system. Skipped outside macOS."""

import uuid

import pytest

import macos


def test_keyboard_and_mouse_permission():
    if macos.mouse.has_permission():
        # Moving the pointer where it already is changes nothing.
        macos.mouse.move(*macos.mouse.position())
    else:
        # The events would be dropped silently: better to say so.
        with pytest.raises(macos.PermissionDeniedError):
            macos.keyboard.press("shift")
        with pytest.raises(macos.PermissionDeniedError):
            macos.mouse.move(*macos.mouse.position())
    assert macos.keyboard.has_permission() == macos.mouse.has_permission()


def test_keyboard_backlight():
    try:
        current = macos.keyboard.brightness()
    except macos.NotSupportedError:
        pytest.skip("no keyboard backlight")
    automatic = macos.keyboard.auto_brightness()
    assert 0.0 <= current <= 1.0
    macos.keyboard.set_brightness(current)
    macos.keyboard.set_auto_brightness(automatic)
    assert macos.keyboard.auto_brightness() == automatic


def test_keyboard_layouts():
    enabled = macos.keyboard.layouts()
    current = macos.keyboard.layout()

    assert enabled and all(isinstance(name, str) and name for name in enabled)
    if current in enabled:  # an input method can be current without being a layout
        assert macos.keyboard.set_layout(current) == current  # the same layout: nothing changes
        assert macos.keyboard.layout() == current
    with pytest.raises(ValueError, match="no enabled keyboard layout"):
        macos.keyboard.set_layout("No Such Layout {}".format(uuid.uuid4()))
