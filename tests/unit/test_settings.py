"""Unit tests for the settings of the keyboard, trackpad, mouse, Dock, Finder, appearance, screen and system."""

from pathlib import Path

import pytest

import macos
from macos import _system, appearance, defaults, dock, finder, screen, system, trackpad, windows


@pytest.fixture
def prefs(monkeypatch):
    """The preferences in a dict keyed by (domain, key, current_host), and what was applied or restarted."""
    store, done = {}, []

    def read(domain, key=None, *, default=None, current_host=False):
        return store.get((domain, key, current_host), default)

    def write(domain, key, value, *, current_host=False):
        store[(domain, key, current_host)] = value

    def delete(domain, key, *, current_host=False):
        return store.pop((domain, key, current_host), None) is not None

    monkeypatch.setattr(defaults, "read", read)
    monkeypatch.setattr(defaults, "write", write)
    monkeypatch.setattr(defaults, "delete", delete)
    monkeypatch.setattr(_system, "apply_input_settings", lambda: done.append("input"))
    monkeypatch.setattr(trackpad, "apply_input_settings", lambda: done.append("input"))
    monkeypatch.setattr(dock, "restart", lambda: done.append("dock"))
    monkeypatch.setattr(finder, "restart", lambda: done.append("finder"))
    monkeypatch.setattr(appearance, "_announce", lambda *names: done.append(names))
    monkeypatch.setattr(screen, "_apply_capture_settings", lambda: done.append("capture"))
    for module in (system, windows):
        monkeypatch.setattr(module, "_run", lambda args: done.append(args[-1]))
    return store, done


G = defaults.GLOBAL


def test_keyboard_settings(prefs):
    store, done = prefs

    assert macos.keyboard.key_repeat() == (0.09, 0.375)
    assert macos.keyboard.press_and_hold() and macos.keyboard.autocorrect()
    macos.keyboard.set_key_repeat(0.03, delay=0.225)
    macos.keyboard.set_press_and_hold(False)
    macos.keyboard.set_standard_function_keys(True)
    macos.keyboard.set_autocorrect(False)
    macos.keyboard.set_smart_quotes(False)
    macos.keyboard.set_smart_dashes(False)
    assert store == {
        (G, "KeyRepeat", False): 2,
        (G, "InitialKeyRepeat", False): 15,
        (G, "ApplePressAndHoldEnabled", False): False,
        (G, "com.apple.keyboard.fnState", False): True,
        (G, "NSAutomaticSpellingCorrectionEnabled", False): False,
        (G, "WebAutomaticSpellingCorrectionEnabled", False): False,
        (G, "NSAutomaticQuoteSubstitutionEnabled", False): False,
        (G, "NSAutomaticDashSubstitutionEnabled", False): False,
    }
    assert macos.keyboard.key_repeat() == (0.03, 0.225)
    assert macos.keyboard.standard_function_keys() and not macos.keyboard.smart_quotes()
    assert done == ["input"]  # only the function keys apply at once

    macos.keyboard.set_key_repeat(delay=0.5)
    assert store[(G, "KeyRepeat", False)] == 2 and store[(G, "InitialKeyRepeat", False)] == 33
    with pytest.raises(ValueError, match="give interval, delay"):
        macos.keyboard.set_key_repeat()
    with pytest.raises(ValueError, match="positive"):
        macos.keyboard.set_key_repeat(0)


def test_trackpad_and_mouse_settings(prefs):
    store, done = prefs

    assert not trackpad.tap_to_click() and trackpad.natural_scrolling()
    trackpad.set_tap_to_click()
    trackpad.set_natural_scrolling(False)
    trackpad.set_tracking_speed(0.5)
    macos.mouse.set_tracking_speed(1)
    assert store == {
        ("com.apple.AppleMultitouchTrackpad", "Clicking", False): True,
        ("com.apple.driver.AppleBluetoothMultitouch.trackpad", "Clicking", False): True,
        (G, "com.apple.mouse.tapBehavior", False): 1,
        (G, "com.apple.swipescrolldirection", False): False,
        (G, "com.apple.trackpad.scaling", False): 1.5,
        (G, "com.apple.mouse.scaling", False): 3.0,
    }
    assert (trackpad.tracking_speed(), macos.mouse.tracking_speed()) == (0.5, 1.0)
    assert done == ["input"] * 4
    for speed in (-0.1, 1.1):
        with pytest.raises(ValueError, match="0.0 to 1.0"):
            trackpad.set_tracking_speed(speed)
        with pytest.raises(ValueError, match="0.0 to 1.0"):
            macos.mouse.set_tracking_speed(speed)


