# -*- coding: utf-8 -*-

"""
Read and change the preferences of apps and of the system, like the ``defaults`` command, with Python values.

::

    macos.defaults.read("com.apple.dock", "autohide")            # True
    macos.defaults.write("com.apple.dock", "autohide", True)
    macos.defaults.read("NSGlobalDomain", "AppleInterfaceStyle")  # 'Dark'
    macos.defaults.delete("com.example.app", "cache-size")
    macos.defaults.read("com.apple.screencapture")                # {'location': '~/Desktop', ...}

Values are ``bool``, ``int``, ``float``, ``str``, ``bytes``,
:class:`~datetime.datetime`, and lists and dicts of them, like property lists.
Goes through CFPreferences, as apps do, so changes reach ``cfprefsd`` at once;
most apps only read them when they start, so restart them to see a change.
"""

import ctypes
from functools import lru_cache
from typing import Any, List, Optional

from . import _cf
from ._system import framework

__all__ = ["read", "write", "delete", "keys", "GLOBAL"]

GLOBAL = "NSGlobalDomain"
"""The preferences every app shares, such as the appearance: ``defaults -g``."""

_GLOBAL_NAMES = {GLOBAL, "-g", "-globalDomain", ".GlobalPreferences"}
_MISSING = object()


@lru_cache(maxsize=None)
def _preferences() -> ctypes.CDLL:
    cf = framework("CoreFoundation")
    pointer = ctypes.c_void_p
    cf.CFPreferencesCopyAppValue.argtypes = (pointer, pointer)
    cf.CFPreferencesCopyAppValue.restype = pointer
    cf.CFPreferencesSetAppValue.argtypes = (pointer, pointer, pointer)
    cf.CFPreferencesSetAppValue.restype = None
    cf.CFPreferencesAppSynchronize.argtypes = (pointer,)
    cf.CFPreferencesAppSynchronize.restype = ctypes.c_bool
    cf.CFPreferencesCopyKeyList.argtypes = (pointer, pointer, pointer)
    cf.CFPreferencesCopyKeyList.restype = pointer
    return cf


def _check(domain: str) -> None:
    if not domain or not domain.strip():
        raise ValueError("domain must not be empty")


def _domain(domain: str) -> int:
    """The domain as CFPreferences names it: an owned string, or the global domain's constant."""
    if domain in _GLOBAL_NAMES:
        constant = ctypes.c_void_p.in_dll(_preferences(), "kCFPreferencesAnyApplication").value
        return _cf.retain(int(constant or 0))
    return _cf.string(domain)


def keys(domain: str) -> List[str]:
    """The keys the domain has, sorted, such as ``["autohide", "orientation", ...]`` for ``"com.apple.dock"``."""
    _check(domain)
    cf = _preferences()
    user = ctypes.c_void_p.in_dll(cf, "kCFPreferencesCurrentUser").value
    host = ctypes.c_void_p.in_dll(cf, "kCFPreferencesAnyHost").value
    with _cf.owned(_domain(domain)) as name, _cf.owned(cf.CFPreferencesCopyKeyList(name, user, host)) as found:
        return sorted(_cf.to_python(found) or [])


def read(domain: str, key: Optional[str] = None, *, default: Any = None) -> Any:
    """
    The value of ``key`` in ``domain`` (an app's bundle ID, or :data:`GLOBAL`), or ``default`` when it isn't set.

    Without ``key``, returns all the domain's values, as a ``dict``.
    """
    _check(domain)
    if key is None:
        return {name: read(domain, name) for name in keys(domain)}
    cf = _preferences()
    with _cf.owned(_domain(domain)) as name, _cf.owned(_cf.string(key)) as wanted:
        with _cf.owned(cf.CFPreferencesCopyAppValue(wanted, name)) as value:
            return _cf.to_python(value) if value else default


def write(domain: str, key: str, value: Any) -> None:
    """
    Set ``key`` in ``domain`` to ``value``, as ``defaults write`` does, but with its Python type.

    ``True`` is written as a boolean, ``3`` as an integer, lists as arrays and
    dicts as dictionaries: no ``-bool`` or ``-int`` flags to get right.
    """
    _check(domain)
    if value is None:
        raise ValueError("value must not be None; use delete() to remove a key")
    cf = _preferences()
    with _cf.owned(_domain(domain)) as name, _cf.owned(_cf.string(key)) as wanted:
        with _cf.owned(_cf.from_python(value)) as converted:
            cf.CFPreferencesSetAppValue(wanted, converted, name)
        cf.CFPreferencesAppSynchronize(name)


def delete(domain: str, key: str) -> bool:
    """Remove ``key`` from ``domain``; return whether it was set."""
    existed = read(domain, key, default=_MISSING) is not _MISSING
    cf = _preferences()
    with _cf.owned(_domain(domain)) as name, _cf.owned(_cf.string(key)) as wanted:
        cf.CFPreferencesSetAppValue(wanted, None, name)
        cf.CFPreferencesAppSynchronize(name)
    return existed
