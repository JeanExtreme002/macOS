# -*- coding: utf-8 -*-

"""
Internal helpers for :mod:`macos.camera` and the microphone in :mod:`macos.audio`:
the Camera and Microphone permissions, through AVFoundation.
"""

import ctypes
import threading
from typing import List

from . import _objc
from ._system import framework
from .errors import PermissionDeniedError

VIDEO, AUDIO = "vide", "soun"  # AVMediaTypeVideo, AVMediaTypeAudio

_NOT_DETERMINED, _RESTRICTED, _DENIED, _AUTHORIZED = 0, 1, 2, 3
_NAMES = {VIDEO: "Camera", AUDIO: "Microphone"}


def _status(media: str) -> int:
    framework("AVFoundation")
    with _objc.autorelease_pool():
        return int(
            _objc.send(
                _objc.cls("AVCaptureDevice"),
                "authorizationStatusForMediaType:",
                _objc.nsstring(media),
                argtypes=(_objc.id,),
                restype=_objc.NSInteger,
            )
        )


def has_permission(media: str) -> bool:
    return _status(media) == _AUTHORIZED


def request_permission(media: str, timeout: float = 120.0) -> bool:
    """Show the system prompt if the user hasn't answered yet, and wait for the answer."""
    status = _status(media)
    if status != _NOT_DETERMINED:
        return status == _AUTHORIZED
    answers: List[bool] = []
    done = threading.Event()

    def answered(granted: bool) -> None:
        answers.append(bool(granted))
        done.set()

    handler = _objc.block(answered, b"v@?B", ctypes.c_bool)
    with _objc.autorelease_pool():
        _objc.send(
            _objc.cls("AVCaptureDevice"),
            "requestAccessForMediaType:completionHandler:",
            _objc.nsstring(media),
            handler,
            argtypes=(_objc.id, ctypes.c_void_p),
            restype=None,
        )
    _objc.run_until(done.is_set, timeout)
    return bool(answers and answers[0])


def require_permission(media: str) -> None:
    """Ask for the permission the first time; raise when it's denied."""
    if request_permission(media):
        return
    name = _NAMES[media]
    raise PermissionDeniedError(
        "{} permission is missing: allow the app running Python (your terminal or IDE) in System Settings › "
        "Privacy & Security › {}, then restart it".format(name, name)
    )
