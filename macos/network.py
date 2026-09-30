# -*- coding: utf-8 -*-

"""
Basic network information and Wi-Fi power.

::

    macos.network.is_online()           # True
    macos.network.ip()                  # '192.168.0.8'
    macos.network.wifi_power()          # True
    macos.network.set_wifi_power(False)

The Wi-Fi network's name (SSID) isn't here: since macOS 14 reading it needs
the Location permission.
"""

import ctypes
import json
import re
import socket
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional

from . import _cf, _objc
from ._system import framework, require_macos, run as _run
from .errors import CommandError, MacOSError, NotSupportedError

__all__ = [
    "is_online",
    "ip",
    "interface",
    "wifi_power",
    "set_wifi_power",
    "SpeedTest",
    "speed_test",
    "WiFiSignal",
    "wifi_signal",
]

_REACHABLE = 1 << 1  # kSCNetworkReachabilityFlagsReachable
_CONNECTION_REQUIRED = 1 << 2  # kSCNetworkReachabilityFlagsConnectionRequired


class _SockaddrIn(ctypes.Structure):
    _fields_ = [
        ("sin_len", ctypes.c_uint8),
        ("sin_family", ctypes.c_uint8),
        ("sin_port", ctypes.c_uint16),
        ("sin_addr", ctypes.c_uint32),
        ("sin_zero", ctypes.c_char * 8),
    ]


@lru_cache(maxsize=None)
def _configuration() -> ctypes.CDLL:
    config = framework("SystemConfiguration")
    config.SCNetworkReachabilityCreateWithAddress.argtypes = (ctypes.c_void_p, ctypes.POINTER(_SockaddrIn))
    config.SCNetworkReachabilityCreateWithAddress.restype = ctypes.c_void_p
    config.SCNetworkReachabilityGetFlags.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
    config.SCNetworkReachabilityGetFlags.restype = ctypes.c_bool
    return config


def is_online() -> bool:
    """
    Whether the Mac has a network connection that can reach the internet.

    Checked locally, without contacting any server, the same way apps decide to
    show "you're offline". A captive portal (hotel Wi-Fi login page) still
    counts as online.
    """
    config = _configuration()
    # 0.0.0.0 stands for "any address": is there a route out at all?
    anywhere = _SockaddrIn(ctypes.sizeof(_SockaddrIn), socket.AF_INET, 0, 0, b"")
    target = config.SCNetworkReachabilityCreateWithAddress(None, ctypes.byref(anywhere))
    if not target:
        return False
    with _cf.owned(target):
        flags = ctypes.c_uint32()
        if not config.SCNetworkReachabilityGetFlags(target, ctypes.byref(flags)):
            return False
    return bool(flags.value & _REACHABLE) and not flags.value & _CONNECTION_REQUIRED


def interface() -> Optional[str]:
    """The network interface internet traffic goes through, e.g. ``'en0'``, or ``None`` when offline."""
    try:
        output = _run(["route", "-n", "get", "default"])
    except CommandError:  # no default route
        return None
    found = re.search(r"interface:\s*(\S+)", output)
    return found.group(1) if found else None


def ip() -> Optional[str]:
    """The Mac's IPv4 address on the local network (e.g. ``'192.168.0.8'``), or ``None`` when offline."""
    name = interface()
    if name is None:
        return None
    try:
        address = _run(["ipconfig", "getifaddr", name]).strip()
    except CommandError:  # the interface has no IPv4 address (e.g. a VPN tunnel)
        return None
    return address or None


def _wifi_device() -> str:
    ports = _run(["networksetup", "-listallhardwareports"])
    found = re.search(r"Hardware Port: (?:Wi-Fi|AirPort)\s*\nDevice: (\S+)", ports)
    if not found:
        raise NotSupportedError("this Mac has no Wi-Fi")
    return found.group(1)


def wifi_power() -> bool:
    """Whether Wi-Fi is turned on. Raises :class:`~macos.errors.NotSupportedError` on a Mac without Wi-Fi."""
    output = _run(["networksetup", "-getairportpower", _wifi_device()])
    return output.strip().lower().endswith("on")


def set_wifi_power(on: bool) -> None:
    """Turn Wi-Fi on or off, like the switch in Control Center."""
    _run(["networksetup", "-setairportpower", _wifi_device(), "on" if on else "off"])


# --- Speed test -------------------------------------------------------------------


@dataclass(frozen=True)
class SpeedTest:
    """How fast the internet connection is, as :func:`speed_test` measured it."""

    download: float
    """In megabits per second, as internet plans are sold."""
    upload: float
    latency: Optional[float]
    """Round trip to the test server when idle, in milliseconds."""
    loaded_latency: Optional[float]
    """Round trip while the connection is busy, in milliseconds: how laggy calls and games get under load."""
    responsiveness: Optional[float]
    """The same under load as a score, in round trips per minute (RPM): the higher, the better."""
    interface: Optional[str]
    """The network interface measured, such as ``'en0'``."""
    server: Optional[str]
    """Apple's test server that answered."""


