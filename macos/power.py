# -*- coding: utf-8 -*-

"""
Battery status and keeping the Mac awake.

::

    battery = macos.power.battery()
    print(battery.percent, battery.charging)

    with macos.power.keep_awake():
        train_model()       # the Mac won't go to sleep meanwhile

Both talk to IOKit directly: the battery comes from the same power-source
information as the menu bar icon, and ``keep_awake`` holds a power assertion,
like the ``caffeinate`` command does.
"""

import ctypes
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Dict, Iterator, Optional, Tuple

from . import _cf
from ._system import framework, run
from .errors import MacOSError

__all__ = ["Battery", "battery", "keep_awake", "sleep", "sleep_display"]

kIOPMAssertionLevelOn = 255
kIOReturnSuccess = 0


@lru_cache(maxsize=None)
def _iokit() -> ctypes.CDLL:
    io = framework("IOKit")

    io.IOPSCopyPowerSourcesInfo.argtypes = ()
    io.IOPSCopyPowerSourcesInfo.restype = _cf.CFTypeRef
    io.IOPSCopyPowerSourcesList.argtypes = (_cf.CFTypeRef,)
    io.IOPSCopyPowerSourcesList.restype = _cf.CFTypeRef
    io.IOPSGetPowerSourceDescription.argtypes = (_cf.CFTypeRef, _cf.CFTypeRef)
    io.IOPSGetPowerSourceDescription.restype = _cf.CFTypeRef

    io.IOPMAssertionCreateWithName.argtypes = (
        _cf.CFTypeRef,
        ctypes.c_uint32,
        _cf.CFTypeRef,
        ctypes.POINTER(ctypes.c_uint32),
    )
    io.IOPMAssertionCreateWithName.restype = ctypes.c_int
    io.IOPMAssertionRelease.argtypes = (ctypes.c_uint32,)
    io.IOPMAssertionRelease.restype = ctypes.c_int

    io.IOServiceMatching.argtypes = (ctypes.c_char_p,)
    io.IOServiceMatching.restype = _cf.CFTypeRef
    io.IOServiceGetMatchingService.argtypes = (ctypes.c_uint32, _cf.CFTypeRef)
    io.IOServiceGetMatchingService.restype = ctypes.c_uint32
    io.IORegistryEntryCreateCFProperty.argtypes = (ctypes.c_uint32, _cf.CFTypeRef, _cf.CFTypeRef, ctypes.c_uint32)
    io.IORegistryEntryCreateCFProperty.restype = _cf.CFTypeRef
    io.IOObjectRelease.argtypes = (ctypes.c_uint32,)
    io.IOObjectRelease.restype = ctypes.c_int
    return io


def _battery_registry(*names: str) -> Dict[str, Optional[int]]:
    """Integer properties of the AppleSmartBattery service (``None`` when missing)."""
    io = _iokit()
    service = io.IOServiceGetMatchingService(0, io.IOServiceMatching(b"AppleSmartBattery"))
    values: Dict[str, Optional[int]] = {name: None for name in names}
    if not service:
        return values
    try:
        for name in names:
            with _cf.owned(_cf.string(name)) as key:
                with _cf.owned(io.IORegistryEntryCreateCFProperty(service, key, None, 0)) as ref:
                    values[name] = _cf.to_int(ref)
    finally:
        io.IOObjectRelease(service)
    return values


def _health() -> Tuple[Optional[int], Optional[int]]:
    data = _battery_registry("CycleCount", "DesignCapacity", "NominalChargeCapacity", "AppleRawMaxCapacity", "MaxCapacity")
    design = data["DesignCapacity"]
    # System Settings uses the nominal charge capacity; older Macs only have
    # the raw maximum (Apple Silicon) or report MaxCapacity in mAh (Intel).
    full = data["NominalChargeCapacity"] or data["AppleRawMaxCapacity"]
    if full is None and (data["MaxCapacity"] or 0) > 100:
        full = data["MaxCapacity"]
    # A new battery can hold slightly more than its design capacity; System
    # Settings shows that as 100%.
    health = min(100, round(full * 100 / design)) if full and design else None
    return data["CycleCount"], health


