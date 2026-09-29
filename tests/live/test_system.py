"""Tests of :mod:`macos.system` against the real system. Skipped outside macOS."""

import uuid
from pathlib import Path

import pytest

import macos


def test_fonts():
    families = macos.system.fonts()

    assert "Helvetica" in families
    assert families == sorted(families, key=str.casefold)
    assert not any(name.startswith(".") for name in families)


def test_system_info():
    import re
    from datetime import timedelta

    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", macos.system.version())
    assert macos.system.build()
    assert macos.system.model()
    assert re.fullmatch(r"[A-Za-z]+\d+,\d+", macos.system.model_identifier())
    assert macos.system.processor()
    assert macos.system.memory() >= 2**30
    assert macos.system.computer_name()
    assert macos.system.uptime() > timedelta(0)
    assert macos.system.idle_time() >= timedelta(0)


def test_volumes_and_eject(tmp_path):
    import subprocess

    volumes = macos.system.volumes()
    assert volumes[0].path == Path("/") and volumes[0].total > 0

    name = "PymacosTest{}".format(uuid.uuid4().hex[:6])
    image = tmp_path / "test.dmg"
    created = subprocess.run(
        ["hdiutil", "create", "-size", "2m", "-fs", "HFS+", "-volname", name, "-o", str(image), "-quiet"]
    )
    if created.returncode != 0 or subprocess.run(["hdiutil", "attach", str(image), "-quiet"]).returncode != 0:
        pytest.skip("hdiutil can't create or attach disk images here")
    try:
        mounted = [volume for volume in macos.system.volumes() if volume.name == name]
        assert mounted and mounted[0].is_ejectable
        macos.system.eject(name)
        assert name not in [volume.name for volume in macos.system.volumes()]
    finally:
        subprocess.run(["hdiutil", "detach", "/Volumes/{}".format(name), "-quiet"], capture_output=True)


def test_thermal_state_and_lid():
    assert macos.system.thermal_state() in ("nominal", "fair", "serious", "critical")
    try:
        assert isinstance(macos.system.lid_closed(), bool)
    except macos.NotSupportedError:
        pass  # a desktop Mac


def test_camera_microphone_and_power_state():
    assert isinstance(macos.system.camera_in_use(), bool)
    assert isinstance(macos.system.microphone_in_use(), bool)
    assert isinstance(macos.power.low_power_mode(), bool)
    assert isinstance(macos.keyboard.caps_lock(), bool)


def test_wait_for_idle():
    assert macos.system.wait_for_idle(0) is True
    assert macos.system.wait_for_idle(3600, timeout=0.3) is False