def test_dock_more_settings(prefs):
    store, done = prefs
    D = "com.apple.dock"

    assert dock.hot_corners() == dict.fromkeys(("top_left", "top_right", "bottom_left", "bottom_right"))
    dock.set_hot_corner("bottom_right", "lock_screen")
    assert store[(D, "wvous-br-corner", False)] == 13 and store[(D, "wvous-br-modifier", False)] == 0
    assert dock.hot_corners()["bottom_right"] == "lock_screen"
    dock.set_hot_corner("bottom_right", None)
    assert store[(D, "wvous-br-corner", False)] == 1

    dock.set_autohide_delay(0)
    dock.set_magnification(96)
    dock.set_show_recents(False)
    dock.set_minimize_effect("scale")
    assert (dock.autohide_delay(), dock.magnification(), dock.show_recents(), dock.minimize_effect()) == (0.0, 96, False, "scale")
    dock.set_magnification(None)
    assert dock.magnification() is None
    assert done == ["dock"] * 7

    with pytest.raises(ValueError, match="corner must be one of"):
        dock.set_hot_corner("middle", None)
    with pytest.raises(ValueError, match="action must be one of"):
        dock.set_hot_corner("top_left", "explode")
    with pytest.raises(ValueError, match="not be negative"):
        dock.set_autohide_delay(-1)
    with pytest.raises(ValueError, match="16 to 128"):
        dock.set_magnification(200)
    with pytest.raises(ValueError, match="'genie' or 'scale'"):
        dock.set_minimize_effect("suck")


def test_finder_more_settings(prefs, fake_run, tmp_path):
    store, done = prefs
    F = "com.apple.finder"

    assert (finder.default_view(), finder.search_scope(), finder.new_window_folder()) == ("icons", "this_mac", Path.home())
    finder.set_show_desktop_icons(False)
    finder.set_default_view("columns")
    finder.set_search_scope("current_folder")
    finder.set_show_full_path_in_title(True)
    finder.set_new_window_folder(tmp_path)
    assert store[(F, "CreateDesktop", False)] is False
    assert store[(F, "FXPreferredViewStyle", False)] == "clmv"
    assert store[(F, "FXDefaultSearchScope", False)] == "SCcf"
    assert store[(F, "_FXShowPosixPathInTitle", False)] is True
    assert store[(F, "NewWindowTarget", False)] == "PfLo"
    assert (finder.default_view(), finder.search_scope(), finder.new_window_folder()) == (
        "columns",
        "current_folder",
        tmp_path.resolve(),
    )
    assert done == ["finder"] * 5

    finder.set_show_library_folder(True)
    assert fake_run.args == ["chflags", "nohidden", str(Path.home() / "Library")]

    with pytest.raises(ValueError, match="view must be one of"):
        finder.set_default_view("cover_flow")
    with pytest.raises(ValueError, match="scope must be one of"):
        finder.set_search_scope("everywhere")
    with pytest.raises(FileNotFoundError):
        finder.set_new_window_folder(tmp_path / "missing")


def test_appearance_settings(prefs):
    store, done = prefs

    appearance.set_accent_color("purple")
    appearance.set_auto_mode(True)
    appearance.set_hide_menu_bar(True)
    assert store == {
        (G, "AppleAccentColor", False): 5,
        (G, "AppleInterfaceStyleSwitchesAutomatically", False): True,
        (G, "_HIHideMenuBar", False): True,
    }
    assert appearance.menu_bar_hidden()
    appearance.set_accent_color("multicolor")  # the key left unset
    assert (G, "AppleAccentColor", False) not in store
    assert done[0] == ("AppleColorPreferencesChangedNotification", "AppleAquaColorVariantChanged")
    assert len(done) == 4
    with pytest.raises(ValueError, match="name must be one of"):
        appearance.set_accent_color("teal")


