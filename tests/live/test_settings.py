"""Tests of the keyboard, trackpad, mouse, Dock, Finder, appearance, screen and system settings. Skipped outside macOS."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

import macos
from tests.helpers import SETTINGS

restored = macos.defaults.restored
G = macos.defaults.GLOBAL


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


# --- v1.14 ------------------------------------------------------------------


def test_v114_settings_are_read():
    keyboard, trackpad, dock, finder, screen, system = (
        macos.keyboard, macos.trackpad, macos.dock, macos.finder, macos.screen, macos.system
    )
    assert keyboard.fn_key_action() in (None, "emoji", "input_source", "dictation")
    assert isinstance(keyboard.inline_predictions(), bool)
    assert set(keyboard.system_shortcuts()) == set(keyboard.SYSTEM_SHORTCUTS)
    assert isinstance(keyboard.app_shortcuts(), dict)
    assert trackpad.click_pressure() in ("light", "medium", "firm")
    assert set(trackpad.gestures()) == set(trackpad.GESTURES)
    assert isinstance(macos.mouse.acceleration(), bool)
    for setting in (dock.dim_hidden_apps, dock.only_open_apps, dock.launch_animation, dock.group_windows_by_app,
                    dock.switch_to_space_with_app, finder.quit_menu, macos.windows.animations,
                    macos.appearance.font_smoothing, macos.sound.ui_sounds, system.open_photos_on_device_connect):
        assert isinstance(setting(), bool), setting.__name__
    assert set(dock.hot_corner_modifiers()) == set(dock.hot_corners())
    assert all(folder.view in ("automatic", "fan", "grid", "list") for folder in dock.folders())
    assert 16 <= finder.desktop_view()["icon_size"] <= 128
    assert 0 <= macos.sound.alert_volume() <= 1
    assert screen.screenshot_target() in ("file", "clipboard", "preview", "mail", "messages")
    assert system.measurement_units() in ("metric", "us") and system.temperature_unit() in ("celsius", "fahrenheit")
    assert set(system.menu_bar_items()) == set(system.MENU_BAR_ITEMS)
    status = system.security_status()
    assert all(value in (True, False, None) for value in vars(status).values())
    current = screen.display_mode()
    assert current in screen.display_modes() and current.width > 0
    assert isinstance(macos.printer.printers(), list)


def test_settings_export_is_json():
    exported = macos.settings.export()
    assert json.loads(json.dumps(exported)).keys() == exported.keys()
    assert {"dock", "finder", "keyboard"} <= set(exported)


@SETTINGS
def test_settings_apply_of_an_export_changes_nothing():
    assert macos.settings.apply(json.loads(json.dumps(macos.settings.export()))) == []


@SETTINGS
def test_v114_quiet_settings_round_trip():
    keys = [
        ("com.apple.HIToolbox", "AppleFnUsageType"),
        (G, "NSAutomaticInlinePredictionEnabled"),
        (G, "NSAutomaticWindowAnimationsEnabled"),
        (G, "AppleFontSmoothing"),
        (G, "AppleMetricUnits"),
        (G, "AppleMeasurementUnits"),
        (G, "AppleTemperatureUnit"),
        (G, "com.apple.sound.beep.volume"),
        ("com.apple.systemsound", "com.apple.sound.uiaudio.enabled"),
        ("com.apple.symbolichotkeys", "AppleSymbolicHotKeys"),
    ]
    with restored(*keys), restored(("com.apple.ImageCapture", "disableHotPlug"), current_host=True):
        macos.keyboard.set_fn_key_action("dictation")
        assert macos.keyboard.fn_key_action() == "dictation"
        macos.keyboard.set_inline_predictions(False)
        macos.windows.set_animations(False)
        macos.appearance.set_font_smoothing(False)
        assert not macos.keyboard.inline_predictions() and not macos.windows.animations()
        assert not macos.appearance.font_smoothing()
        for units, unit in (("us", "fahrenheit"), ("metric", "celsius")):
            macos.system.set_measurement_units(units)
            macos.system.set_temperature_unit(unit)
            assert (macos.system.measurement_units(), macos.system.temperature_unit()) == (units, unit)
        macos.sound.set_alert_volume(0.25)
        macos.sound.set_ui_sounds(False)
        assert macos.sound.alert_volume() == 0.25 and not macos.sound.ui_sounds()
        macos.system.set_open_photos_on_device_connect(False)
        assert not macos.system.open_photos_on_device_connect()
        macos.keyboard.set_system_shortcut("move_left_a_space", False)
        assert not macos.keyboard.system_shortcuts()["move_left_a_space"]


@SETTINGS
def test_app_shortcut_round_trip():
    domain = "com.github.pymacos.test"
    try:
        macos.keyboard.set_app_shortcut(domain, "File > Export…", "cmd+shift+e")
        assert macos.defaults.read(domain, "NSUserKeyEquivalents") == {"\x1bFile\x1bExport…": "@$e"}
        assert macos.keyboard.app_shortcuts(domain) == {"File > Export…": "cmd+shift+e"}
        macos.keyboard.set_app_shortcut(domain, "File > Export…", None)
        assert macos.keyboard.app_shortcuts(domain) == {}
    finally:
        subprocess.run(["defaults", "delete", domain], capture_output=True)  # the whole test domain, through cfprefsd
        Path("~/Library/Preferences/{}.plist".format(domain)).expanduser().unlink(missing_ok=True)  # left empty


@SETTINGS
def test_dock_and_finder_v114_round_trip(tmp_path):
    folder = tmp_path / "Stack"
    folder.mkdir()
    try:
        with restored("com.apple.dock"):
            macos.dock.set_dim_hidden_apps(not macos.dock.dim_hidden_apps())
            macos.dock.add_folder(folder, view="grid")
            assert any(found.path == folder.resolve() and found.view == "grid" for found in macos.dock.folders())
            assert macos.dock.remove_folder(folder)
        with restored(("com.apple.finder", "DesktopViewSettings")):
            size = macos.finder.desktop_view()["icon_size"]
            macos.finder.set_desktop_view(icon_size=48 if size != 48 else 64)
            assert macos.finder.desktop_view()["icon_size"] == (48 if size != 48 else 64)
    finally:
        macos.dock.restart()
        macos.finder.restart()


@SETTINGS
def test_display_mode_round_trip():
    before = macos.screen.display_mode()
    others = [mode for mode in macos.screen.display_modes() if (mode.width, mode.height) != (before.width, before.height)]
    try:
        assert macos.screen.set_display_mode(before.width, before.height, hidpi=before.hidpi).width == before.width
        if others:
            chosen = macos.screen.set_display_mode(others[-1].width, others[-1].height)
            assert (macos.screen.display_mode().width, macos.screen.display_mode().height) == (chosen.width, chosen.height)
    finally:
        macos.screen.set_display_mode(before.width, before.height, refresh_rate=before.refresh_rate or None, hidpi=before.hidpi)
    assert macos.screen.display_mode() == before
    macos.screen.stop_mirroring()  # nothing to stop: no error


@SETTINGS
def test_printing_to_a_test_queue():
    ppd = (
        "/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/PrintCore.framework"
        "/Versions/A/Resources/Generic.ppd"
    )
    queue = "pymacos_test"
    command = ["lpadmin", "-p", queue, "-E", "-v", "socket://127.0.0.1:9", "-P", ppd, "-o", "printer-is-shared=false"]
    added = subprocess.run(command, capture_output=True, text=True)
    if added.returncode != 0:
        pytest.skip("can't add a test printer here: " + added.stderr.strip())
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as file:
        file.write("pymacos test\n")
    try:
        assert queue in [found.name for found in macos.printer.printers()]
        job = macos.printer.print_file(file.name, queue, copies=2, title="pymacos test")
        assert job.printer == queue and any(found.id == job.id for found in macos.printer.jobs(queue))
        job.cancel()
        assert not any(found.id == job.id for found in macos.printer.jobs(queue))
    finally:
        os.unlink(file.name)
        subprocess.run(["lpadmin", "-x", queue], capture_output=True)
