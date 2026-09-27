# -*- coding: utf-8 -*-

"""
Store and retrieve passwords in the macOS Keychain.

Items are *generic passwords* identified by a ``service`` and an ``account``,
the same kind of item Keychain Access shows as "application password"::

    macos.keychain.set("my-app", "alice", "s3cret")
    macos.keychain.get("my-app", "alice")     # 's3cret'
    macos.keychain.delete("my-app", "alice")

This talks to the Security framework directly (``SecItem*``) rather than the
``security`` command, whose ``-w <password>`` flag would expose the secret to
every user through the process list.
"""

import ctypes
from functools import lru_cache
from typing import Dict, Optional

from . import _cf
from ._system import framework
from .errors import KeychainError, PermissionDeniedError

__all__ = ["get", "set", "delete"]

errSecSuccess = 0
errSecUserCanceled = -128
errSecAuthFailed = -25293
errSecDuplicateItem = -25299
errSecItemNotFound = -25300
errSecInteractionNotAllowed = -25308


@lru_cache(maxsize=None)
def _security() -> ctypes.CDLL:
    sec = framework("Security")

    sec.SecItemCopyMatching.argtypes = (_cf.CFTypeRef, ctypes.POINTER(_cf.CFTypeRef))
    sec.SecItemCopyMatching.restype = ctypes.c_int32
    sec.SecItemAdd.argtypes = (_cf.CFTypeRef, ctypes.POINTER(_cf.CFTypeRef))
    sec.SecItemAdd.restype = ctypes.c_int32
    sec.SecItemUpdate.argtypes = (_cf.CFTypeRef, _cf.CFTypeRef)
    sec.SecItemUpdate.restype = ctypes.c_int32
    sec.SecItemDelete.argtypes = (_cf.CFTypeRef,)
    sec.SecItemDelete.restype = ctypes.c_int32
    sec.SecCopyErrorMessageString.argtypes = (ctypes.c_int32, ctypes.c_void_p)
    sec.SecCopyErrorMessageString.restype = _cf.CFTypeRef
    return sec


def _check(status: int) -> None:
    if status == errSecSuccess:
        return

    with _cf.owned(_security().SecCopyErrorMessageString(status, None)) as ref:
        message = _cf.to_str(ref)

    if status in (errSecUserCanceled, errSecAuthFailed, errSecInteractionNotAllowed):
        raise PermissionDeniedError("{} (OSStatus {})".format(message or "Keychain access was denied", status))
    raise KeychainError(status, message)


def _query(service: str, account: str, extra: Optional[Dict[str, int]] = None) -> int:
    """Build the ``CFDictionary`` identifying one generic-password item."""
    sec = _security()
    service_ref = _cf.string(service)
    account_ref = _cf.string(account)
    try:
        items = {
            _cf.constant(sec, "kSecClass"): _cf.constant(sec, "kSecClassGenericPassword"),
            _cf.constant(sec, "kSecAttrService"): service_ref,
            _cf.constant(sec, "kSecAttrAccount"): account_ref,
        }
        for key, value in (extra or {}).items():
            items[_cf.constant(sec, key)] = value
        return _cf.dictionary(items)
    finally:
        _cf.release(service_ref)
        _cf.release(account_ref)


def get(service: str, account: str) -> Optional[str]:
    """Return the password stored for ``service``/``account``, or ``None`` if there is none."""
    sec = _security()
    cf = _cf.lib()
    extra = {
        "kSecReturnData": _cf.constant(cf, "kCFBooleanTrue"),
        "kSecMatchLimit": _cf.constant(sec, "kSecMatchLimitOne"),
    }
    result = _cf.CFTypeRef()
    with _cf.owned(_query(service, account, extra)) as query:
        status = sec.SecItemCopyMatching(query, ctypes.byref(result))

    if status == errSecItemNotFound:
        return None
    _check(status)

    with _cf.owned(result.value) as ref:
        return _cf.to_bytes(ref).decode("utf-8")


def set(service: str, account: str, password: str) -> None:
    """Store ``password`` for ``service``/``account``, replacing any existing one."""
    sec = _security()
    secret = _cf.data(password.encode("utf-8"))
    with _cf.owned(secret):
        with _cf.owned(_query(service, account, {"kSecValueData": secret})) as item:
            status = sec.SecItemAdd(item, None)

        if status == errSecDuplicateItem:
            update = _cf.dictionary({_cf.constant(sec, "kSecValueData"): secret})
            with _cf.owned(_query(service, account)) as query, _cf.owned(update):
                status = sec.SecItemUpdate(query, update)

    _check(status)


def delete(service: str, account: str) -> bool:
    """Delete the item for ``service``/``account``. Return ``False`` if it didn't exist."""
    with _cf.owned(_query(service, account)) as query:
        status = _security().SecItemDelete(query)

    if status == errSecItemNotFound:
        return False
    _check(status)
    return True
