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
import plistlib
from typing import Any, Dict, Iterator, List, Optional

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

    cf.CFArrayGetCount.argtypes = (CFTypeRef,)
    cf.CFArrayGetCount.restype = CFIndex
    cf.CFArrayGetValueAtIndex.argtypes = (CFTypeRef, CFIndex)
    cf.CFArrayGetValueAtIndex.restype = CFTypeRef
    cf.CFDictionaryGetValue.argtypes = (CFTypeRef, CFTypeRef)
    cf.CFDictionaryGetValue.restype = CFTypeRef
    cf.CFNumberGetTypeID.argtypes = ()
    cf.CFNumberGetTypeID.restype = ctypes.c_ulong
    cf.CFNumberGetValue.argtypes = (CFTypeRef, ctypes.c_long, ctypes.c_void_p)
    cf.CFNumberGetValue.restype = ctypes.c_bool
    cf.CFNumberCreate.argtypes = (CFTypeRef, ctypes.c_long, ctypes.c_void_p)
    cf.CFNumberCreate.restype = CFTypeRef

    cf.CFURLCreateFromFileSystemRepresentation.argtypes = (CFTypeRef, ctypes.c_char_p, CFIndex, ctypes.c_bool)
    cf.CFURLCreateFromFileSystemRepresentation.restype = CFTypeRef

    cf.CFDictionaryCreateMutableCopy.argtypes = (CFTypeRef, CFIndex, CFTypeRef)
    cf.CFDictionaryCreateMutableCopy.restype = CFTypeRef
    cf.CFDictionarySetValue.argtypes = (CFTypeRef, CFTypeRef, CFTypeRef)
    cf.CFDictionarySetValue.restype = None

    cf.CFPropertyListCreateData.argtypes = (CFTypeRef, CFTypeRef, CFIndex, ctypes.c_ulong, ctypes.c_void_p)
    cf.CFPropertyListCreateData.restype = CFTypeRef
    cf.CFPropertyListCreateWithData.argtypes = (CFTypeRef, CFTypeRef, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)
    cf.CFPropertyListCreateWithData.restype = CFTypeRef
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


kCFNumberLongLongType = 11
kCFNumberDoubleType = 13


def number(value: float) -> int:
    """Create a ``CFNumber`` (caller owns it): an integer stays an integer."""
    if isinstance(value, int) and not isinstance(value, bool):
        integer = ctypes.c_longlong(value)
        return lib().CFNumberCreate(None, kCFNumberLongLongType, ctypes.byref(integer))
    real = ctypes.c_double(value)
    return lib().CFNumberCreate(None, kCFNumberDoubleType, ctypes.byref(real))


def file_url(path: str) -> int:
    """Create a file ``CFURL`` for ``path`` (caller owns it)."""
    raw = path.encode("utf-8")
    return lib().CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)


def to_int(ref: Optional[int]) -> Optional[int]:
    """Read a ``CFNumber`` as an integer (``None`` for anything else)."""
    cf = lib()
    if not is_type(ref, cf.CFNumberGetTypeID()):
        return None
    value = ctypes.c_longlong()
    cf.CFNumberGetValue(ref, kCFNumberLongLongType, ctypes.byref(value))
    return value.value


def items(ref: Optional[int]) -> List[int]:
    """The elements of a ``CFArray`` (borrowed references: don't release them)."""
    if not ref:
        return []
    cf = lib()
    return [cf.CFArrayGetValueAtIndex(ref, index) for index in range(cf.CFArrayGetCount(ref))]


def lookup(ref: Optional[int], key: str) -> Optional[int]:
    """The value for ``key`` in a ``CFDictionary`` (borrowed), or ``None``."""
    if not ref:
        return None
    with owned(string(key)) as name:
        return lib().CFDictionaryGetValue(ref, name)


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


_BINARY_PLIST = 200  # kCFPropertyListBinaryFormat_v1_0


def to_python(ref: Optional[int]) -> Any:
    """
    Convert a property-list ``CFType`` (dictionaries, arrays, strings, numbers,
    dates, data, booleans, nested) into Python objects.

    Goes through a binary property list, so every nesting level converts at once.
    """
    if not ref:
        return None
    with owned(lib().CFPropertyListCreateData(None, ref, _BINARY_PLIST, 0, None)) as data:
        if not data:
            raise ValueError("not a property list")
        return plistlib.loads(to_bytes(data))


def from_python(value: Any) -> int:
    """The reverse of :func:`to_python`: an owned ``CFType`` for a plist-compatible Python object."""
    with owned(data(plistlib.dumps(value, fmt=plistlib.FMT_BINARY))) as raw:
        ref = lib().CFPropertyListCreateWithData(None, raw, 0, None, None)
    if not ref:
        raise ValueError("not a property list")
    return ref
