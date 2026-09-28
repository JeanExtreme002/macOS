# -*- coding: utf-8 -*-

"""
List audio devices and switch the default output and input.

::

    [device.name for device in macos.audio.outputs()]   # ['MacBook Pro Speakers', 'AirPods Pro']
    macos.audio.default_output()                          # Device(name='MacBook Pro Speakers', ...)
    macos.audio.set_output("AirPods Pro")
    macos.audio.set_input("MacBook Pro Microphone")
    macos.audio.mute_input()                              # mute the microphone

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
from .errors import MacOSError, NotSupportedError

__all__ = [
    "Device",
    "devices",
    "outputs",
    "inputs",
    "default_output",
    "default_input",
    "set_output",
    "set_input",
    "input_volume",
    "set_input_volume",
    "input_muted",
    "mute_input",
]


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


def _property(target: int, selector: str, scope: int = _GLOBAL, element: int = _MAIN_ELEMENT) -> Optional[bytes]:
    """Raw bytes of a CoreAudio property, or ``None`` if the object doesn't have it."""
    audio = _core_audio()
    address = _Address(_code(selector), scope, element)
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


def _uint(target: int, selector: str, scope: int = _GLOBAL, element: int = _MAIN_ELEMENT) -> Optional[int]:
    raw = _property(target, selector, scope, element)
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


# The microphone's volume and mute, on the default input device or another one.


def _input_device(device: Union[str, Device, None]) -> Device:
    if device is None:
        current = default_input()
        if current is None:
            raise NotSupportedError("this Mac has no microphone")
        return current
    return _find(device, inputs(), "input")


def _input_channels(device: Device) -> int:
    """How many input channels the device has, from its stream configuration (an AudioBufferList)."""
    raw = _property(device.id, "slay", _INPUT) or b""
    if len(raw) < 4:
        return 0
    buffers = struct.unpack("I", raw[:4])[0]
    # Each AudioBuffer is 16 bytes (channels, byte size, data pointer), after 8 bytes of header.
    offsets = [8 + 16 * index for index in range(buffers) if len(raw) >= 24 + 16 * index]
    return sum(struct.unpack("I", raw[offset : offset + 4])[0] for offset in offsets)


def _elements(device: Device, selector: str) -> List[int]:
    """The elements that have ``selector`` on the input side: the main one, or each of the device's channels."""
    if _property(device.id, selector, _INPUT, 0) is not None:
        return [0]
    channels = range(1, _input_channels(device) + 1)
    return [channel for channel in channels if _property(device.id, selector, _INPUT, channel) is not None]


def _set_input(device: Device, selector: str, elements: List[int], value: ctypes._SimpleCData) -> None:
    audio = _core_audio()
    for element in elements:
        address = _Address(_code(selector), _INPUT, element)
        status = audio.AudioObjectSetPropertyData(
            device.id, ctypes.byref(address), 0, None, ctypes.sizeof(value), ctypes.byref(value)
        )
        if status != 0:
            raise MacOSError("could not change {!r} (OSStatus {})".format(device.name, status))


def input_volume(device: Union[str, Device, None] = None) -> float:
    """
    The microphone's input volume, from 0.0 to 1.0, as the slider in System Settings › Sound › Input.

    ``device`` works as in :func:`set_input`; by default, the default input.
    """
    chosen = _input_device(device)
    levels = [
        struct.unpack("f", raw[:4])[0]
        for raw in (_property(chosen.id, "volm", _INPUT, element) for element in _elements(chosen, "volm"))
        if raw and len(raw) >= 4
    ]
    if not levels:
        raise NotSupportedError("{!r} has no adjustable input volume".format(chosen.name))
    return round(sum(levels) / len(levels), 3)


def set_input_volume(value: float, *, device: Union[str, Device, None] = None) -> None:
    """Set the microphone's input volume, from 0.0 to 1.0. ``device`` works as in :func:`input_volume`."""
    if not 0.0 <= value <= 1.0:
        raise ValueError("volume must be from 0.0 to 1.0, not {}".format(value))
    chosen = _input_device(device)
    elements = _elements(chosen, "volm")
    if not elements:
        raise NotSupportedError("{!r} has no adjustable input volume".format(chosen.name))
    _set_input(chosen, "volm", elements, ctypes.c_float(value))


def input_muted(device: Union[str, Device, None] = None) -> bool:
    """Whether the microphone is muted. ``device`` works as in :func:`input_volume`."""
    chosen = _input_device(device)
    elements = _elements(chosen, "mute")
    if not elements:
        raise NotSupportedError("{!r} can't be muted; use set_input_volume(0.0)".format(chosen.name))
    return all(_uint(chosen.id, "mute", _INPUT, element) for element in elements)


def mute_input(on: bool = True, *, device: Union[str, Device, None] = None) -> None:
    """
    Mute the microphone (or unmute it with ``on=False``), for every app at once.

    Handy as a "mute me" shortcut in meetings. ``device`` works as in
    :func:`input_volume`. Devices without a mute switch raise
    :class:`~macos.errors.NotSupportedError`: set their volume to 0 instead.
    """
    chosen = _input_device(device)
    elements = _elements(chosen, "mute")
    if not elements:
        raise NotSupportedError("{!r} can't be muted; use set_input_volume(0.0)".format(chosen.name))
    _set_input(chosen, "mute", elements, ctypes.c_uint32(1 if on else 0))
