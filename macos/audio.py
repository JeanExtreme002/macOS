# -*- coding: utf-8 -*-

"""
List audio devices and switch the default output and input.

::

    [device.name for device in macos.audio.outputs()]   # ['MacBook Pro Speakers', 'AirPods Pro']
    macos.audio.default_output()                          # Device(name='MacBook Pro Speakers', ...)
    macos.audio.set_output("AirPods Pro")
    macos.audio.set_input("MacBook Pro Microphone")

Talks to CoreAudio directly, like the Sound settings do. Switching needs no
permission.
"""

import ctypes
import struct
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Union

from . import _cf
from ._system import framework
from .errors import MacOSError

__all__ = ["Device", "devices", "outputs", "inputs", "default_output", "default_input", "set_output", "set_input"]


def _code(text: str) -> int:
    """A CoreAudio four-character code, such as ``'dev#'``."""
    return int(struct.unpack(">I", text.encode("ascii"))[0])


_SYSTEM = 1  # kAudioObjectSystemObject
_GLOBAL, _OUTPUT, _INPUT = _code("glob"), _code("outp"), _code("inpt")
_MAIN_ELEMENT = 0

_TRANSPORTS = {
    "bltn": "builtin",
    "usb ": "usb",
    "blue": "bluetooth",
    "blea": "bluetooth",
    "hdmi": "hdmi",
    "dprt": "displayport",
    "airp": "airplay",
    "thun": "thunderbolt",
    "pci ": "pci",
    "virt": "virtual",
    "grup": "aggregate",
    "cont": "continuity",
    "avb ": "avb",
}


class _Address(ctypes.Structure):
    _fields_ = [("selector", ctypes.c_uint32), ("scope", ctypes.c_uint32), ("element", ctypes.c_uint32)]


@dataclass(frozen=True)
class Device:
    """An audio device: speakers, headphones, a microphone, a display's audio..."""

    id: int
    name: str
    """As shown in System Settings › Sound, in the system's language."""
    uid: str
    """A stable identifier that survives reconnecting the device."""
    transport: str
    """How it's connected: ``'builtin'``, ``'usb'``, ``'bluetooth'``, ``'hdmi'``, ``'airplay'``..."""
    is_output: bool
    is_input: bool


