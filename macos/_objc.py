# -*- coding: utf-8 -*-

"""
A minimal Objective-C bridge over ctypes.

Just enough of the runtime to message Cocoa objects without PyObjC:
``send(obj, "selector:", arg, argtypes=(...), restype=...)``.

``objc_msgSend`` is a trampoline, not a real variadic function: on arm64 it
must be called through a prototype whose argument and return types match the
method exactly, or arguments land in the wrong registers. That is why every
call names its ``argtypes``/``restype`` instead of relying on ctypes defaults.
"""

import ctypes
import os
import platform
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator, Optional, Sequence

from ._system import framework, require_macos

id = ctypes.c_void_p
SEL = ctypes.c_void_p
Class = ctypes.c_void_p
NSUInteger = ctypes.c_ulong
NSInteger = ctypes.c_long
BOOL = ctypes.c_bool


@lru_cache(maxsize=None)
def _libobjc() -> ctypes.CDLL:
    require_macos()
    lib = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    # Foundation defines NSString, NSArray and NSBundle, which the helpers
    # below use directly. Load it explicitly instead of relying on AppKit (or
    # the interpreter) having pulled it in already.
    framework("Foundation")

    lib.objc_getClass.argtypes = (ctypes.c_char_p,)
    lib.objc_getClass.restype = Class
    lib.sel_registerName.argtypes = (ctypes.c_char_p,)
    lib.sel_registerName.restype = SEL
    lib.objc_autoreleasePoolPush.argtypes = ()
    lib.objc_autoreleasePoolPush.restype = ctypes.c_void_p
    lib.objc_autoreleasePoolPop.argtypes = (ctypes.c_void_p,)
    lib.objc_autoreleasePoolPop.restype = None
    return lib


def _needs_stret(restype: Any) -> bool:
    """
    Whether a method returning ``restype`` must go through ``objc_msgSend_stret``.

    On x86_64, structs larger than 16 bytes (a CGRect, for example) come back
    through a hidden pointer, which plain ``objc_msgSend`` doesn't handle.
    arm64 has no such variant: ``objc_msgSend`` covers every return type.
    """
    return (
        platform.machine() == "x86_64"
        and isinstance(restype, type)
        and issubclass(restype, ctypes.Structure)
        and ctypes.sizeof(restype) > 16
    )


@lru_cache(maxsize=None)
def _prototype(restype: Any, argtypes: Sequence[Any]) -> Any:
    signature = ctypes.CFUNCTYPE(restype, id, SEL, *argtypes)
    # Declaring the struct return type makes ctypes pass the hidden pointer
    # itself, which is exactly the calling convention _stret expects.
    entry = _libobjc().objc_msgSend_stret if _needs_stret(restype) else _libobjc().objc_msgSend
    address = ctypes.cast(entry, ctypes.c_void_p).value
    assert address is not None
    return signature(address)


@lru_cache(maxsize=None)
def cls(name: str) -> int:
    """Look up an Objective-C class by name."""
    pointer = _libobjc().objc_getClass(name.encode())
    if not pointer:
        raise LookupError("Objective-C class {!r} is not loaded".format(name))
    return pointer


@lru_cache(maxsize=None)
def sel(name: str) -> int:
    """Register (or look up) a selector by name."""
    return _libobjc().sel_registerName(name.encode())


def send(receiver: Optional[int], selector: str, *args: Any, argtypes: Sequence[Any] = (), restype: Any = id) -> Any:
    """Send ``selector`` to ``receiver`` and return the result as ``restype``."""
    if len(args) != len(argtypes):
        raise TypeError("send({!r}) got {} arguments but {} argtypes".format(selector, len(args), len(argtypes)))
    return _prototype(restype, tuple(argtypes))(receiver, sel(selector), *args)


@contextmanager
def autorelease_pool() -> Iterator[None]:
    """Drain autoreleased Cocoa objects created inside the block."""
    lib = _libobjc()
    pool = lib.objc_autoreleasePoolPush()
    try:
        yield
    finally:
        lib.objc_autoreleasePoolPop(pool)


NSUTF8StringEncoding = 4