def test_screen_and_system_settings(prefs, monkeypatch):
    store, _ = prefs
    commands = []
    monkeypatch.setattr(system, "_run", lambda args: commands.append(args))

    assert screen.screensaver_delay() == 20.0
    screen.set_screensaver_delay(5)
    assert store[("com.apple.screensaver", "idleTime", True)] == 300 and screen.screensaver_delay() == 5.0
    screen.set_screensaver_delay(None)
    assert store[("com.apple.screensaver", "idleTime", True)] == 0 and screen.screensaver_delay() is None
    screen.set_screensaver_delay(0.001)  # not 0 seconds, which would mean never
    assert store[("com.apple.screensaver", "idleTime", True)] == 1
    with pytest.raises(ValueError, match="positive"):
        screen.set_screensaver_delay(0)

    assert system.ds_store_on_network() and system.ds_store_on_usb() and not system.keep_windows_on_quit()
    system.set_ds_store_on_network(False)
    system.set_ds_store_on_usb(False)
    system.set_keep_windows_on_quit(True)
    system.set_show_battery_percentage(True)
    assert store[("com.apple.desktopservices", "DSDontWriteNetworkStores", False)] is True
    assert store[("com.apple.desktopservices", "DSDontWriteUSBStores", False)] is True
    assert store[(G, "NSQuitAlwaysKeepsWindows", False)] is True
    assert store[("com.apple.controlcenter", "BatteryShowPercentage", True)] is True
    assert not system.ds_store_on_network() and system.keep_windows_on_quit() and system.battery_percentage_shown()
    assert commands == [["killall", "ControlCenter"]]


def test_auth_required(monkeypatch):
    answers = []
    monkeypatch.setattr(macos.auth, "confirm", lambda reason, only_touch_id=False: answers.append((reason, only_touch_id)) or ok)

    @macos.auth.required("deploy", only_touch_id=True)
    def deploy(target):
        """Deploy it."""
        return "deployed " + target

    ok = True
    assert deploy("prod") == "deployed prod"
    assert (deploy.__name__, deploy.__doc__) == ("deploy", "Deploy it.")
    ok = False
    with pytest.raises(macos.PermissionDeniedError, match="deploy"):
        deploy("prod")
    assert answers == [("deploy", True)] * 2
    with pytest.raises(ValueError, match="reason must not be empty"):
        macos.auth.required(" ")


def test_more_keyboard_settings(prefs):
    store, _ = prefs

    assert macos.keyboard.auto_capitalization() and macos.keyboard.double_space_period()
    assert not macos.keyboard.full_keyboard_access()
    macos.keyboard.set_auto_capitalization(False)
    macos.keyboard.set_double_space_period(False)
    macos.keyboard.set_full_keyboard_access(True)
    assert store == {
        (G, "NSAutomaticCapitalizationEnabled", False): False,
        (G, "NSAutomaticPeriodSubstitutionEnabled", False): False,
        (G, "AppleKeyboardUIMode", False): 2,
    }
    assert macos.keyboard.full_keyboard_access()
    store[(G, "AppleKeyboardUIMode", False)] = 3  # as older macOS wrote it
    assert macos.keyboard.full_keyboard_access()
    macos.keyboard.set_full_keyboard_access(False)
    assert store[(G, "AppleKeyboardUIMode", False)] == 1  # the other bit kept
    macos.keyboard.set_full_keyboard_access(True)
    assert store[(G, "AppleKeyboardUIMode", False)] == 3


