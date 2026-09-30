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


def test_sleep_blockers_see_keep_awake():
    import os

    reason = "pymacos test {}".format(uuid.uuid4())

    def mine():
        return [blocker for blocker in macos.power.sleep_blockers() if blocker.reason == reason]

    with macos.power.keep_awake(reason=reason, display=True):
        found = mine()
        assert len(found) == 1 and found[0].pid == os.getpid() and found[0].display is True
        assert found[0].since is not None and found[0].until is None
    assert mine() == []


def test_battery_health():
    battery = macos.power.battery()
    if battery is None:
        pytest.skip("no battery")
    assert battery.cycle_count is None or battery.cycle_count >= 0
    assert battery.health is None or 0 < battery.health <= 100