def nsstring(text: str) -> int:
    """
    Create an autoreleased ``NSString`` from a Python string.

    Built from an explicit byte length, not a C string, so an embedded NUL
    character is kept instead of silently ending the string.
    """
    raw = text.encode("utf-8")
    string = send(cls("NSString"), "alloc")
    string = send(
        string,
        "initWithBytes:length:encoding:",
        raw,
        len(raw),
        NSUTF8StringEncoding,
        argtypes=(ctypes.c_char_p, NSUInteger, NSUInteger),
    )
    return send(string, "autorelease")


def pystring(obj: Optional[int]) -> Optional[str]:
    """Convert an ``NSString`` to a Python string (``None`` stays ``None``), NUL characters included."""
    if not obj:
        return None
    data = send(obj, "dataUsingEncoding:", NSUTF8StringEncoding, argtypes=(NSUInteger,))
    if not data:
        return None
    length = send(data, "length", restype=NSUInteger)
    return ctypes.string_at(send(data, "bytes", restype=ctypes.c_void_p), length).decode("utf-8") if length else ""


def nsdata(payload: bytes) -> int:
    """Create an autoreleased ``NSData`` holding a copy of ``payload``."""
    return send(
        cls("NSData"), "dataWithBytes:length:", payload, len(payload), argtypes=(ctypes.c_char_p, NSUInteger)
    )


def pybytes(obj: Optional[int]) -> Optional[bytes]:
    """Copy the contents of an ``NSData`` into Python bytes (``None`` stays ``None``)."""
    if not obj:
        return None
    length = send(obj, "length", restype=NSUInteger)
    return ctypes.string_at(send(obj, "bytes", restype=ctypes.c_void_p), length) if length else b""


def nsarray(obj: Optional[int]) -> Iterator[int]:
    """Iterate over the elements of an ``NSArray``."""
    if not obj:
        return
    for index in range(send(obj, "count", restype=NSUInteger)):
        yield send(obj, "objectAtIndex:", index, argtypes=(NSUInteger,))


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class CGRect(ctypes.Structure):
    _fields_ = [("origin", CGPoint), ("size", CGSize)]


def nsarray_of(objects: Sequence[int]) -> int:
    """Create an autoreleased ``NSArray`` holding ``objects``."""
    items = (ctypes.c_void_p * len(objects))(*objects)
    return send(cls("NSArray"), "arrayWithObjects:count:", items, len(objects), argtypes=(ctypes.c_void_p, NSUInteger))


def file_url(path: "os.PathLike[str] | str") -> int:
    """Create an autoreleased file ``NSURL`` for ``path``."""
    return send(cls("NSURL"), "fileURLWithPath:", nsstring(os.fspath(path)), argtypes=(id,))


def error_message(error: ctypes.c_void_p) -> Optional[str]:
    """The ``localizedDescription`` of an ``NSError`` out-parameter, or ``None`` if none was set."""
    return pystring(send(error.value, "localizedDescription")) if error.value else None


def png(rep: int) -> bytes:
    """Encode an ``NSBitmapImageRep`` as PNG bytes."""
    data = send(
        rep,
        "representationUsingType:properties:",
        4,  # NSBitmapImageFileTypePNG
        send(cls("NSDictionary"), "dictionary"),
        argtypes=(NSUInteger, id),
    )
    return pybytes(data) or b""


def new(class_name: str) -> int:
    """``[[class_name alloc] init]``, autoreleased."""
    return send(send(send(cls(class_name), "alloc"), "init"), "autorelease")


def cgimage_png(image: Optional[int]) -> bytes:
    """Encode an owned ``CGImage`` as PNG bytes, then release it. Needs AppKit loaded."""
    if not image:
        raise ValueError("no image to encode")
    try:
        rep = send(cls("NSBitmapImageRep"), "alloc")
        rep = send(rep, "initWithCGImage:", image, argtypes=(ctypes.c_void_p,))
        send(rep, "autorelease")
        return png(rep)
    finally:
        _core_foundation().CFRelease(image)


@lru_cache(maxsize=None)
def _core_foundation() -> ctypes.CDLL:
    cf = framework("CoreFoundation")
    cf.CFRelease.argtypes = (ctypes.c_void_p,)
    cf.CFRelease.restype = None
    return cf
