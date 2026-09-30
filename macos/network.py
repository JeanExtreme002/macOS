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

from . import _cf
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
    interface: Optional[str]
    """The network interface measured, such as ``'en0'``."""
    server: Optional[str]
    """Apple's test server that answered."""


def _speed(result: Dict[str, Any]) -> SpeedTest:
    def megabits(key: str) -> float:
        return round(float(result.get(key) or 0) / 1e6, 2)

    def milliseconds(key: str) -> Optional[float]:
        return round(float(result[key]), 1) if result.get(key) is not None else None

    return SpeedTest(
        download=megabits("dl_throughput"),
        upload=megabits("ul_throughput"),
        latency=milliseconds("base_rtt"),
        loaded_latency=milliseconds("responsiveness"),
        interface=result.get("interface_name"),
        server=result.get("test_endpoint"),
    )


def speed_test(*, sequential: bool = False) -> SpeedTest:
    """
    Measure the internet connection's download and upload speed, and its latency, against Apple's servers.

    ::

        result = macos.network.speed_test()
        result.download, result.upload   # (43.61, 39.42): megabits per second
        result.latency                   # 54.6 ms

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
