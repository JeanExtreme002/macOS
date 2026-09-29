"""Tests of :mod:`macos.bluetooth` against the real system. Skipped outside macOS."""

import pytest

import macos


def test_bluetooth():
    try:
        on = macos.bluetooth.power()
    except macos.NotSupportedError:
        pytest.skip("no Bluetooth")
    assert isinstance(on, bool)
    found = macos.bluetooth.devices()
    assert all(isinstance(device, macos.bluetooth.Device) and device.address for device in found)
    assert len({device.address for device in found}) == len(found)
