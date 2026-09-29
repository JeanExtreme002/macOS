# -*- coding: utf-8 -*-

"""
Save this Mac's settings to a file and apply them to another Mac: dotfiles for macOS.

::

    import json

    json.dump(macos.settings.export(), open("my-mac.json", "w"), indent=2)
    # on the new Mac:
    macos.settings.apply(json.load(open("my-mac.json")))

It covers the keyboard, trackpad, mouse, Dock, Finder, windows, appearance,
screenshots, sounds and system settings this package reads and changes;
the file is plain JSON, to keep in a repository and edit by hand.
"""

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, NamedTuple, Optional

from . import appearance, dock, finder, keyboard, mouse, screen, sound, system, trackpad, windows
from ._system import batched_restarts, require_macos
from .errors import NotSupportedError

__all__ = ["export", "apply", "names"]


class _Setting(NamedTuple):
    read: Callable[[], Any]
    change: Callable[[Any], None]


def _each(change: Callable[..., None]) -> Callable[[Mapping[str, Any]], None]:
    """A setter for a dict of settings, called once per entry: ``change(name, value)``."""

    def apply_all(values: Mapping[str, Any]) -> None:
        for name, value in values.items():
            change(name, value)

    return apply_all


def _hot_corners() -> Dict[str, Dict[str, Optional[str]]]:
    modifiers = dock.hot_corner_modifiers()
    return {corner: {"action": action, "modifier": modifiers[corner]} for corner, action in dock.hot_corners().items()}


def _set_hot_corners(corners: Mapping[str, Mapping[str, Optional[str]]]) -> None:
    for corner, wanted in corners.items():
        dock.set_hot_corner(corner, wanted.get("action"), modifier=wanted.get("modifier"))


def _set_remappings(remappings: Mapping[str, str]) -> None:
    keyboard.clear_remappings()
    for key, target in remappings.items():
        keyboard.remap(key, target)


def _night_shift_schedule() -> Any:
    found = screen.night_shift_schedule()
    if isinstance(found, tuple):
        return [moment.strftime("%H:%M") for moment in found]
    return found


def _portable(folder: Path) -> str:
    """A folder under the home folder as ``~/...``, so it works on a Mac with another user name."""
    home = Path.home()
    try:
        return os.path.join("~", str(folder.relative_to(home))) if folder != home else "~"
    except ValueError:
        return str(folder)


def _set_night_shift_schedule(schedule: Any) -> None:
    screen.set_night_shift_schedule(tuple(schedule) if isinstance(schedule, list) else schedule)


