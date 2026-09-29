"""Unit tests for :mod:`macos.system`. They run on any platform."""

from pathlib import Path

import pytest

import macos


def test_system_commands(fake_run):
    fake_run.stdout = "24G90\n"
    assert macos.system.build() == "24G90"
    assert fake_run.args == ["sw_vers", "-buildVersion"]

    fake_run.stdout = "My Mac\n"
    assert macos.system.computer_name() == "My Mac"
    assert fake_run.args == ["scutil", "--get", "ComputerName"]


def test_eject(fake_run, monkeypatch):
    backup = macos.system.Volume("Backup", Path("/Volumes/Backup"), 10, 5, False, True, True)
    root = macos.system.Volume("Macintosh HD", Path("/"), 10, 5, True, False, False)
    monkeypatch.setattr(macos.system, "volumes", lambda: [root, backup])

    macos.system.eject("Backup")
    assert fake_run.args == ["diskutil", "eject", "/Volumes/Backup"]
    macos.system.eject("/Volumes/Backup/")
    assert fake_run.args[-1] == "/Volumes/Backup"
    macos.system.eject(backup)
    assert fake_run.args[-1] == "/Volumes/Backup"

    with pytest.raises(ValueError, match="startup disk"):
        macos.system.eject("Macintosh HD")
    with pytest.raises(ValueError, match="no mounted volume"):
        macos.system.eject("Nope")


def test_eject_refuses_folders_and_hidden_system_volumes(fake_run, monkeypatch, tmp_path):
    monkeypatch.setattr(macos.system, "volumes", lambda: [])

    for target in (tmp_path, "/System/Volumes/Data"):
        with pytest.raises(ValueError, match="no mounted volume"):
            macos.system.eject(target)
    assert fake_run.calls == []


def test_eject_refuses_ambiguous_names_and_fixed_volumes(fake_run, monkeypatch):
    first = macos.system.Volume("Untitled", Path("/Volumes/Untitled"), 10, 5, False, True, True)
    second = macos.system.Volume("Untitled", Path("/Volumes/Untitled 1"), 10, 5, False, True, True)
    fixed = macos.system.Volume("Data", Path("/Volumes/Data"), 10, 5, True, False, False)
    monkeypatch.setattr(macos.system, "volumes", lambda: [first, second, fixed])

    with pytest.raises(ValueError, match="more than one volume"):
        macos.system.eject("Untitled")
    macos.system.eject("/Volumes/Untitled 1")
    assert fake_run.args == ["diskutil", "eject", "/Volumes/Untitled 1"]

    with pytest.raises(ValueError, match="can't be ejected"):
        macos.system.eject("Data")


def test_microphone_in_use(monkeypatch):
    from macos import audio

    properties = {(1, "prs#"): [101, 102], (101, "piri"): 0, (102, "piri"): 0}

    def fake_property(target, selector, scope=None, element=0):
        value = properties.get((target, selector))
        if value is None:
            return None
        values = value if isinstance(value, list) else [value]
        return b"".join(number.to_bytes(4, "little") for number in values)

    monkeypatch.setattr(audio, "_property", fake_property)
    monkeypatch.setattr(audio, "_uint", lambda target, selector: properties.get((target, selector)))
    assert macos.system.microphone_in_use() is False
    properties[(102, "piri")] = 1  # one app records
    assert macos.system.microphone_in_use() is True

    # Before macOS 14 there's no process list: an input device running counts.
    del properties[(1, "prs#")]
    monkeypatch.setattr(audio, "inputs", lambda: [audio.Device(9, "Mic", "mic", "builtin", False, True)])
    assert macos.system.microphone_in_use() is False
    properties[(9, "gone")] = 1
    assert macos.system.microphone_in_use() is True


def test_camera_in_use(monkeypatch):
    running = {1: [34, 35], 34: [0], 35: [0]}
    monkeypatch.setattr(
        macos.system,
        "_camera_property",
        lambda target, selector: b"".join(number.to_bytes(4, "little") for number in running[target]),
    )

    assert macos.system.camera_in_use() is False
    running[35] = [1]
    assert macos.system.camera_in_use() is True