def _speed(result: Dict[str, Any]) -> SpeedTest:
    def megabits(key: str) -> float:
        return round(float(result.get(key) or 0) / 1e6, 2)

    idle = result.get("base_rtt")
    # "responsiveness" is a score in round trips per minute, not a time: 60,000 ms / RPM.
    rpm = float(result["responsiveness"]) if result.get("responsiveness") else None
    return SpeedTest(
        download=megabits("dl_throughput"),  # bits per second, as its text summary's Mbps show
        upload=megabits("ul_throughput"),
        latency=round(float(idle), 1) if idle is not None else None,
        loaded_latency=round(60000 / rpm, 1) if rpm else None,
        responsiveness=round(rpm, 1) if rpm else None,
        interface=result.get("interface_name"),
        server=result.get("test_endpoint"),
    )


def speed_test(*, sequential: bool = False) -> SpeedTest:
    """
    Measure the internet connection's download and upload speed, and its latency, against Apple's servers.

    ::

        result = macos.network.speed_test()
        result.download, result.upload   # (43.61, 39.42): megabits per second
        result.latency                   # 54.6 ms, idle
        result.loaded_latency            # 1126.6 ms while busy: calls lag

    It takes 15 to 60 seconds and moves a few hundred megabytes: mind a
    metered connection. ``sequential=True`` measures download and upload
    one after the other instead of together, which reads each more exactly.
    Goes through ``networkQuality``, which comes with macOS.
    """
    require_macos()
    output = _run(["networkQuality", "-c", *(["-s"] if sequential else [])])
    try:
        return _speed(json.loads(output))
    except ValueError:
        raise MacOSError("networkQuality gave an answer that isn't JSON: {!r}".format(output[:200])) from None


# --- Wi-Fi signal -------------------------------------------------------------------

_BANDS = {1: "2.4GHz", 2: "5GHz", 3: "6GHz"}  # CWChannelBand
_WIDTHS = {1: 20, 2: 40, 3: 80, 4: 160}  # CWChannelWidth, in MHz
_SECURITY = {  # CWSecurity
    0: "none",
    1: "wep",
    2: "wpa_personal",
    3: "wpa_personal",
    4: "wpa2_personal",
    5: "personal",
    6: "dynamic_wep",
    7: "wpa_enterprise",
    8: "wpa_enterprise",
    9: "wpa2_enterprise",
    10: "enterprise",
    11: "wpa3_personal",
    12: "wpa3_enterprise",
    13: "wpa3_transition",
    14: "owe",
    15: "owe_transition",
}


@dataclass(frozen=True)
class WiFiSignal:
    """How good the Wi-Fi connection is right now."""

    rssi: int
    """Signal strength, in dBm: -50 is excellent, -70 fair, below -80 poor."""
    noise: int
    """Background noise, in dBm: the lower, the better."""
    transmit_rate: float
    """The speed the link runs at, in megabits per second: an upper bound, not the internet's speed."""
    channel: Optional[int]
    band: Optional[str]
    """``'2.4GHz'``, ``'5GHz'`` or ``'6GHz'``."""
    channel_width: Optional[int]
    """In MHz: 20, 40, 80 or 160."""
    security: Optional[str]
    """Such as ``'wpa2_personal'`` or ``'wpa3_personal'``."""

    @property
    def snr(self) -> int:
        """Signal-to-noise ratio, in dB: above 25 is good, below 15 unreliable."""
        return self.rssi - self.noise

    @property
    def quality(self) -> str:
        """``'excellent'``, ``'good'``, ``'fair'`` or ``'poor'``, from the signal strength."""
        if self.rssi >= -55:
            return "excellent"
        if self.rssi >= -67:
            return "good"
        if self.rssi >= -75:
            return "fair"
        return "poor"


def wifi_signal() -> Optional[WiFiSignal]:
    """
    The current Wi-Fi connection's signal, noise, speed and channel; ``None`` when not connected to Wi-Fi.

    ::

        signal = macos.network.wifi_signal()
        signal.rssi, signal.quality      # (-62, 'good')
        signal.band, signal.channel      # ('5GHz', 157)

    Handy to find the room's dead spots, or tell a weak signal from a slow
    internet. It needs no permission; the network's name, which macOS keeps
    behind the Location permission, isn't part of it.
    """
    framework("CoreWLAN")
    with _objc.autorelease_pool():
        client = _objc.send(_objc.cls("CWWiFiClient"), "sharedWiFiClient")
        interface = _objc.send(client, "interface")
        if not interface or not _objc.send(interface, "powerOn", restype=_objc.BOOL):
            return None
        rssi = int(_objc.send(interface, "rssiValue", restype=ctypes.c_long))
        if rssi == 0:
            return None  # powered on, but not connected
        channel = _objc.send(interface, "wlanChannel")

        def number(selector: str) -> Optional[int]:
            return int(_objc.send(channel, selector, restype=ctypes.c_long)) if channel else None

        security = int(_objc.send(interface, "security", restype=ctypes.c_long))
        return WiFiSignal(
            rssi=rssi,
            noise=int(_objc.send(interface, "noiseMeasurement", restype=ctypes.c_long)),
            transmit_rate=float(_objc.send(interface, "transmitRate", restype=ctypes.c_double)),
            channel=number("channelNumber") or None,
            band=_BANDS.get(number("channelBand") or 0),
            channel_width=_WIDTHS.get(number("channelWidth") or 0),
            security=_SECURITY.get(security),
        )
