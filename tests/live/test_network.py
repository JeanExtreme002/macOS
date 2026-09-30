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
