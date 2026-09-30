"""Tests of :mod:`macos.network` against the real system. Skipped outside macOS."""

import macos


def test_network():
    import re

    assert isinstance(macos.network.is_online(), bool)
    address = macos.network.ip()
    assert address is None or re.fullmatch(r"\d+\.\d+\.\d+\.\d+", address)
    try:
        assert isinstance(macos.network.wifi_power(), bool)
    except macos.NotSupportedError:
        pass  # no Wi-Fi, as on some CI runners


def test_vpns():
    import pytest

    found = macos.network.vpns()
    assert all(vpn.status in ("connected", "connecting", "disconnecting", "disconnected") for vpn in found)
    with pytest.raises(macos.MacOSError, match="no VPN named"):
        macos.network.connect_vpn("pymacos-missing-vpn")


def test_bandwidth():
    found = macos.network.bandwidth(0.5)
    assert found and all(use.download >= 0 and use.upload >= 0 and use.interface != "lo0" for use in found)
    assert [use.received + use.sent for use in found] == sorted((use.received + use.sent for use in found), reverse=True)
