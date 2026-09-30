"""Unit tests for :mod:`macos.network`. They run on any platform."""

import pytest

import macos


def test_network_ip_follows_the_default_route(commands):
    commands.answers["-n"] = (0, "   route to: default\n   interface: en7\n", "")
    commands.answers["getifaddr"] = (0, "10.0.0.5\n", "")

    assert macos.network.interface() == "en7"
    assert macos.network.ip() == "10.0.0.5"
    assert commands.calls[-1] == ["ipconfig", "getifaddr", "en7"]


def test_network_offline(commands):
    commands.answers["-n"] = (1, "", "route: writing to routing socket: not in table")

    assert macos.network.interface() is None
    assert macos.network.ip() is None


def test_wifi_power(commands):
    commands.answers["-listallhardwareports"] = (
        0,
        "Hardware Port: Ethernet\nDevice: en1\n\nHardware Port: Wi-Fi\nDevice: en0\n",
        "",
    )
    commands.answers["-getairportpower"] = (0, "Wi-Fi Power (en0): Off\n", "")

    assert macos.network.wifi_power() is False
    macos.network.set_wifi_power(True)
    assert commands.calls[-1] == ["networksetup", "-setairportpower", "en0", "on"]


def test_no_wifi(commands):
    commands.answers["-listallhardwareports"] = (0, "Hardware Port: Ethernet\nDevice: en1\n", "")

    with pytest.raises(macos.NotSupportedError, match="no Wi-Fi"):
        macos.network.wifi_power()


_VPN_LIST = """Available network connection services in the current set (*=enabled):
* ({office})   5E3C8DF5-5B2D-4F5E-9F1A-3A2B1C4D5E6F PPP --> L2TP       "Office"     [PPP/L2TP]
* (Connected)      4E3C8DF5-5B2D-4F5E-9F1A-3A2B1C4D5E6F VPN (com.wireguard.macos) "Home lab"   [VPN/WireGuard]
"""


def _scutil(monkeypatch, statuses):
    """A fake scutil whose "Office" VPN goes through ``statuses``, one per listing."""
    import subprocess

    from macos import _system

    calls = []

    def run(args, **kwargs):
        calls.append(list(args))
        if args[2] != "list":
            return subprocess.CompletedProcess(args, 0, "", "")
        status = statuses.pop(0) if len(statuses) > 1 else statuses[0]
        return subprocess.CompletedProcess(args, 0, _VPN_LIST.format(office=status), "")

    monkeypatch.setattr(_system.subprocess, "run", run)
    monkeypatch.setattr(macos.network.time, "sleep", lambda seconds: None)
    return calls


def test_vpns(fake_run, monkeypatch):
    _scutil(monkeypatch, ["Disconnected"])
    office, home = macos.network.vpns()
    assert (office.name, office.kind, office.status) == ("Office", "L2TP", "disconnected")
    assert (home.name, home.kind, home.status) == ("Home lab", "WireGuard", "connected")
    with pytest.raises(macos.MacOSError, match="no VPN named 'Work'.*'Office'"):
        macos.network.connect_vpn("Work")


def test_connect_vpn_waits_until_connected(fake_run, monkeypatch):
    calls = _scutil(monkeypatch, ["Disconnected", "Disconnected", "Connecting", "Connected"])
    macos.network.connect_vpn("Office")
    assert ["scutil", "--nc", "start", "5E3C8DF5-5B2D-4F5E-9F1A-3A2B1C4D5E6F"] in calls
    assert calls[-1] == ["scutil", "--nc", "list"]

    calls = _scutil(monkeypatch, ["Connected"])
    macos.network.connect_vpn("Office")  # already connected: nothing to do
    assert calls == [["scutil", "--nc", "list"]]

    calls = _scutil(monkeypatch, ["Connected", "Disconnecting", "Disconnected"])
    macos.network.disconnect_vpn("5E3C8DF5-5B2D-4F5E-9F1A-3A2B1C4D5E6F")  # by its id too
    assert ["scutil", "--nc", "stop", "5E3C8DF5-5B2D-4F5E-9F1A-3A2B1C4D5E6F"] in calls


def test_connect_vpn_fails(fake_run, monkeypatch):
    _scutil(monkeypatch, ["Disconnected", "Connecting", "Disconnected"])
    with pytest.raises(macos.MacOSError, match="didn't get connected"):
        macos.network.connect_vpn("Office")

    _scutil(monkeypatch, ["Disconnected"])
    with pytest.raises(macos.MacOSError, match="isn't connected after 0 seconds"):
        macos.network.connect_vpn("Office", timeout=0)

    calls = _scutil(monkeypatch, ["Disconnected"])
    macos.network.connect_vpn("Office", wait=False)
    assert calls[-1][:3] == ["scutil", "--nc", "start"]