@dataclass(frozen=True)
class Battery:
    """A snapshot of the internal battery."""

    percent: int
    """Charge level, from 0 to 100."""
    charging: bool
    """Whether it is charging right now (``False`` once full, even if plugged in)."""
    plugged_in: bool
    """Whether the Mac is running on AC power."""
    time_remaining: Optional[timedelta]
    """Time until empty on battery, or until full while charging.
    ``None`` while macOS is still estimating, or when fully charged."""
    cycle_count: Optional[int] = None
    """How many full charge cycles the battery has gone through."""
    health: Optional[int] = None
    """Maximum capacity compared with when it was new, in percent, as shown in
    System Settings › Battery › Battery Health."""


def _minutes(value: Optional[int]) -> Optional[timedelta]:
    # IOKit reports -1 while it is still estimating.
    return timedelta(minutes=value) if value is not None and value >= 0 else None


def battery() -> Optional[Battery]:
    """Return the internal battery's status, or ``None`` on a Mac without one (e.g. a Mac mini)."""
    io = _iokit()
    with _cf.owned(io.IOPSCopyPowerSourcesInfo()) as info, _cf.owned(io.IOPSCopyPowerSourcesList(info)) as sources:
        for source in _cf.items(sources):
            description = io.IOPSGetPowerSourceDescription(info, source)
            if _cf.to_str(_cf.lookup(description, "Type")) != "InternalBattery":
                continue
            if not _cf.to_bool(_cf.lookup(description, "Is Present")):
                continue

            current = _cf.to_int(_cf.lookup(description, "Current Capacity")) or 0
            maximum = _cf.to_int(_cf.lookup(description, "Max Capacity")) or 100
            charging = _cf.to_bool(_cf.lookup(description, "Is Charging"))
            plugged_in = _cf.to_str(_cf.lookup(description, "Power Source State")) == "AC Power"
            key = "Time to Full Charge" if charging else "Time to Empty"
            remaining = _minutes(_cf.to_int(_cf.lookup(description, key)))

            cycle_count, health = _health()
            return Battery(
                percent=round(current * 100 / maximum) if maximum else 0,
                charging=charging,
                plugged_in=plugged_in,
                time_remaining=remaining if charging or not plugged_in else None,
                cycle_count=cycle_count,
                health=health,
            )
    return None


@contextmanager
def keep_awake(*, display: bool = False, reason: str = "pymacos keep_awake") -> Iterator[None]:
    """
    Keep the Mac from going to sleep while the block runs.

    By default the display may still turn off; ``display=True`` keeps it on
    too. ``reason`` shows up in ``pmset -g assertions`` and Activity Monitor.
    It works as a decorator as well::

        @macos.power.keep_awake()
        def backup():
            ...

    Closing the lid still puts a laptop to sleep, as with ``caffeinate``.
    """
    io = _iokit()
    kind = "PreventUserIdleDisplaySleep" if display else "PreventUserIdleSystemSleep"
    assertion = ctypes.c_uint32()
    with _cf.owned(_cf.string(kind)) as kind_ref, _cf.owned(_cf.string(reason)) as reason_ref:
        status = io.IOPMAssertionCreateWithName(kind_ref, kIOPMAssertionLevelOn, reason_ref, ctypes.byref(assertion))
    if status != kIOReturnSuccess:
        raise MacOSError("could not create the power assertion (IOReturn {:#x})".format(status & 0xFFFFFFFF))

    try:
        yield
    finally:
        io.IOPMAssertionRelease(assertion.value)


def sleep() -> None:
    """Put the Mac to sleep right away, like  › Sleep."""
    run(["pmset", "sleepnow"])


def sleep_display() -> None:
    """
    Turn the display off right away; the Mac keeps running.

    With *Require password after screen saver begins or display is turned off*
    set to *Immediately* (the default), this also locks the screen.
    """
    run(["pmset", "displaysleepnow"])
