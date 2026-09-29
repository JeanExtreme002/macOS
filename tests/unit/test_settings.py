"""Unit tests for the settings of the keyboard, trackpad, mouse, Dock, Finder, appearance, screen and system."""

from pathlib import Path

import pytest

import macos
from macos import _system, appearance, defaults, dock, finder, screen, system, trackpad


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