# Section -> name -> how to read and change it, with JSON values.
_SETTINGS: Dict[str, Dict[str, _Setting]] = {
    "keyboard": {
        "key_repeat": _Setting(
            lambda: list(keyboard.key_repeat()), lambda value: keyboard.set_key_repeat(value[0], delay=value[1])
        ),
        "press_and_hold": _Setting(keyboard.press_and_hold, keyboard.set_press_and_hold),
        "standard_function_keys": _Setting(keyboard.standard_function_keys, keyboard.set_standard_function_keys),
        "fn_key_action": _Setting(keyboard.fn_key_action, keyboard.set_fn_key_action),
        "autocorrect": _Setting(keyboard.autocorrect, keyboard.set_autocorrect),
        "smart_quotes": _Setting(keyboard.smart_quotes, keyboard.set_smart_quotes),
        "smart_dashes": _Setting(keyboard.smart_dashes, keyboard.set_smart_dashes),
        "auto_capitalization": _Setting(keyboard.auto_capitalization, keyboard.set_auto_capitalization),
        "double_space_period": _Setting(keyboard.double_space_period, keyboard.set_double_space_period),
        "inline_predictions": _Setting(keyboard.inline_predictions, keyboard.set_inline_predictions),
        "full_keyboard_access": _Setting(keyboard.full_keyboard_access, keyboard.set_full_keyboard_access),
        "system_shortcuts": _Setting(keyboard.system_shortcuts, _each(keyboard.set_system_shortcut)),
        "remappings": _Setting(keyboard.remappings, _set_remappings),
        "backlight_timeout": _Setting(keyboard.backlight_timeout, keyboard.set_backlight_timeout),
    },
    "trackpad": {
        "tap_to_click": _Setting(trackpad.tap_to_click, trackpad.set_tap_to_click),
        "natural_scrolling": _Setting(trackpad.natural_scrolling, trackpad.set_natural_scrolling),
        "tracking_speed": _Setting(trackpad.tracking_speed, trackpad.set_tracking_speed),
        "click_pressure": _Setting(trackpad.click_pressure, trackpad.set_click_pressure),
        "secondary_click": _Setting(trackpad.secondary_click, trackpad.set_secondary_click),
        "three_finger_drag": _Setting(trackpad.three_finger_drag, trackpad.set_three_finger_drag),
        "gestures": _Setting(trackpad.gestures, _each(trackpad.set_gesture)),
    },
    "mouse": {
        "tracking_speed": _Setting(mouse.tracking_speed, mouse.set_tracking_speed),
        "acceleration": _Setting(mouse.acceleration, mouse.set_acceleration),
        "scroll_speed": _Setting(mouse.scroll_speed, mouse.set_scroll_speed),
        "double_click_speed": _Setting(mouse.double_click_speed, mouse.set_double_click_speed),
    },
    "dock": {
        "autohide": _Setting(dock.autohide, dock.set_autohide),
        "autohide_delay": _Setting(dock.autohide_delay, dock.set_autohide_delay),
        "autohide_duration": _Setting(dock.autohide_duration, dock.set_autohide_duration),
        "size": _Setting(dock.size, dock.set_size),
        "position": _Setting(dock.position, dock.set_position),
        "magnification": _Setting(dock.magnification, dock.set_magnification),
        "minimize_effect": _Setting(dock.minimize_effect, dock.set_minimize_effect),
        "minimize_to_app": _Setting(dock.minimize_to_app, dock.set_minimize_to_app),
        "show_recents": _Setting(dock.show_recents, dock.set_show_recents),
        "show_indicators": _Setting(dock.show_indicators, dock.set_show_indicators),
        "dim_hidden_apps": _Setting(dock.dim_hidden_apps, dock.set_dim_hidden_apps),
        "only_open_apps": _Setting(dock.only_open_apps, dock.set_only_open_apps),
        "launch_animation": _Setting(dock.launch_animation, dock.set_launch_animation),
        "hot_corners": _Setting(_hot_corners, _set_hot_corners),
        "group_windows_by_app": _Setting(dock.group_windows_by_app, dock.set_group_windows_by_app),
        "switch_to_space_with_app": _Setting(dock.switch_to_space_with_app, dock.set_switch_to_space_with_app),
        "auto_rearrange_spaces": _Setting(dock.auto_rearrange_spaces, dock.set_auto_rearrange_spaces),
        "separate_spaces_per_display": _Setting(dock.separate_spaces_per_display, dock.set_separate_spaces_per_display),
    },
    "finder": {
        "show_hidden_files": _Setting(finder.show_hidden_files, finder.set_show_hidden_files),
        "show_extensions": _Setting(finder.show_extensions, finder.set_show_extensions),
        "show_path_bar": _Setting(finder.show_path_bar, finder.set_show_path_bar),
        "show_status_bar": _Setting(finder.show_status_bar, finder.set_show_status_bar),
        "show_full_path_in_title": _Setting(finder.show_full_path_in_title, finder.set_show_full_path_in_title),
        "show_library_folder": _Setting(finder.show_library_folder, finder.set_show_library_folder),
        "show_desktop_icons": _Setting(finder.show_desktop_icons, finder.set_show_desktop_icons),
        "default_view": _Setting(finder.default_view, finder.set_default_view),
        "new_window_folder": _Setting(lambda: _portable(finder.new_window_folder()), finder.set_new_window_folder),
        "search_scope": _Setting(finder.search_scope, finder.set_search_scope),
        "folders_first": _Setting(finder.folders_first, finder.set_folders_first),
        "extension_change_warning": _Setting(finder.extension_change_warning, finder.set_extension_change_warning),
        "remove_old_trash_items": _Setting(finder.remove_old_trash_items, finder.set_remove_old_trash_items),
        "quit_menu": _Setting(finder.quit_menu, finder.set_quit_menu),
        "drives_on_desktop": _Setting(finder.drives_on_desktop, lambda value: finder.set_show_drives_on_desktop(**value)),
        "desktop_view": _Setting(finder.desktop_view, lambda value: finder.set_desktop_view(**value)),
    },
    "windows": {
        "double_click_title_bar": _Setting(windows.double_click_title_bar, windows.set_double_click_title_bar),
        "tiling": _Setting(windows.tiling, windows.set_tiling),
        "click_wallpaper_to_show_desktop": _Setting(
            windows.click_wallpaper_to_show_desktop, windows.set_click_wallpaper_to_show_desktop
        ),
        "animations": _Setting(windows.animations, windows.set_animations),
    },
    "appearance": {
        "auto_mode": _Setting(appearance.is_auto, appearance.set_auto_mode),
        "hide_menu_bar": _Setting(appearance.menu_bar_hidden, appearance.set_hide_menu_bar),
        "scroll_bars": _Setting(appearance.scroll_bars, appearance.set_scroll_bars),
        "font_smoothing": _Setting(appearance.font_smoothing, appearance.set_font_smoothing),
    },
    "screen": {
        "screenshot_folder": _Setting(lambda: _portable(screen.screenshot_folder()), screen.set_screenshot_folder),
        "screenshot_format": _Setting(screen.screenshot_format, screen.set_screenshot_format),
        "screenshot_name": _Setting(screen.screenshot_name, screen.set_screenshot_name),
        "screenshot_target": _Setting(screen.screenshot_target, screen.set_screenshot_target),
        "screenshot_shadow": _Setting(screen.screenshot_shadow, screen.set_screenshot_shadow),
        "screenshot_thumbnail": _Setting(screen.screenshot_thumbnail, screen.set_screenshot_thumbnail),
        "screensaver_delay": _Setting(screen.screensaver_delay, screen.set_screensaver_delay),
        "night_shift_schedule": _Setting(_night_shift_schedule, _set_night_shift_schedule),
        "night_shift_strength": _Setting(screen.night_shift_strength, screen.set_night_shift_strength),
    },
    "sound": {
        "alert_sound": _Setting(sound.alert_sound, sound.set_alert_sound),
        "alert_volume": _Setting(sound.alert_volume, sound.set_alert_volume),
        "ui_sounds": _Setting(sound.ui_sounds, sound.set_ui_sounds),
    },
    "system": {
        "clock_format": _Setting(system.clock_format, lambda value: system.set_clock_format(**value)),
        "menu_bar_items": _Setting(system.menu_bar_items, lambda value: system.set_menu_bar_items(**value)),
        "menu_bar_spacing": _Setting(system.menu_bar_spacing, system.set_menu_bar_spacing),
        "battery_percentage": _Setting(system.battery_percentage_shown, system.set_show_battery_percentage),
        "measurement_units": _Setting(system.measurement_units, system.set_measurement_units),
        "temperature_unit": _Setting(system.temperature_unit, system.set_temperature_unit),
        "keep_windows_on_quit": _Setting(system.keep_windows_on_quit, system.set_keep_windows_on_quit),
        "save_to_icloud_by_default": _Setting(system.save_to_icloud_by_default, system.set_save_to_icloud_by_default),
        "expanded_save_dialog": _Setting(system.expanded_save_dialog, system.set_expanded_save_dialog),
        "ds_store_on_network": _Setting(system.ds_store_on_network, system.set_ds_store_on_network),
        "ds_store_on_usb": _Setting(system.ds_store_on_usb, system.set_ds_store_on_usb),
        "open_photos_on_device_connect": _Setting(
            system.open_photos_on_device_connect, system.set_open_photos_on_device_connect
        ),
    },
}


