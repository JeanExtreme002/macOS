# -*- coding: utf-8 -*-

"""
Information about the Mac: macOS version, model, name, uptime, idle time, disks, fonts, heat, lid, camera and microphone use.

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
import re
import time
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from . import _cf, _objc
from ._system import framework, require_macos, run as _run
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
    "cpu_usage",
    "MemoryUsage",
    "memory_usage",
    "idle_time",
    "wait_for_idle",
    "wait_for_activity",
    "volumes",
    "eject",
    "mount_image",
    "unmount_image",
    "Update",
    "available_updates",
    "fonts",
    "thermal_state",
    "lid_closed",
    "camera_in_use",
    "microphone_in_use",
    "Volume",
    "ds_store_on_network",
    "set_ds_store_on_network",
    "ds_store_on_usb",
    "set_ds_store_on_usb",
    "keep_windows_on_quit",
    "set_keep_windows_on_quit",
    "battery_percentage_shown",
    "set_show_battery_percentage",
    "save_to_icloud_by_default",
    "set_save_to_icloud_by_default",
    "expanded_save_dialog",
    "set_expanded_save_dialog",
    "clock_format",
    "set_clock_format",
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
    return _run(["sw_vers", "-buildVersion"]).strip()


@lru_cache(maxsize=None)
def model() -> str:
    """The Mac's marketing name, e.g. ``'MacBook Pro'`` or ``'Mac mini'``."""
    # system_profiler takes a moment, and the answer never changes: cache it.
    report = json.loads(_run(["system_profiler", "SPHardwareDataType", "-json"]))
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
    return _run(["scutil", "--get", "ComputerName"]).strip()


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


_CPU_LOAD_INFO, _VM_INFO64 = 3, 4  # HOST_CPU_LOAD_INFO, HOST_VM_INFO64


class _VMStatistics(ctypes.Structure):
    """``vm_statistics64``: page counts."""

    natural, counter = ctypes.c_uint32, ctypes.c_uint64
    _fields_ = [
        ("free_count", natural),
        ("active_count", natural),
        ("inactive_count", natural),
        ("wire_count", natural),
        ("zero_fill_count", counter),
        ("reactivations", counter),
        ("pageins", counter),
        ("pageouts", counter),
        ("faults", counter),
        ("cow_faults", counter),
        ("lookups", counter),
        ("hits", counter),
        ("purges", counter),
        ("purgeable_count", natural),
        ("speculative_count", natural),
        ("decompressions", counter),
        ("compressions", counter),
        ("swapins", counter),
        ("swapouts", counter),
        ("compressor_page_count", natural),
        ("throttled_count", natural),
        ("external_page_count", natural),
        ("internal_page_count", natural),
        ("total_uncompressed_pages_in_compressor", counter),
    ]


@lru_cache(maxsize=None)
def _mach() -> ctypes.CDLL:
    libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    libc.mach_host_self.restype = ctypes.c_uint32
    libc.host_statistics.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
    libc.host_statistics.restype = ctypes.c_int
    libc.host_statistics64.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
    libc.host_statistics64.restype = ctypes.c_int
    return libc


def _cpu_ticks() -> Tuple[int, int, int, int]:
    """The processor's user, system, idle and nice ticks since startup, all cores together (32-bit counters)."""
    require_macos()
    ticks = (ctypes.c_uint32 * 4)()  # user, system, idle, nice
    count = ctypes.c_uint32(4)
    mach = _mach()
    if mach.host_statistics(mach.mach_host_self(), _CPU_LOAD_INFO, ticks, ctypes.byref(count)) != 0:
        raise MacOSError("could not read the processor load")
    return ticks[0], ticks[1], ticks[2], ticks[3]


def cpu_usage(interval: float = 0.5) -> float:
    """
    How busy the processor is, from 0.0 (idle) to 1.0 (every core busy), over the next ``interval`` seconds.

    Like the CPU graph in Activity Monitor, all cores together.
    """
    if interval <= 0:
        raise ValueError("interval must be positive, not {}".format(interval))
    before = _cpu_ticks()
    time.sleep(interval)
    after = _cpu_ticks()
    # Each counter is 32-bit and wraps around: take each one's own difference, modulo 2**32.
    user, system_, idle, nice = ((later - earlier) % 2**32 for earlier, later in zip(before, after))
    total = user + system_ + idle + nice
    return min(1.0, (user + system_ + nice) / total) if total else 0.0


