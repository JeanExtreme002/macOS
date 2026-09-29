"""Unit tests for :mod:`macos.settings`, over fake settings. They run on any platform."""

import json

import pytest

import macos
from macos import _system, settings


@pytest.fixture
def fake_settings(monkeypatch):
    """Two sections of settings kept in a dict, and the restarts they asked for."""
    values = {"autohide": False, "size": 48, "key_repeat": (0.03, 0.225), "gestures": {"rotate": True, "smart_zoom": False}}
    changes, restarts = [], []

    def setter(name):
        def change(value):
            if _system.restart_later("Dock", lambda: restarts.append("dock")):
                changes.append((name, value))
                values[name] = value
                return
            raise AssertionError("changes must happen in a batch")

        return change

    def unsupported():
        raise macos.NotSupportedError("this Mac has no keyboard backlight")

    table = {
        "dock": {name: settings._Setting(lambda name=name: values[name], setter(name)) for name in ("autohide", "size")},
        "keyboard": {
            "key_repeat": settings._Setting(lambda: values["key_repeat"], setter("key_repeat")),
            "backlight_timeout": settings._Setting(unsupported, setter("backlight_timeout")),
        },
        "trackpad": {"gestures": settings._Setting(lambda: values["gestures"], setter("gestures"))},
    }
    monkeypatch.setattr(settings, "_SETTINGS", table)
    monkeypatch.setattr(settings, "require_macos", lambda: None)
    return values, changes, restarts


def test_export_is_json_and_skips_what_this_mac_lacks(fake_settings):
    exported = settings.export()
    assert exported == {
        "dock": {"autohide": False, "size": 48},
        "keyboard": {"key_repeat": (0.03, 0.225)},
        "trackpad": {"gestures": {"rotate": True, "smart_zoom": False}},
    }
    assert json.loads(json.dumps(exported))["keyboard"]["key_repeat"] == [0.03, 0.225]
    assert "keyboard.backlight_timeout" in settings.names()


def test_apply_changes_only_what_differs_and_restarts_once(fake_settings):
    values, changes, restarts = fake_settings
    saved = json.loads(json.dumps(settings.export()))  # through JSON, as from a file

    assert settings.apply(saved) == []  # the same settings: nothing to do
    changed = settings.apply({"dock": {"autohide": True, "size": 48}, "keyboard": {"key_repeat": [0.05, 0.3]}})
    assert changed == ["dock.autohide", "keyboard.key_repeat"]
    assert changes == [("autohide", True), ("key_repeat", [0.05, 0.3])]
    assert restarts == ["dock"]  # once, at the end


def test_apply_refuses_unknown_names_before_changing_anything(fake_settings):
    _, changes, _ = fake_settings
    with pytest.raises(ValueError, match="unknown settings: dock.colour, printer"):
        settings.apply({"dock": {"autohide": True, "colour": "red"}, "printer": {}})
    assert changes == []


def test_the_real_table_reads_and_changes_existing_functions():
    for section, table in settings._SETTINGS.items():
        for name, setting in table.items():
            assert callable(setting.read) and callable(setting.change), "{}.{}".format(section, name)
    assert len(settings.names()) == len(set(settings.names())) > 80
