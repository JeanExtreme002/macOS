# -*- coding: utf-8 -*-

"""
Play sounds: system alert sounds, audio files, and the alert beep.

::

    macos.sound.play("Glass")              # a system alert sound
    macos.sound.play("done.mp3", volume=0.5)
    macos.sound.beep()
    macos.sound.names()                    # ['Basso', 'Blow', 'Bottle', ...]

Uses ``NSSound``, so any format macOS plays works (MP3, AAC/M4A, WAV, AIFF...).
"""

import ctypes
import os
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import List, Set, Union

from . import _objc
from ._objc import BOOL
from ._system import framework, require_macos

__all__ = ["play", "beep", "names"]

_SOUND_FOLDERS = (Path("/System/Library/Sounds"), Path("/Library/Sounds"), Path("~/Library/Sounds").expanduser())


@lru_cache(maxsize=None)
def _appkit() -> ctypes.CDLL:
    appkit = framework("AppKit")
    appkit.NSBeep.argtypes = ()
    appkit.NSBeep.restype = None
    return appkit


def names() -> List[str]:
    """Return the names of the alert sounds that :func:`play` accepts, as in System Settings › Sound."""
    require_macos()
    found: Set[str] = set()
    for folder in _SOUND_FOLDERS:
        if folder.is_dir():
            found.update(path.stem for path in folder.iterdir() if path.suffix.lower() in (".aiff", ".aif", ".caf", ".wav"))
    return sorted(found)


def _load(sound: Union[str, "os.PathLike[str]"]) -> int:
    """A retained ``NSSound`` (+1) for a sound name or an audio file."""
    _appkit()
    text = os.fspath(sound)
    looks_like_path = os.sep in text or Path(text).suffix != ""
    if looks_like_path:
        path = Path(text).expanduser().absolute()
        if not path.exists():
            raise FileNotFoundError(str(path))
        player = _objc.send(_objc.cls("NSSound"), "alloc")
        player = _objc.send(
            player, "initWithContentsOfFile:byReference:", _objc.nsstring(str(path)), False, argtypes=(_objc.id, BOOL)
        )
        if not player:
            raise ValueError("{} is not an audio file macOS can play".format(path))
        return player
    player = _objc.send(_objc.cls("NSSound"), "soundNamed:", _objc.nsstring(text), argtypes=(_objc.id,))
    if not player:
        raise ValueError("no alert sound is named {!r}; see macos.sound.names()".format(text))
    return _objc.send(player, "retain")


def play(sound: Union[str, "os.PathLike[str]"], *, volume: float = 1.0, wait: bool = True) -> None:
    """
    Play an alert sound by name (``"Glass"``, ``"Ping"``...) or an audio file.

    ``volume`` goes from 0.0 to 1.0, relative to the system volume. By default
    this returns when the sound ends; ``wait=False`` returns right away.
    """
    if not 0.0 <= volume <= 1.0:
        raise ValueError("volume must be from 0.0 to 1.0, not {}".format(volume))
    player = _load(sound)
    _objc.send(player, "setVolume:", volume, argtypes=(ctypes.c_float,), restype=None)
    duration = float(_objc.send(player, "duration", restype=ctypes.c_double))
    if not _objc.send(player, "play", restype=BOOL):
        _objc.send(player, "release", restype=None)
        raise ValueError("{!r} could not be played".format(os.fspath(sound)))

    # NSSound only reports progress through the run loop, which a script
    # doesn't spin, so the sound's own length decides when it's done. It must
    # stay alive until then: releasing it stops the playback.
    def finish() -> None:
        _objc.send(player, "release", restype=None)

    if wait:
        time.sleep(duration)
        finish()
    else:
        timer = threading.Timer(duration + 0.5, finish)
        timer.daemon = True
        timer.start()


def beep() -> None:
    """Play the alert sound chosen in System Settings › Sound, like an app's error beep."""
    _appkit().NSBeep()