def names() -> List[str]:
    """Every setting :func:`export` saves, as ``"section.name"``: ``["keyboard.key_repeat", ...]``."""
    return ["{}.{}".format(section, name) for section, settings in _SETTINGS.items() for name in settings]


def export() -> Dict[str, Dict[str, Any]]:
    """
    This Mac's settings, as JSON-ready values by section: ``{"dock": {"autohide": True, ...}, ...}``.

    Settings this Mac doesn't have (a keyboard backlight, Night Shift...) are left out.
    """
    require_macos()
    found: Dict[str, Dict[str, Any]] = {}
    for section, settings in _SETTINGS.items():
        for name, setting in settings.items():
            try:
                found.setdefault(section, {})[name] = setting.read()
            except NotSupportedError:
                continue  # this Mac lacks it
    return found


def _normalized(value: Any) -> Any:
    """Compare values as JSON gives them back: tuples as lists."""
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalized(item) for key, item in value.items()}
    return value


def apply(settings: Mapping[str, Mapping[str, Any]]) -> List[str]:
    """
    Change this Mac's settings to those of ``settings``, as :func:`export` gives them, and return those that changed.

    ::

        macos.settings.apply({"dock": {"autohide": True, "size": 48}, "finder": {"show_extensions": True}})

    Any part of an export works: settings left out stay as they are. Those
    already as wanted aren't touched, and the Dock and Finder restart once
    at the end. Unknown names raise :class:`ValueError` before anything
    changes, and settings this Mac lacks (a keyboard backlight, Night Shift...)
    are skipped. Returns ``["dock.autohide", ...]``.
    """
    require_macos()
    unknown = []
    for section, values in settings.items():
        if section not in _SETTINGS:
            unknown.append(section)
        else:
            unknown.extend("{}.{}".format(section, name) for name in values if name not in _SETTINGS[section])
    if unknown:
        raise ValueError("unknown settings: {}; see macos.settings.names()".format(", ".join(sorted(set(unknown)))))
    changed = []
    with batched_restarts():
        for section, values in settings.items():
            for name, value in values.items():
                setting = _SETTINGS[section][name]
                try:
                    current = _normalized(setting.read())
                except NotSupportedError:
                    continue  # this Mac lacks it (a keyboard backlight, Night Shift...): the others still apply
                if current == _normalized(value):
                    continue
                try:
                    setting.change(value)
                except NotSupportedError:
                    continue  # this Mac lacks it (a keyboard backlight, Night Shift...): the others still apply
                changed.append("{}.{}".format(section, name))
    return changed
