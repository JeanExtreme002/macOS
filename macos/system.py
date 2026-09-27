# -*- coding: utf-8 -*-

"""
Information about the Mac: macOS version, model, name, uptime and idle time.

::

    macos.system.version()        # '15.6.1'
    macos.system.model()          # 'MacBook Pro'
    macos.system.processor()      # 'Apple M2 Pro'
    macos.system.idle_time()      # datetime.timedelta(seconds=312)

Kernel values come from ``sysctl`` and IOKit directly; the rest from the
commands that ship with macOS.
"""

import ctypes
import json
import platform
import time
from datetime import timedelta
from functools import lru_cache
from typing import Optional

from . import _cf
from ._system import framework, require_macos, run
from .errors import MacOSError

__all__ = [
    "version",
    "build",
    "model",
    "model_identifier",
    "processor",
    "memory",
    "computer_name",
    "uptime",
    "idle_time",
]


class _Timeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_int32)]


@lru_cache(maxsize=None)
def _libc() -> ctypes.CDLL:
    require_macos()
    lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    lib.sysctlbyname.argtypes = (
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_void_p,
        ctypes.c_size_t,
    )
    lib.sysctlbyname.restype = ctypes.c_int
    return lib


def _sysctl(name: str) -> bytes:
    lib = _libc()
    size = ctypes.c_size_t()
    if lib.sysctlbyname(name.encode(), None, ctypes.byref(size), None, 0) != 0:
        raise MacOSError("sysctl {} is not available".format(name))
    buffer = ctypes.create_string_buffer(size.value)
    if lib.sysctlbyname(name.encode(), buffer, ctypes.byref(size), None, 0) != 0:
        raise MacOSError("sysctl {} is not available".format(name))
    return buffer.raw[: size.value]


def _sysctl_str(name: str) -> str:
    return _sysctl(name).rstrip(b"\0").decode("utf-8", "replace")


def version() -> str:
    """The macOS version, e.g. ``'15.6.1'``."""
    require_macos()
    return platform.mac_ver()[0]


def build() -> str:
    """The macOS build number, e.g. ``'24G90'``."""
    return run(["sw_vers", "-buildVersion"]).strip()


@lru_cache(maxsize=None)
def model() -> str:
    """The Mac's marketing name, e.g. ``'MacBook Pro'`` or ``'Mac mini'``."""
    # system_profiler takes a moment, and the answer never changes: cache it.
    report = json.loads(run(["system_profiler", "SPHardwareDataType", "-json"]))
    return str(report["SPHardwareDataType"][0]["machine_name"])


def model_identifier() -> str:
    """The Mac's model identifier, e.g. ``'Mac14,9'``."""
    return _sysctl_str("hw.model")


def processor() -> str:
    """The processor's name, e.g. ``'Apple M2 Pro'`` or ``'Intel(R) Core(TM) i7-9750H ...'``."""
    return _sysctl_str("machdep.cpu.brand_string")


def memory() -> int:
    """The installed memory (RAM), in bytes."""
    return int.from_bytes(_sysctl("hw.memsize"), "little")


def computer_name() -> str:
    """The name shown in System Settings › General › About (and on the network)."""
    return run(["scutil", "--get", "ComputerName"]).strip()


def uptime() -> timedelta:
    """How long the Mac has been running since it last started (sleep time included)."""
    boot = _Timeval.from_buffer_copy(_sysctl("kern.boottime")[: ctypes.sizeof(_Timeval)])
    return timedelta(seconds=round(time.time() - (boot.tv_sec + boot.tv_usec / 1e6)))


@lru_cache(maxsize=None)
def _iokit() -> ctypes.CDLL:
    io = framework("IOKit")
    io.IOServiceMatching.argtypes = (ctypes.c_char_p,)
    io.IOServiceMatching.restype = _cf.CFTypeRef
    io.IOServiceGetMatchingService.argtypes = (ctypes.c_uint32, _cf.CFTypeRef)
    io.IOServiceGetMatchingService.restype = ctypes.c_uint32
    io.IORegistryEntryCreateCFProperty.argtypes = (ctypes.c_uint32, _cf.CFTypeRef, _cf.CFTypeRef, ctypes.c_uint32)
    io.IORegistryEntryCreateCFProperty.restype = _cf.CFTypeRef
    io.IOObjectRelease.argtypes = (ctypes.c_uint32,)
    io.IOObjectRelease.restype = ctypes.c_int
    return io


def idle_time() -> timedelta:
    """
    Time since the last keyboard, mouse or trackpad input.

    Useful to run something only while the user is away::

        if macos.system.idle_time() > timedelta(minutes=10):
            run_heavy_job()
    """
    io = _iokit()
    # IOServiceGetMatchingService consumes the matching dictionary; 0 is the
    # default main port.
    service = io.IOServiceGetMatchingService(0, io.IOServiceMatching(b"IOHIDSystem"))
    if not service:
        raise MacOSError("the IOHIDSystem service is not available")
    try:
        with _cf.owned(_cf.string("HIDIdleTime")) as key:
            value: Optional[int]
            with _cf.owned(io.IORegistryEntryCreateCFProperty(service, key, None, 0)) as ref:
                value = _cf.to_int(ref)
    finally:
        io.IOObjectRelease(service)
    if value is None:
        raise MacOSError("the idle time is not available")
    return timedelta(microseconds=value / 1000)  # nanoseconds