@lru_cache(maxsize=None)
def _core_audio() -> ctypes.CDLL:
    audio = framework("CoreAudio")
    address = ctypes.POINTER(_Address)
    size = ctypes.POINTER(ctypes.c_uint32)
    audio.AudioObjectGetPropertyDataSize.argtypes = (ctypes.c_uint32, address, ctypes.c_uint32, ctypes.c_void_p, size)
    audio.AudioObjectGetPropertyDataSize.restype = ctypes.c_int32
    audio.AudioObjectGetPropertyData.argtypes = (
        ctypes.c_uint32,
        address,
        ctypes.c_uint32,
        ctypes.c_void_p,
        size,
        ctypes.c_void_p,
    )
    audio.AudioObjectGetPropertyData.restype = ctypes.c_int32
    audio.AudioObjectSetPropertyData.argtypes = (
        ctypes.c_uint32,
        address,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    audio.AudioObjectSetPropertyData.restype = ctypes.c_int32
    return audio


def _property(target: int, selector: str, scope: int = _GLOBAL) -> Optional[bytes]:
    """Raw bytes of a CoreAudio property, or ``None`` if the object doesn't have it."""
    audio = _core_audio()
    address = _Address(_code(selector), scope, _MAIN_ELEMENT)
    size = ctypes.c_uint32()
    if audio.AudioObjectGetPropertyDataSize(target, ctypes.byref(address), 0, None, ctypes.byref(size)) != 0:
        return None
    buffer = ctypes.create_string_buffer(size.value)
    if audio.AudioObjectGetPropertyData(target, ctypes.byref(address), 0, None, ctypes.byref(size), buffer) != 0:
        return None
    return buffer.raw[: size.value]


def _string(target: int, selector: str) -> str:
    raw = _property(target, selector)
    if not raw:
        return ""
    # AudioHardwareBase.h, for kAudioObjectPropertyName and
    # kAudioDevicePropertyDeviceUID: "The caller is responsible for releasing
    # the returned CFObject", so the string is released once read.
    with _cf.owned(ctypes.c_void_p.from_buffer_copy(raw).value) as ref:
        return _cf.to_str(ref) or ""


def _uint(target: int, selector: str) -> Optional[int]:
    raw = _property(target, selector)
    return int(struct.unpack("I", raw[:4])[0]) if raw and len(raw) >= 4 else None


def _device(device_id: int) -> Device:
    transport = _uint(device_id, "tran")
    code = struct.pack(">I", transport).decode("ascii", "replace") if transport else ""
    return Device(
        id=device_id,
        name=_string(device_id, "lnam"),
        uid=_string(device_id, "uid "),
        transport=_TRANSPORTS.get(code, code.strip() or "unknown"),
        # A device plays (or records) when it has output (or input) streams.
        is_output=bool(_property(device_id, "stm#", _OUTPUT)),
        is_input=bool(_property(device_id, "stm#", _INPUT)),
    )


def devices() -> List[Device]:
    """Return every audio device, outputs and inputs."""
    raw = _property(_SYSTEM, "dev#") or b""
    ids = struct.unpack("{}I".format(len(raw) // 4), raw)
    return [_device(device_id) for device_id in ids]


def outputs() -> List[Device]:
    """Return the devices that play sound (speakers, headphones, displays...)."""
    return [device for device in devices() if device.is_output]


def inputs() -> List[Device]:
    """Return the devices that record sound (microphones...)."""
    return [device for device in devices() if device.is_input]


def _default(selector: str) -> Optional[Device]:
    device_id = _uint(_SYSTEM, selector)
    return _device(device_id) if device_id else None


def default_output() -> Optional[Device]:
    """Return the device sound currently plays through."""
    return _default("dOut")


def default_input() -> Optional[Device]:
    """Return the device currently used to record (the microphone apps get by default)."""
    return _default("dIn ")


def _find(target: Union[str, Device], candidates: List[Device], kind: str) -> Device:
    if isinstance(target, Device):
        target = target.uid
    exact = [device for device in candidates if target in (device.uid, device.name)]
    if exact:
        return exact[0]
    wanted = target.casefold()
    loose = [device for device in candidates if wanted in device.name.casefold()]
    if len(loose) == 1:
        return loose[0]
    names = ", ".join(repr(device.name) for device in candidates)
    if not loose:
        raise ValueError("no {} device matches {!r}; available: {}".format(kind, target, names))
    raise ValueError("{!r} matches several {} devices ({}); use the full name".format(target, kind, names))


def _set_default(selector: str, device: Device) -> None:
    value = ctypes.c_uint32(device.id)
    address = _Address(_code(selector), _GLOBAL, _MAIN_ELEMENT)
    status = _core_audio().AudioObjectSetPropertyData(
        _SYSTEM, ctypes.byref(address), 0, None, ctypes.sizeof(value), ctypes.byref(value)
    )
    if status != 0:
        raise MacOSError("could not switch to {!r} (OSStatus {})".format(device.name, status))


def set_output(device: Union[str, Device]) -> Device:
    """
    Play sound through ``device`` and return it.

    ``device`` is a :class:`Device`, its full name, its uid, or part of its
    name when that matches only one device (``"AirPods"``).
    """
    chosen = _find(device, outputs(), "output")
    _set_default("dOut", chosen)
    return chosen


def set_input(device: Union[str, Device]) -> Device:
    """Record from ``device`` by default and return it. ``device`` works as in :func:`set_output`."""
    chosen = _find(device, inputs(), "input")
    _set_default("dIn ", chosen)
    return chosen
