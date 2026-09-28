# -*- coding: utf-8 -*-

"""
Internal helpers shared by every module: the platform guard, running system
commands and loading system frameworks.
"""

import ctypes
import subprocess
import sys
from functools import lru_cache
from typing import Optional, Sequence

from .errors import CommandError, NotSupportedError


def require_macos() -> None:
    """Raise :class:`NotSupportedError` unless running on macOS."""
    if sys.platform != "darwin":
        raise NotSupportedError("pymacos only works on macOS (running on {!r})".format(sys.platform))


def run(args: Sequence[str], *, input: Optional[str] = None) -> str:
    """
    Run a system command and return its standard output.

    Arguments are passed as a list (never through a shell), so user-provided
    text can't be interpreted as shell syntax. A non-zero exit status raises
    :class:`CommandError` carrying the command's stderr.
    """
    require_macos()

    try:
        result = subprocess.run(list(args), input=input, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        raise NotSupportedError("the {!r} command was not found on this system".format(args[0])) from None

    if result.returncode != 0:
        raise CommandError(args, result.returncode, result.stderr)
    return result.stdout


@lru_cache(maxsize=None)
def framework(name: str) -> ctypes.CDLL:
    """Load a system framework (e.g. ``"AppKit"``) once and cache the handle."""
    require_macos()
    return ctypes.CDLL("/System/Library/Frameworks/{0}.framework/{0}".format(name))


@lru_cache(maxsize=None)
def private_framework(name: str) -> ctypes.CDLL:
    """
    Load one of Apple's private frameworks, raising :class:`NotSupportedError` when this macOS lacks it.

    Private frameworks (brightness, keyboard backlight...) have no public
    alternative, but Apple may change them in any release: callers check
    what they need exists before using it.
    """
    require_macos()
    try:
        return ctypes.CDLL("/System/Library/PrivateFrameworks/{0}.framework/{0}".format(name))
    except OSError:
        raise NotSupportedError("this version of macOS doesn't have {}".format(name)) from None
