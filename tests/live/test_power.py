"""Tests of :mod:`macos.power` against the real system. Skipped outside macOS."""

import uuid

import pytest

import macos


def test_battery():
    battery = macos.power.battery()

    if battery is not None:  # desktops, and CI runners, have none
        assert 0 <= battery.percent <= 100
        assert isinstance(battery.charging, bool)
        assert isinstance(battery.plugged_in, bool)


def test_keep_awake_holds_a_power_assertion():
    import subprocess

    reason = "pymacos test {}".format(uuid.uuid4())

    def active():
        return reason in subprocess.run(["pmset", "-g", "assertions"], capture_output=True, text=True).stdout

    with macos.power.keep_awake(reason=reason):
        assert active()
    assert not active()


def test_battery_health():
    battery = macos.power.battery()
    if battery is None:
        pytest.skip("no battery")
    assert battery.cycle_count is None or battery.cycle_count >= 0
    assert battery.health is None or 0 < battery.health <= 100
