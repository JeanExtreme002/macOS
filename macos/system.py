# -*- coding: utf-8 -*-

"""
Information about the Mac: macOS version, model, name, uptime, idle time, disks, fonts, heat and lid.

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
import os
import platform
import time
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

from . import _cf, _objc
from ._system import framework, require_macos, run
from .errors import MacOSError, NotSupportedError

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
    "volumes",
    "eject",
    "fonts",
    "thermal_state",
    "lid_closed",
    "Volume",
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


@dataclass(frozen=True)
class Volume:
    """A mounted volume: the startup disk, an external drive, a disk image..."""

    name: str
    path: Path
    """Where it's mounted, e.g. ``/Volumes/Backup`` (``/`` for the startup disk)."""
    total: int
    """Capacity, in bytes."""
    free: int
    """Space available, in bytes, as Finder shows it (purgeable space included)."""
    is_internal: bool
    is_removable: bool
    """A USB stick, SD card or other removable media."""
    is_ejectable: bool
    """Whether :func:`eject` (or Finder's eject button) can unmount it."""


_SKIP_HIDDEN_VOLUMES = 1 << 1  # NSVolumeEnumerationSkipHiddenVolumes


def _resource(url: int, key: str) -> Optional[int]:
    """The value of an ``NSURL`` resource key (a Foundation constant), or ``None``."""
    constant = ctypes.c_void_p.in_dll(framework("Foundation"), key).value
    value = ctypes.c_void_p()
    ok = _objc.send(
        url,
        "getResourceValue:forKey:error:",
        ctypes.byref(value),
        constant,
        None,
        argtypes=(ctypes.c_void_p, _objc.id, ctypes.c_void_p),
        restype=_objc.BOOL,
    )
    return value.value if ok and value.value else None


def _number(url: int, key: str) -> int:
    value = _resource(url, key)
    return int(_objc.send(value, "longLongValue", restype=ctypes.c_longlong)) if value else 0


def _flag(url: int, key: str) -> bool:
    value = _resource(url, key)
    return bool(value) and bool(_objc.send(value, "boolValue", restype=_objc.BOOL))


def volumes() -> List[Volume]:
    """Return the mounted volumes that Finder shows, the startup disk first."""
    framework("Foundation")
    found = []
    with _objc.autorelease_pool():
        manager = _objc.send(_objc.cls("NSFileManager"), "defaultManager")
        urls = _objc.send(
            manager,
            "mountedVolumeURLsIncludingResourceValuesForKeys:options:",
            None,
            _SKIP_HIDDEN_VOLUMES,
            argtypes=(_objc.id, _objc.NSUInteger),
        )
        for url in _objc.nsarray(urls):
            path = _objc.pystring(_objc.send(url, "path"))
            if not path:
                continue
            name_ref = _resource(url, "NSURLVolumeLocalizedNameKey")
            free = _number(url, "NSURLVolumeAvailableCapacityForImportantUsageKey") or _number(
                url, "NSURLVolumeAvailableCapacityKey"
            )
            found.append(
                Volume(
                    name=_objc.pystring(name_ref) or os.path.basename(path) or path,
                    path=Path(path),
                    total=_number(url, "NSURLVolumeTotalCapacityKey"),
                    free=free,
                    is_internal=_flag(url, "NSURLVolumeIsInternalKey"),
                    is_removable=_flag(url, "NSURLVolumeIsRemovableKey"),
                    is_ejectable=_flag(url, "NSURLVolumeIsEjectableKey"),
                )
            )
    return sorted(found, key=lambda volume: volume.path != Path("/"))


def eject(volume: Union[str, "os.PathLike[str]", Volume]) -> None:
    """
    Eject a volume, like Finder's eject button. Unsaved work on it is not waited for.

    ``volume`` is a :class:`Volume`, its name (``"Backup"``) or its mount
    path. When several volumes share a name, pass the path.
    """
    if isinstance(volume, Volume):
        chosen = volume
    else:
        text = os.fspath(volume)
        as_path = Path(text).expanduser()
        mounted = volumes()
        # Only the volumes Finder shows can be ejected: that leaves out the
        # startup disk's hidden system volumes (/System/Volumes/Data...).
        by_path = [found for found in mounted if found.path == as_path]
        by_name = [found for found in mounted if found.name == text]
        if not by_path and len(by_name) > 1:
            paths = ", ".join(str(found.path) for found in by_name)
            raise ValueError("more than one volume is named {!r} ({}); pass its path instead".format(text, paths))
        matches = by_path or by_name
        if not matches:
            raise ValueError("no mounted volume is named {!r}".format(text))
        chosen = matches[0]
    if chosen.path == Path("/"):
        raise ValueError("the startup disk can't be ejected")
    if not chosen.is_ejectable:
        raise ValueError("{} can't be ejected".format(chosen.name))
    run(["diskutil", "eject", str(chosen.path)])


def fonts() -> List[str]:
    """
    Return the font families installed on the Mac, sorted: ``['Arial', 'Avenir', ...]``.

    The names are the ones apps show in their font menus, including fonts the
    user installed. Handy to check a font exists before using it in a plot or
    an image.
    """
    framework("AppKit")
    with _objc.autorelease_pool():
        manager = _objc.send(_objc.cls("NSFontManager"), "sharedFontManager")
        families = _objc.nsarray(_objc.send(manager, "availableFontFamilies"))
        names = [_objc.pystring(family) or "" for family in families]
    # Hidden system families (".SF NS", ".Apple Color Emoji UI"...) can't be picked by name.
    return sorted((name for name in names if name and not name.startswith(".")), key=str.casefold)


_THERMAL_STATES = ("nominal", "fair", "serious", "critical")


def thermal_state() -> str:
    """
    How hot the Mac is running: ``'nominal'``, ``'fair'``, ``'serious'`` or ``'critical'``.

    At ``'serious'`` macOS slows the processor down to cool it; at
    ``'critical'`` it's close to shutting down. A long job can check it and
    pause::

        while macos.system.thermal_state() in ("serious", "critical"):
            time.sleep(60)
    """
    framework("Foundation")
    with _objc.autorelease_pool():
        info = _objc.send(_objc.cls("NSProcessInfo"), "processInfo")
        state = int(_objc.send(info, "thermalState", restype=_objc.NSInteger))
    return _THERMAL_STATES[state] if 0 <= state < len(_THERMAL_STATES) else "unknown"


def lid_closed() -> bool:
    """
    Whether the MacBook's lid is closed, as when it runs with an external display (clamshell mode).

    Raises :class:`~macos.errors.NotSupportedError` on a Mac without a lid.
    """
    io = _iokit()
    service = io.IOServiceGetMatchingService(0, io.IOServiceMatching(b"IOPMrootDomain"))
    if not service:
        raise MacOSError("the IOPMrootDomain service is not available")
    try:
        with _cf.owned(_cf.string("AppleClamshellState")) as key:
            with _cf.owned(io.IORegistryEntryCreateCFProperty(service, key, None, 0)) as value:
                if not value:
                    raise NotSupportedError("this Mac has no lid")
                return _cf.to_bool(value)
    finally:
        io.IOObjectRelease(service)