def test_remap(monkeypatch):
    state = {"mappings": []}

    def hidutil(args):
        if args[2] == "--set":
            import json

            state["mappings"] = json.loads(args[3])["UserKeyMapping"]
            return ""
        blocks = "".join(
            "    {{\n        HIDKeyboardModifierMappingDst = {};\n        HIDKeyboardModifierMappingSrc = {};\n    }}\n".format(
                pair["HIDKeyboardModifierMappingDst"], pair["HIDKeyboardModifierMappingSrc"]
            )
            for pair in state["mappings"]
        )
        return "(\n{})\n".format(blocks) if state["mappings"] else "(null)\n"

    monkeypatch.setattr(_system, "run", hidutil)

    assert macos.keyboard.remappings() == {}
    macos.keyboard.remap("Caps_Lock", "esc")
    assert state["mappings"] == [{"HIDKeyboardModifierMappingSrc": 0x700000039, "HIDKeyboardModifierMappingDst": 0x700000029}]
    macos.keyboard.remap("right_option", "control")
    macos.keyboard.remap("fn", "f13")
    assert macos.keyboard.remappings() == {"caps_lock": "escape", "right_option": "ctrl", "fn": "f13"}
    macos.keyboard.remap("caps_lock", None)
    assert macos.keyboard.remappings() == {"right_option": "ctrl", "fn": "f13"}
    macos.keyboard.clear_remappings()
    assert macos.keyboard.remappings() == {}
    assert (macos.keyboard._HID_CODES["a"], macos.keyboard._HID_CODES["1"], macos.keyboard._HID_CODES["0"]) == (
        0x700000004,
        0x70000001E,
        0x700000027,
    )
    assert (macos.keyboard._HID_CODES["f12"], macos.keyboard._HID_CODES["f13"]) == (0x700000045, 0x700000068)
    with pytest.raises(ValueError, match="can't remap 'hyper'"):
        macos.keyboard.remap("hyper", "escape")


def test_more_trackpad_and_mouse_settings(prefs):
    store, done = prefs
    T = "com.apple.AppleMultitouchTrackpad"

    assert not trackpad.three_finger_drag() and trackpad.secondary_click() == "two_fingers"
    trackpad.set_three_finger_drag()
    trackpad.set_secondary_click("bottom_right")
    assert store[(T, "TrackpadThreeFingerDrag", False)] is True
    assert store[("com.apple.driver.AppleBluetoothMultitouch.trackpad", "TrackpadCornerSecondaryClick", False)] == 2
    assert trackpad.three_finger_drag() and trackpad.secondary_click() == "bottom_right"
    trackpad.set_secondary_click(None)
    assert trackpad.secondary_click() is None
    with pytest.raises(ValueError, match="how must be"):
        trackpad.set_secondary_click("three_fingers")

    assert (macos.mouse.scroll_speed(), macos.mouse.double_click_speed()) == (0.3125, 0.5)
    macos.mouse.set_scroll_speed(1)
    macos.mouse.set_double_click_speed(0.3)
    assert (macos.mouse.scroll_speed(), macos.mouse.double_click_speed()) == (1.0, 0.3)
    with pytest.raises(ValueError, match="not be negative"):
        macos.mouse.set_scroll_speed(-1)
    with pytest.raises(ValueError, match="positive"):
        macos.mouse.set_double_click_speed(0)
    assert done.count("input") == 4


def test_dock_spacers_and_spaces(prefs):
    store, done = prefs
    D = "com.apple.dock"

    def app(name, path):
        data = {"file-data": {"_CFURLString": "file://{}/".format(path)}, "file-label": name}
        return {"tile-data": data, "tile-type": "file-tile"}

    safari, mail = app("Safari", "/Applications/Safari.app"), app("Mail", "/System/Applications/Mail.app")
    store[(D, "persistent-apps", False)] = [safari, mail]

    dock.add_spacer(index=1)
    dock.add_spacer(small=True)
    assert [tile["tile-type"] for tile in store[(D, "persistent-apps", False)]] == [
        "file-tile",
        "spacer-tile",
        "file-tile",
        "small-spacer-tile",
    ]
    assert [app.name for app in dock.apps()] == ["Safari", "Mail"]
    assert dock.remove_spacers() == 2 and dock.remove_spacers() == 0
    assert store[(D, "persistent-apps", False)] == [safari, mail]

    assert dock.show_indicators() and not dock.minimize_to_app() and dock.autohide_duration() is None
    dock.set_show_indicators(False)
    dock.set_minimize_to_app(True)
    dock.set_autohide_duration(0)
    dock.set_auto_rearrange_spaces(False)
    dock.set_separate_spaces_per_display(False)
    assert (dock.show_indicators(), dock.minimize_to_app(), dock.autohide_duration()) == (False, True, 0.0)
    assert not dock.auto_rearrange_spaces() and not dock.separate_spaces_per_display()
    assert store[("com.apple.spaces", "spans-displays", False)] is True
    dock.set_autohide_duration(None)
    assert (D, "autohide-time-modifier", False) not in store
    assert done.count("dock") == 8  # the spaces per display wait for the next login
    with pytest.raises(ValueError, match="not be negative"):
        dock.set_autohide_duration(-1)