@dataclass(frozen=True)
class MemoryUsage:
    """The memory in use, in bytes, counted as Activity Monitor's Memory tab does."""

    total: int
    used: int
    """App memory, wired and compressed memory: what isn't free to give to an app."""
    wired: int
    """Memory the system keeps, which can't be compressed or paged out."""
    compressed: int
    cached: int
    """Recently used files, kept in memory while nothing needs it."""

    @property
    def free(self) -> int:
        return max(0, self.total - self.used)

    @property
    def percent(self) -> float:
        """``used`` as a fraction of ``total``, from 0.0 to 1.0."""
        return self.used / self.total if self.total else 0.0


def memory_usage() -> MemoryUsage:
    """How the memory is used right now: see :class:`MemoryUsage`."""
    require_macos()
    stats = _VMStatistics()
    count = ctypes.c_uint32(ctypes.sizeof(_VMStatistics) // 4)  # in 32-bit words
    mach = _mach()
    if mach.host_statistics64(mach.mach_host_self(), _VM_INFO64, ctypes.byref(stats), ctypes.byref(count)) != 0:
        raise MacOSError("could not read the memory statistics")
    page = int.from_bytes(_sysctl("hw.pagesize"), "little") or 4096
    app = max(0, stats.internal_page_count - stats.purgeable_count)
    wired, compressed = stats.wire_count, stats.compressor_page_count
    return MemoryUsage(
        total=memory(),
        used=(app + wired + compressed) * page,
        wired=wired * page,
        compressed=compressed * page,
        cached=(stats.external_page_count + stats.purgeable_count) * page,
    )


def wait_for_idle(seconds: Union[float, timedelta], *, timeout: Optional[float] = None) -> bool:
    """
    Wait until nobody has touched the keyboard, mouse or trackpad for ``seconds``; return ``False`` on ``timeout``.

    For work that should wait for you to step away::

        macos.system.wait_for_idle(300)       # 5 minutes away
        run_backup()

    ``seconds`` may be a :class:`~datetime.timedelta`. See :func:`idle_time`.
    """
    wanted = seconds.total_seconds() if isinstance(seconds, timedelta) else float(seconds)
    if wanted < 0:
        raise ValueError("seconds must not be negative, not {}".format(seconds))
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        idle = idle_time().total_seconds()
        if idle >= wanted:
            return True
        # Nothing can happen sooner than the idle time reaching the goal: sleep until then.
        pause = max(0.2, wanted - idle)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            pause = min(pause, remaining)
        time.sleep(pause)


_IDLE_SLACK = 0.05  # seconds: the idle time and the clock aren't read at the very same instant


def wait_for_activity(*, timeout: Optional[float] = None, interval: float = 0.2) -> bool:
    """
    Wait until someone uses the keyboard, mouse or trackpad; return ``False`` on ``timeout``.

    ::

        macos.system.wait_for_idle(300)
        macos.system.wait_for_activity()      # back at the Mac
        macos.say("Welcome back")

    Checks every ``interval`` seconds.
    """
    if interval <= 0:
        raise ValueError("interval must be positive, not {}".format(interval))
    deadline = None if timeout is None else time.monotonic() + timeout
    start, idle_at_start = time.monotonic(), idle_time().total_seconds()
    while True:
        remaining = None if deadline is None else deadline - time.monotonic()
        if remaining is not None and remaining <= 0:
            return False
        time.sleep(interval if remaining is None else min(interval, remaining))
        # Without input, the idle time grows as fast as the clock; any input starts it over,
        # so it falls behind, even when the input came right after the previous reading.
        expected = idle_at_start + (time.monotonic() - start)
        if idle_time().total_seconds() < expected - _IDLE_SLACK:
            return True


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
    _run(["diskutil", "eject", str(chosen.path)])


def mount_image(path: Union[str, "os.PathLike[str]"]) -> Path:
    """
    Mount a disk image (``.dmg``, ``.iso``...) like double-clicking it, without opening a Finder window; return where.

    ::

        mounted = macos.system.mount_image("~/Downloads/Tool.dmg")   # PosixPath('/Volumes/Tool')
        ...
        macos.system.unmount_image(mounted)

    A license the image shows first is accepted. See also :func:`macos.apps.install_from_dmg`.
    """
    import plistlib

    image = Path(path).expanduser().resolve()
    if not image.is_file():
        raise FileNotFoundError(str(image))
    # "Y" answers the license agreement some images show before mounting.
    output = _run(["hdiutil", "attach", "-nobrowse", "-noautoopen", "-plist", str(image)], input="Y\n")
    start = output.find("<?xml")
    try:
        details = plistlib.loads(output[start:].encode()) if start >= 0 else {}
    except (plistlib.InvalidFileException, ValueError):
        details = {}
    entities = details.get("system-entities", [])
    points = [entity["mount-point"] for entity in entities if entity.get("mount-point")]
    if not points:
        # Attached without a volume: detach its disk, so the image isn't left attached.
        devices = sorted((entity["dev-entry"] for entity in entities if entity.get("dev-entry")), key=len)
        for device in devices[:1]:
            try:
                _run(["hdiutil", "detach", device, "-force"])
            except MacOSError:
                pass
        raise MacOSError("{} has no volume to mount".format(image))
    return Path(points[0])


def unmount_image(mount_point: Union[str, "os.PathLike[str]"], *, force: bool = False) -> None:
    """Unmount a disk image mounted with :func:`mount_image` (or from Finder), given where it's mounted."""
    _run(["hdiutil", "detach", str(Path(mount_point)), *(["-force"] if force else [])])


@dataclass(frozen=True)
class Update:
    """A software update macOS offers, as System Settings › General › Software Update lists it."""

    label: str
    """The name ``softwareupdate --install`` takes, such as ``'macOS Sequoia 15.8.1-24H32'``."""
    title: str
    version: str
    size: Optional[int]
    """In bytes."""
    recommended: bool
    restart: bool
    """Whether installing it restarts the Mac."""


def _updates(output: str) -> List[Update]:
    found = []
    for label, details in re.findall(r"^\*\s*Label:\s*(.+?)\s*\n\s*(.+)$", output, re.M):
        fields = dict(
            (key.strip(), value.strip()) for key, _, value in (part.partition(":") for part in details.split(",")) if key.strip()
        )
        size = re.match(r"(\d+)\s*KiB", fields.get("Size", ""))
        found.append(
            Update(
                label=label,
                title=fields.get("Title", label).replace("\xa0", " "),
                version=fields.get("Version", ""),
                size=int(size.group(1)) * 1024 if size else None,
                recommended=fields.get("Recommended", "").upper() == "YES",
                restart=fields.get("Action", "").lower() == "restart",
            )
        )
    return found


def available_updates() -> List[Update]:
    """
    The macOS and app updates Software Update offers; ``[]`` when everything is up to date.

    Asks Apple's servers, so it takes a while (often 10 to 30 seconds). To
    install one, run ``softwareupdate --install "<label>"`` (with ``sudo``
    for most).
    """
    return _updates(_run(["softwareupdate", "--list"]))


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


class _PropertyAddress(ctypes.Structure):
    # The same layout for CoreAudio and CoreMediaIO properties.
    _fields_ = [("selector", ctypes.c_uint32), ("scope", ctypes.c_uint32), ("element", ctypes.c_uint32)]


def _four_cc(text: str) -> int:
    return int.from_bytes(text.encode("ascii"), "big")


@lru_cache(maxsize=None)
def _media_io() -> ctypes.CDLL:
    media = framework("CoreMediaIO")
    address = ctypes.POINTER(_PropertyAddress)
    size = ctypes.POINTER(ctypes.c_uint32)
    media.CMIOObjectGetPropertyDataSize.argtypes = (ctypes.c_uint32, address, ctypes.c_uint32, ctypes.c_void_p, size)
    media.CMIOObjectGetPropertyDataSize.restype = ctypes.c_int32
    media.CMIOObjectGetPropertyData.argtypes = (
        ctypes.c_uint32,
        address,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        size,
        ctypes.c_void_p,
    )
    media.CMIOObjectGetPropertyData.restype = ctypes.c_int32
    return media


def _camera_property(target: int, selector: str) -> Optional[bytes]:
    media = _media_io()
    address = _PropertyAddress(_four_cc(selector), _four_cc("glob"), 0)
    size = ctypes.c_uint32()
    if media.CMIOObjectGetPropertyDataSize(target, ctypes.byref(address), 0, None, ctypes.byref(size)) != 0:
        return None
    buffer = ctypes.create_string_buffer(size.value)
    used = ctypes.c_uint32()
    status = media.CMIOObjectGetPropertyData(
        target, ctypes.byref(address), 0, None, size.value, ctypes.byref(used), buffer
    )
    return buffer.raw[: used.value] if status == 0 else None


def _uints(raw: Optional[bytes]) -> List[int]:
    raw = raw or b""
    return [int.from_bytes(raw[index : index + 4], "little") for index in range(0, len(raw) - 3, 4)]


def camera_in_use() -> bool:
    """
    Whether an app is using a camera right now, as when its green light is on.

    Handy for an "on air" light, or to pause something noisy during video
    calls. It doesn't say which app. Needs no permission.
    """
    cameras = _uints(_camera_property(1, "dev#"))  # 1: kCMIOObjectSystemObject
    return any(_uints(_camera_property(camera, "gone"))[:1] == [1] for camera in cameras)


def microphone_in_use() -> bool:
    """
    Whether an app is recording from a microphone right now, as when the orange dot shows in the menu bar.

    It doesn't say which app. Needs no permission.
    """
    from . import audio

    processes = _uints(audio._property(audio._SYSTEM, "prs#"))
    if processes:
        # macOS 14+: each process says whether it records (kAudioProcessPropertyIsRunningInput).
        return any(audio._uint(process, "piri") for process in processes)
    # Before: whether an input device is running for any app. A headset
    # that only plays sound can count too.
    return any(audio._uint(device.id, "gone") for device in audio.inputs())


_DESKTOP_SERVICES = "com.apple.desktopservices"


def ds_store_on_network() -> bool:
    """Whether Finder writes ``.DS_Store`` files into network shares it opens."""
    from . import defaults

    return not defaults.read(_DESKTOP_SERVICES, "DSDontWriteNetworkStores", default=False)


def set_ds_store_on_network(on: bool = True) -> None:
    """
    Let Finder write ``.DS_Store`` files into network shares, or not (``False``), sparing everyone else on them.

    Takes effect at the next login.
    """
    from . import defaults

    defaults.write(_DESKTOP_SERVICES, "DSDontWriteNetworkStores", not on)


def ds_store_on_usb() -> bool:
    """Whether Finder writes ``.DS_Store`` files onto USB drives and other external disks."""
    from . import defaults

    return not defaults.read(_DESKTOP_SERVICES, "DSDontWriteUSBStores", default=False)


def set_ds_store_on_usb(on: bool = True) -> None:
    """Let Finder write ``.DS_Store`` files onto USB drives and external disks, or not. Takes effect at the next login."""
    from . import defaults

    defaults.write(_DESKTOP_SERVICES, "DSDontWriteUSBStores", not on)


def keep_windows_on_quit() -> bool:
    """Whether apps reopen the windows they had when they quit (unchecks "Close windows when quitting an app")."""
    from . import defaults

    return bool(defaults.read(defaults.GLOBAL, "NSQuitAlwaysKeepsWindows", default=False))


def set_keep_windows_on_quit(on: bool = True) -> None:
    """Make apps reopen their windows when opened again, or start fresh (``False``)."""
    from . import defaults

    defaults.write(defaults.GLOBAL, "NSQuitAlwaysKeepsWindows", bool(on))


def battery_percentage_shown() -> bool:
    """Whether the battery icon in the menu bar shows the percentage."""
    from . import defaults

    return bool(defaults.read("com.apple.controlcenter", "BatteryShowPercentage", default=False, current_host=True))


def set_show_battery_percentage(on: bool = True) -> None:
    """Show the battery percentage next to its icon in the menu bar, or not."""
    from . import defaults

    defaults.write("com.apple.controlcenter", "BatteryShowPercentage", bool(on), current_host=True)
    try:
        _run(["killall", "ControlCenter"])  # macOS starts it again, reading the setting
    except MacOSError:
        pass


def save_to_icloud_by_default() -> bool:
    """Whether new documents are saved to iCloud Drive unless another place is chosen."""
    from . import defaults

    return bool(defaults.read(defaults.GLOBAL, "NSDocumentSaveNewDocumentsToCloud", default=True))


def set_save_to_icloud_by_default(on: bool = True) -> None:
    """Offer iCloud Drive first when saving a new document, or the Mac (``False``). Apps pick it up when reopened."""
    from . import defaults

    defaults.write(defaults.GLOBAL, "NSDocumentSaveNewDocumentsToCloud", bool(on))


def expanded_save_dialog() -> bool:
    """Whether the Save dialog opens expanded, with the sidebar and the folders."""
    from . import defaults

    return bool(defaults.read(defaults.GLOBAL, "NSNavPanelExpandedStateForSaveMode", default=False))


def set_expanded_save_dialog(on: bool = True) -> None:
    """Open the Save dialog expanded, with every folder, or small (``False``). Apps pick it up when reopened."""
    from . import defaults

    for key in ("NSNavPanelExpandedStateForSaveMode", "NSNavPanelExpandedStateForSaveMode2"):
        defaults.write(defaults.GLOBAL, key, bool(on))


_CLOCK = "com.apple.menuextra.clock"
# Name: (key, default).
_CLOCK_OPTIONS = {
    "seconds": ("ShowSeconds", False),
    "day_of_week": ("ShowDayOfWeek", True),
    "am_pm": ("ShowAMPM", True),
    "analog": ("IsAnalog", False),
}
_CLOCK_DATES = ("auto", "always", "never")  # ShowDate's 0, 1 and 2


def clock_format() -> Dict[str, object]:
    """
    How the menu bar's clock shows the time.

    ``{"seconds": False, "day_of_week": True, "am_pm": True, "analog": False, "date": "auto"}``;
    ``date`` is ``"auto"`` (when there's room), ``"always"`` or ``"never"``.
    """
    from . import defaults

    found: Dict[str, object] = {
        name: bool(defaults.read(_CLOCK, key, default=default)) for name, (key, default) in _CLOCK_OPTIONS.items()
    }
    date = int(defaults.read(_CLOCK, "ShowDate", default=0))
    found["date"] = _CLOCK_DATES[date] if 0 <= date < len(_CLOCK_DATES) else "auto"
    return found


def set_clock_format(
    *,
    seconds: Optional[bool] = None,
    day_of_week: Optional[bool] = None,
    am_pm: Optional[bool] = None,
    analog: Optional[bool] = None,
    date: Optional[str] = None,
) -> None:
    """
    Change how the menu bar's clock shows the time; the options left out stay as they are.

    ::

        macos.system.set_clock_format(seconds=True, date="always")

    ``date`` is ``"auto"`` (when there's room), ``"always"`` or ``"never"``.
    Whether it's 12 or 24 hours follows System Settings › General › Date & Time.
    """
    from . import defaults

    options = {"seconds": seconds, "day_of_week": day_of_week, "am_pm": am_pm, "analog": analog}
    if date is None and all(value is None for value in options.values()):
        raise ValueError("say what to change: seconds=, day_of_week=, am_pm=, analog= or date=")
    if date is not None and date not in _CLOCK_DATES:
        raise ValueError("date must be 'auto', 'always' or 'never', not {!r}".format(date))
    for name, value in options.items():
        if value is not None:
            defaults.write(_CLOCK, _CLOCK_OPTIONS[name][0], bool(value))
    if date is not None:
        defaults.write(_CLOCK, "ShowDate", _CLOCK_DATES.index(date))
    try:
        _run(["killall", "ControlCenter"])  # it draws the clock; macOS starts it again, reading the settings
    except MacOSError:
        pass
