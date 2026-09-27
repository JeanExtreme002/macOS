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
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator, Optional, Sequence

from ._system import require_macos

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

    lib.objc_getClass.argtypes = (ctypes.c_char_p,)
    lib.objc_getClass.restype = Class
    lib.sel_registerName.argtypes = (ctypes.c_char_p,)
    lib.sel_registerName.restype = SEL
    lib.objc_autoreleasePoolPush.argtypes = ()
    lib.objc_autoreleasePoolPush.restype = ctypes.c_void_p
    lib.objc_autoreleasePoolPop.argtypes = (ctypes.c_void_p,)
    lib.objc_autoreleasePoolPop.restype = None
    return lib


@lru_cache(maxsize=None)
def _prototype(restype: Any, argtypes: Sequence[Any]) -> Any:
    signature = ctypes.CFUNCTYPE(restype, id, SEL, *argtypes)
    address = ctypes.cast(_libobjc().objc_msgSend, ctypes.c_void_p).value
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


def nsstring(text: str) -> int:
    """Create an autoreleased ``NSString`` from a Python string."""
    return send(cls("NSString"), "stringWithUTF8String:", text.encode("utf-8"), argtypes=(ctypes.c_char_p,))


def pystring(obj: Optional[int]) -> Optional[str]:
    """Convert an ``NSString`` to a Python string (``None`` stays ``None``)."""
    if not obj:
        return None
    raw = send(obj, "UTF8String", restype=ctypes.c_char_p)
    return raw.decode("utf-8") if raw is not None else None


def nsarray(obj: Optional[int]) -> Iterator[int]:
    """Iterate over the elements of an ``NSArray``."""
    if not obj:
        return
    for index in range(send(obj, "count", restype=NSUInteger)):
        yield send(obj, "objectAtIndex:", index, argtypes=(NSUInteger,))
