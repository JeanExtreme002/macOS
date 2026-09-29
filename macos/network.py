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
import re
import socket
from functools import lru_cache
from typing import Optional

from . import _cf
from ._system import framework, run as _run
from .errors import CommandError, NotSupportedError

__all__ = ["is_online", "ip", "interface", "wifi_power", "set_wifi_power"]

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
