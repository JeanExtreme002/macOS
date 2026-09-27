# -*- coding: utf-8 -*-

"""
Exceptions raised by the ``macos`` package.

Every exception derives from :class:`MacOSError`, so ``except macos.MacOSError``
catches anything the package raises on purpose. Where a builtin exception has
the same meaning, the package's exception subclasses it too, so existing
``except PermissionError`` / ``except LookupError`` handlers keep working.
"""

from typing import Optional, Sequence


class MacOSError(Exception):
    """Base class for every error raised by the ``macos`` package."""


class NotSupportedError(MacOSError):
    """The feature is not available on this system (e.g. not running on macOS)."""


class PermissionDeniedError(MacOSError, PermissionError):
    """macOS refused the operation because a privacy permission is missing."""


class AppNotFoundError(MacOSError, LookupError):
    """No application matched the given name, bundle identifier or path."""


class CommandError(MacOSError):
    """A system command the package relies on exited with an error."""

    def __init__(self, args: Sequence[str], returncode: int, stderr: str = "") -> None:
        self.cmd = list(args)
        self.returncode = returncode
        self.stderr = stderr.strip()

        message = "{!r} exited with status {}".format(self.cmd[0], returncode)
        if self.stderr:
            message += ": " + self.stderr
        super().__init__(message)


class KeychainError(MacOSError):
    """The Security framework returned an error status (``OSStatus``)."""

    def __init__(self, status: int, message: Optional[str] = None) -> None:
        self.status = status
        super().__init__("{} (OSStatus {})".format(message or "Keychain error", status))