def test_more_finder_settings(prefs):
    store, done = prefs
    F = "com.apple.finder"

    assert not finder.folders_first() and finder.extension_change_warning() and not finder.remove_old_trash_items()
    finder.set_folders_first()
    finder.set_extension_change_warning(False)
    finder.set_remove_old_trash_items()
    assert store[(F, "_FXSortFoldersFirst", False)] and store[(F, "_FXSortFoldersFirstOnDesktop", False)]
    assert finder.folders_first() and not finder.extension_change_warning() and finder.remove_old_trash_items()

    assert finder.drives_on_desktop() == {"internal": False, "external": True, "removable": True, "servers": False}
    finder.set_show_drives_on_desktop(external=False, servers=True)
    assert finder.drives_on_desktop() == {"internal": False, "external": False, "removable": True, "servers": True}
    assert (F, "ShowHardDrivesOnDesktop", False) not in store
    assert done == ["finder"] * 4
    with pytest.raises(ValueError, match="say which disks"):
        finder.set_show_drives_on_desktop()


def test_window_appearance_screen_and_system_settings(prefs):
    store, done = prefs
    W = "com.apple.WindowManager"

    assert windows.double_click_title_bar() == "zoom" and windows.tiling() and windows.click_wallpaper_to_show_desktop()
    windows.set_double_click_title_bar("minimize")
    windows.set_tiling(False)
    windows.set_click_wallpaper_to_show_desktop(False)
    assert store[(G, "AppleActionOnDoubleClick", False)] == "Minimize"
    assert store[(W, "EnableTilingByEdgeDrag", False)] is False and store[(W, "EnableTopTilingByEdgeDrag", False)] is False
    assert windows.double_click_title_bar() == "minimize" and not windows.tiling()
    assert not windows.click_wallpaper_to_show_desktop()
    windows.set_double_click_title_bar(None)
    assert windows.double_click_title_bar() is None
    with pytest.raises(ValueError, match="action must be"):
        windows.set_double_click_title_bar("maximize")

    assert appearance.scroll_bars() == "automatic"
    appearance.set_scroll_bars("always")
    assert store[(G, "AppleShowScrollBars", False)] == "Always" and appearance.scroll_bars() == "always"
    with pytest.raises(ValueError, match="when must be"):
        appearance.set_scroll_bars("never")

    assert screen.screenshot_thumbnail()
    screen.set_screenshot_thumbnail(False)
    assert not screen.screenshot_thumbnail()

    assert system.save_to_icloud_by_default() and not system.expanded_save_dialog()
    system.set_save_to_icloud_by_default(False)
    system.set_expanded_save_dialog()
    assert store[(G, "NSNavPanelExpandedStateForSaveMode2", False)] is True
    assert not system.save_to_icloud_by_default() and system.expanded_save_dialog()

    assert system.clock_format() == {"seconds": False, "day_of_week": True, "am_pm": True, "analog": False, "date": "auto"}
    system.set_clock_format(seconds=True, date="never")
    assert system.clock_format()["seconds"] and system.clock_format()["date"] == "never"
    assert store[("com.apple.menuextra.clock", "ShowDate", False)] == 2
    with pytest.raises(ValueError, match="say what to change"):
        system.set_clock_format()
    with pytest.raises(ValueError, match="date must be"):
        system.set_clock_format(date="sometimes")

    assert done == ["WindowManager", "WindowManager", ("AppleShowScrollBarsSettingChanged",), "capture", "ControlCenter"]
