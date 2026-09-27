# -*- coding: utf-8 -*-

"""
pymacos (imported as ``macos``) — a Pythonic interface to macOS.

Notifications, clipboard, appearance, apps, Keychain, speech and screenshots
in one import, with no dependencies::

    import macos

    macos.notify("Build finished", title="CI")
    macos.clipboard.copy("hello")
    macos.appearance.is_dark()
    macos.apps.running()
    macos.keychain.get("my-app", "alice")
    macos.say("Done!")
    macos.screenshot("screen.png")

The package imports on any platform (so it can sit in cross-platform code and
docs builds), but its functions raise :class:`NotSupportedError` outside macOS.
"""

__version__ = "0.1.0"

from . import appearance, apps, clipboard, keychain, screen, speech
from .errors import (
    AppNotFoundError,
    CommandError,
    KeychainError,
    MacOSError,
    NotSupportedError,
    PermissionDeniedError,
)
from .notifications import notify
from .screen import screenshot
from .speech import say

__all__ = [
    "appearance",
    "apps",
    "clipboard",
    "keychain",
    "screen",
    "speech",
    "notify",
    "say",
    "screenshot",
    "AppNotFoundError",
    "CommandError",
    "KeychainError",
    "MacOSError",
    "NotSupportedError",
    "PermissionDeniedError",
]
