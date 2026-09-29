# -*- coding: utf-8 -*-

"""
Ask the user to confirm it's them, with Touch ID, their login password or their Apple Watch.

::

    if macos.auth.confirm("unlock the production credentials"):
        token = macos.keychain.get("deploy", "prod")

macOS shows its own prompt, and checks the fingerprint or the password
itself: the script only learns whether it succeeded. It's a check before a
sensitive action, not encryption: a Keychain item isn't locked behind it.
"""

import ctypes
import functools
import threading
from typing import Any, Callable, List, TypeVar

from . import _objc
from ._system import framework
from .errors import NotSupportedError, PermissionDeniedError

__all__ = ["confirm", "is_available", "required"]

_BIOMETRICS, _OWNER = 1, 2  # LAPolicyDeviceOwnerAuthenticationWithBiometrics, LAPolicyDeviceOwnerAuthentication


def _policy(only_touch_id: bool) -> int:
    return _BIOMETRICS if only_touch_id else _OWNER


def _context() -> int:
    """An ``LAContext`` owned by the caller, who releases it (``_objc.new`` would be autoreleased)."""
    framework("LocalAuthentication")
    return _objc.send(_objc.send(_objc.cls("LAContext"), "alloc"), "init")


def is_available(*, only_touch_id: bool = False) -> bool:
    """
    Whether :func:`confirm` can ask, without asking.

    With ``only_touch_id=True``, whether Touch ID is set up (and not locked
    out after failed tries). Otherwise it's always true, as the login password
    works on any Mac.
    """
    context = _context()
    with _objc.autorelease_pool():
        try:
            return bool(
                _objc.send(
                    context,
                    "canEvaluatePolicy:error:",
                    _policy(only_touch_id),
                    None,
                    argtypes=(_objc.NSInteger, ctypes.c_void_p),
                    restype=_objc.BOOL,
                )
            )
        finally:
            _objc.send(context, "release", restype=None)


def confirm(reason: str, *, only_touch_id: bool = False, timeout: float = 120.0) -> bool:
    """
    Show macOS's prompt to confirm it's the Mac's owner, and return whether they did.

    ``reason`` completes the prompt's sentence: *"Python wants to <reason>"*.
    The user can place their finger on Touch ID, or type their login password
    (or approve on their Apple Watch); ``only_touch_id=True`` accepts only the
    fingerprint. Cancelling, failing, or ``timeout`` seconds without an answer
    return ``False``. Raises :class:`~macos.errors.NotSupportedError` when
    ``only_touch_id=True`` and Touch ID isn't available.
    """
    if not reason.strip():
        raise ValueError("reason must not be empty: macOS shows it in the prompt")
    framework("LocalAuthentication")  # before the reply block: NotSupportedError outside macOS
    if only_touch_id and not is_available(only_touch_id=True):
        raise NotSupportedError("Touch ID isn't set up on this Mac (or is locked after failed tries)")
    answers: List[bool] = []
    done = threading.Event()

    def replied(success: bool, error: int) -> None:
        answers.append(bool(success))
        done.set()

    handler = _objc.block(replied, b"v@?B@", ctypes.c_bool, ctypes.c_void_p)
    context = _context()
    try:
        with _objc.autorelease_pool():
            _objc.send(
                context,
                "evaluatePolicy:localizedReason:reply:",
                _policy(only_touch_id),
                _objc.nsstring(reason),
                handler,
                argtypes=(_objc.NSInteger, _objc.id, ctypes.c_void_p),
                restype=None,
            )
        if not _objc.run_until(done.is_set, timeout):
            _objc.send(context, "invalidate", restype=None)  # takes the prompt away
            return False
        return bool(answers and answers[0])
    finally:
        _objc.send(context, "release", restype=None)


_Function = TypeVar("_Function", bound=Callable[..., Any])


def required(reason: str, *, only_touch_id: bool = False) -> Callable[[_Function], _Function]:
    """
    Ask to confirm with :func:`confirm` each time the decorated function is called, before it runs.

    ::

        @macos.auth.required("deploy to production")
        def deploy():
            ...

    When the user doesn't confirm, the call raises
    :class:`~macos.errors.PermissionDeniedError` and the function doesn't run.
    """
    if not reason.strip():
        raise ValueError("reason must not be empty: macOS shows it in the prompt")

    def decorate(function: _Function) -> _Function:
        @functools.wraps(function)
        def guarded(*args: Any, **kwargs: Any) -> Any:
            if not confirm(reason, only_touch_id=only_touch_id):
                raise PermissionDeniedError("{} wasn't confirmed".format(reason))
            return function(*args, **kwargs)

        return guarded  # type: ignore[return-value]

    return decorate
