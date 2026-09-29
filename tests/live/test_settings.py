"""Tests of the keyboard, trackpad, mouse, Dock, Finder, appearance, screen and system settings. Skipped outside macOS."""

from contextlib import contextmanager

import macos
from tests.helpers import SETTINGS

_UNSET = object()


@contextmanager
def restored(*keys, current_host=False):
    """Put the ``(domain, key)`` pairs back as they were, deleting the ones that weren't set."""
    before = [(domain, key, macos.defaults.read(domain, key, default=_UNSET, current_host=current_host)) for domain, key in keys]
    try:
        yield
    finally:
        for domain, key, value in before:
            if value is _UNSET:
                macos.defaults.delete(domain, key, current_host=current_host)
            else:
                macos.defaults.write(domain, key, value, current_host=current_host)


def test_settings_are_read():
    interval, delay = macos.keyboard.key_repeat()
    assert interval > 0 and delay > 0
    for setting in (
        macos.keyboard.press_and_hold,
        macos.keyboard.standard_function_keys,
        macos.keyboard.autocorrect,
        macos.keyboard.smart_quotes,
        macos.keyboard.smart_dashes,
        macos.trackpad.tap_to_click,
        macos.trackpad.natural_scrolling,
        macos.dock.show_recents,
        macos.finder.show_desktop_icons,
        macos.finder.show_library_folder,
        macos.finder.show_full_path_in_title,
        macos.appearance.menu_bar_hidden,
        macos.system.ds_store_on_network,
        macos.system.ds_store_on_usb,
        macos.system.keep_windows_on_quit,
        macos.system.battery_percentage_shown,
    ):
        assert isinstance(setting(), bool), setting.__name__
    assert 0 <= macos.trackpad.tracking_speed() <= 1 and 0 <= macos.mouse.tracking_speed() <= 1
    assert set(macos.dock.hot_corners().values()) <= {None, *macos.dock.HOT_CORNER_ACTIONS}
    assert macos.dock.autohide_delay() >= 0 and macos.dock.minimize_effect() in ("genie", "scale")
    assert macos.dock.magnification() is None or 16 <= macos.dock.magnification() <= 128
    assert macos.finder.default_view() in ("icons", "list", "columns", "gallery")
    assert macos.finder.search_scope() in ("this_mac", "current_folder", "previous")
    assert macos.finder.new_window_folder().is_absolute()
    delay = macos.screen.screensaver_delay()
    assert delay is None or delay > 0


def test_more_settings_are_read():
    for setting in (
        macos.keyboard.auto_capitalization,
        macos.keyboard.double_space_period,
        macos.keyboard.full_keyboard_access,
        macos.trackpad.three_finger_drag,
        macos.dock.show_indicators,
        macos.dock.minimize_to_app,
        macos.dock.auto_rearrange_spaces,
        macos.dock.separate_spaces_per_display,
        macos.finder.folders_first,
        macos.finder.extension_change_warning,
        macos.finder.remove_old_trash_items,
        macos.windows.tiling,
        macos.windows.click_wallpaper_to_show_desktop,
        macos.screen.screenshot_thumbnail,
        macos.system.save_to_icloud_by_default,
        macos.system.expanded_save_dialog,
    ):
        assert isinstance(setting(), bool), setting.__name__
    assert macos.trackpad.secondary_click() in ("two_fingers", "bottom_right", "bottom_left", None)
    assert macos.mouse.scroll_speed() >= 0 and macos.mouse.double_click_speed() > 0
    assert macos.dock.autohide_duration() is None or macos.dock.autohide_duration() >= 0
    assert set(macos.finder.drives_on_desktop()) == {"internal", "external", "removable", "servers"}
    assert macos.windows.double_click_title_bar() in ("zoom", "fill", "minimize", None)
    assert macos.appearance.scroll_bars() in ("automatic", "when_scrolling", "always")
    assert macos.system.clock_format()["date"] in ("auto", "always", "never")
    assert isinstance(macos.keyboard.remappings(), dict)


@SETTINGS
def test_keyboard_and_system_settings_round_trip():
    keys = [
        (macos.defaults.GLOBAL, "NSAutomaticDashSubstitutionEnabled"),
        (macos.defaults.GLOBAL, "NSQuitAlwaysKeepsWindows"),
        ("com.apple.desktopservices", "DSDontWriteUSBStores"),
    ]
    with restored(*keys):
        macos.keyboard.set_smart_dashes(not macos.keyboard.smart_dashes())
        wanted = macos.keyboard.smart_dashes()
        macos.keyboard.set_smart_dashes(not wanted)
        assert macos.keyboard.smart_dashes() is not wanted
        for on in (True, False):
            macos.system.set_keep_windows_on_quit(on)
            macos.system.set_ds_store_on_usb(on)
            assert macos.system.keep_windows_on_quit() is on and macos.system.ds_store_on_usb() is on


@SETTINGS
def test_screensaver_delay_round_trip():
    with restored(("com.apple.screensaver", "idleTime"), current_host=True):
        macos.screen.set_screensaver_delay(7)
        assert macos.screen.screensaver_delay() == 7
        macos.screen.set_screensaver_delay(None)
        assert macos.screen.screensaver_delay() is None


@SETTINGS
def test_dock_and_finder_settings_round_trip():
    try:
        with restored(("com.apple.dock", "mineffect")):
            effect = macos.dock.minimize_effect()
            other = "scale" if effect == "genie" else "genie"
            macos.dock.set_minimize_effect(other)
            assert macos.dock.minimize_effect() == other
        with restored(("com.apple.finder", "FXDefaultSearchScope")):
            macos.finder.set_search_scope("current_folder")
            assert macos.finder.search_scope() == "current_folder"
    finally:
        macos.dock.restart()
        macos.finder.restart()


@SETTINGS
def test_remap_round_trip():
    before = macos.keyboard._mappings()
    try:
        macos.keyboard.remap("f13", "f14")  # keys few keyboards have
        assert macos.keyboard.remappings()["f13"] == "f14"
        macos.keyboard.remap("f13", None)
        assert "f13" not in macos.keyboard.remappings()
    finally:
        macos.keyboard._set_mappings(before)


@SETTINGS
def test_more_settings_round_trip():
    keys = [
        (macos.defaults.GLOBAL, "NSAutomaticPeriodSubstitutionEnabled"),
        (macos.defaults.GLOBAL, "AppleKeyboardUIMode"),
        (macos.defaults.GLOBAL, "NSNavPanelExpandedStateForSaveMode"),
        (macos.defaults.GLOBAL, "NSNavPanelExpandedStateForSaveMode2"),
        (macos.defaults.GLOBAL, "com.apple.mouse.doubleClickThreshold"),
        ("com.apple.spaces", "spans-displays"),
    ]
    with restored(*keys):
        for on in (True, False):
            macos.keyboard.set_double_space_period(on)
            macos.keyboard.set_full_keyboard_access(on)
            macos.system.set_expanded_save_dialog(on)
            macos.dock.set_separate_spaces_per_display(on)
            assert macos.keyboard.double_space_period() is on and macos.keyboard.full_keyboard_access() is on
            assert macos.system.expanded_save_dialog() is on and macos.dock.separate_spaces_per_display() is on
        macos.mouse.set_double_click_speed(0.8)
        assert macos.mouse.double_click_speed() == 0.8
