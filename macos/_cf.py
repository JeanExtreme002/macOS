# -*- coding: utf-8 -*-

"""
CoreFoundation helpers over ctypes: creating and reading ``CFString``,
``CFData`` and ``CFDictionary`` values, and releasing them.

Every ``CF*Create``/``Copy`` result is owned by the caller and must be passed
to :func:`release`; :func:`owned` does that automatically at the end of a
``with`` block.
"""

import ctypes
from contextlib import contextmanager
from functools import lru_cache
from typing import Dict, Iterator, Optional

from ._system import framework

CFTypeRef = ctypes.c_void_p
CFIndex = ctypes.c_long

kCFStringEncodingUTF8 = 0x08000100


@lru_cache(maxsize=None)
def lib() -> ctypes.CDLL:
    cf = framework("CoreFoundation")

    cf.CFRelease.argtypes = (CFTypeRef,)
    cf.CFRelease.restype = None

    cf.CFStringCreateWithBytes.argtypes = (CFTypeRef, ctypes.c_char_p, CFIndex, ctypes.c_uint32, ctypes.c_bool)
    cf.CFStringCreateWithBytes.restype = CFTypeRef
    cf.CFStringGetLength.argtypes = (CFTypeRef,)
    cf.CFStringGetLength.restype = CFIndex
    cf.CFStringGetMaximumSizeForEncoding.argtypes = (CFIndex, ctypes.c_uint32)
    cf.CFStringGetMaximumSizeForEncoding.restype = CFIndex
    cf.CFStringGetCString.argtypes = (CFTypeRef, ctypes.c_char_p, CFIndex, ctypes.c_uint32)
    cf.CFStringGetCString.restype = ctypes.c_bool

    cf.CFDataCreate.argtypes = (CFTypeRef, ctypes.c_char_p, CFIndex)
    cf.CFDataCreate.restype = CFTypeRef
    cf.CFDataGetLength.argtypes = (CFTypeRef,)
    cf.CFDataGetLength.restype = CFIndex
    cf.CFDataGetBytePtr.argtypes = (CFTypeRef,)
    cf.CFDataGetBytePtr.restype = ctypes.c_void_p

    cf.CFDictionaryCreate.argtypes = (
        CFTypeRef,
        ctypes.POINTER(CFTypeRef),
        ctypes.POINTER(CFTypeRef),
        CFIndex,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    cf.CFDictionaryCreate.restype = CFTypeRef

    cf.CFGetTypeID.argtypes = (CFTypeRef,)
    cf.CFGetTypeID.restype = ctypes.c_ulong
    cf.CFBooleanGetTypeID.argtypes = ()
    cf.CFBooleanGetTypeID.restype = ctypes.c_ulong
    cf.CFBooleanGetValue.argtypes = (CFTypeRef,)
    cf.CFBooleanGetValue.restype = ctypes.c_bool
    cf.CFStringGetTypeID.argtypes = ()
    cf.CFStringGetTypeID.restype = ctypes.c_ulong

    cf.CFPreferencesAppSynchronize.argtypes = (CFTypeRef,)
    cf.CFPreferencesAppSynchronize.restype = ctypes.c_bool
    cf.CFPreferencesCopyAppValue.argtypes = (CFTypeRef, CFTypeRef)
    cf.CFPreferencesCopyAppValue.restype = CFTypeRef
    return cf


def constant(library: ctypes.CDLL, name: str) -> int:
    """Read a global ``CFTypeRef`` constant (e.g. ``kSecClass``) from a library."""
    value = CFTypeRef.in_dll(library, name).value
    if value is None:
        raise LookupError("{} is NULL".format(name))
    return value


def release(ref: Optional[int]) -> None:
    if ref:
        lib().CFRelease(ref)


@contextmanager
def owned(ref: Optional[int]) -> Iterator[Optional[int]]:
    """Yield ``ref`` and ``CFRelease`` it when the block exits."""
    try:
        yield ref
    finally:
        release(ref)


def string(text: str) -> int:
    """Create a ``CFString`` (caller owns it). Embedded NUL characters are kept."""
    raw = text.encode("utf-8")
    return lib().CFStringCreateWithBytes(None, raw, len(raw), kCFStringEncodingUTF8, False)


def is_type(ref: Optional[int], type_id: int) -> bool:
    return bool(ref) and lib().CFGetTypeID(ref) == type_id


def to_str(ref: Optional[int]) -> Optional[str]:
    """Copy a ``CFString`` into a Python string (``None`` for anything else)."""
    if not is_type(ref, lib().CFStringGetTypeID()):
        return None
    cf = lib()
    size = cf.CFStringGetMaximumSizeForEncoding(cf.CFStringGetLength(ref), kCFStringEncodingUTF8) + 1
    buffer = ctypes.create_string_buffer(size)
    if not cf.CFStringGetCString(ref, buffer, size, kCFStringEncodingUTF8):
        return None
    return buffer.value.decode("utf-8")


def data(payload: bytes) -> int:
    """Create a ``CFData`` (caller owns it)."""
    return lib().CFDataCreate(None, payload, len(payload))


def to_bool(ref: Optional[int]) -> bool:
    """Read a ``CFBoolean`` (``False`` for anything else)."""
    cf = lib()
    return is_type(ref, cf.CFBooleanGetTypeID()) and bool(cf.CFBooleanGetValue(ref))


def to_bytes(ref: Optional[int]) -> bytes:
    """Copy the contents of a ``CFData`` into Python bytes."""
    if not ref:
        return b""
    cf = lib()
    return ctypes.string_at(cf.CFDataGetBytePtr(ref), cf.CFDataGetLength(ref))


def dictionary(items: Dict[int, int]) -> int:
    """
    Create a ``CFDictionary`` from CF keys and values (caller owns it).

    Uses the standard ``kCFType`` callbacks, so the dictionary retains its keys
    and values: the caller may release its own references right after.
    """
    cf = lib()
    count = len(items)
    keys = (CFTypeRef * count)(*items.keys())
    values = (CFTypeRef * count)(*items.values())
    key_callbacks = ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryKeyCallBacks"))
    value_callbacks = ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryValueCallBacks"))
    return cf.CFDictionaryCreate(None, keys, values, count, key_callbacks, value_callbacks)
