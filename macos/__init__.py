# -*- coding: utf-8 -*-

"""
pymacos (imported as ``macos``) — a Pythonic interface to macOS.

Notifications, clipboard, appearance, apps, Keychain, speech, screenshots,
power, Shortcuts, Finder, volume, Spotlight, dialogs, system info, OCR,
document scanning, images, PDFs and language detection in one import, with no
dependencies::

    import macos

    macos.notify("Build finished", title="CI")
    macos.clipboard.copy("hello")
    macos.appearance.is_dark()
    macos.apps.running()
    macos.keychain.get("my-app", "alice")
    macos.say("Done!")
    macos.screenshot("screen.png")
    macos.power.battery()
    macos.shortcuts.run("Resize Image", input=Path("photo.jpg"))
    macos.finder.trash("old.log")
    macos.volume.set(30)
    macos.spotlight.search("kind:pdf invoice")
    macos.dialog.confirm("Continue?")
    macos.system.idle_time()
    macos.vision.text("screenshot.png")
    macos.open_with("report.pdf", "Preview")
    macos.image.convert("IMG_0042.heic", "IMG_0042.jpg")
    macos.pdf.text("report.pdf")
    macos.language.detect("Olá, tudo bem?")
    macos.vision.remove_background("photo.jpg")
    macos.vision.scan_document("receipt.jpg")
    macos.audio.set_output("AirPods")

The package imports on any platform (so it can sit in cross-platform code and
docs builds), but its functions raise :class:`NotSupportedError` outside macOS.
"""

__version__ = "1.6.0"

from . import (
    appearance,
    apps,
    audio,
    clipboard,
    dialog,
    finder,
    image,
    keychain,
    language,
    network,
    notifications,
    pdf,
    power,
    screen,
    shortcuts,
    sound,
    speech,
    spotlight,
    system,
    vision,
    volume,
)
from .errors import (
    AppNotFoundError,
    CommandError,
    KeychainError,
    MacOSError,
    NotSupportedError,
    PermissionDeniedError,
    ShortcutNotFoundError,
)
from .launch import open, open_with
from .notifications import notify
from .screen import screenshot
from .speech import say

__all__ = [
    "appearance",
    "apps",
    "audio",
    "clipboard",
    "dialog",
    "finder",
    "image",
    "keychain",
    "language",
    "network",
    "notifications",
    "pdf",
    "power",
    "screen",
    "shortcuts",
    "sound",
    "speech",
    "spotlight",
    "system",
    "vision",
    "volume",
    "notify",
    "open_with",
    "say",
    "screenshot",
    "AppNotFoundError",
    "CommandError",
    "KeychainError",
    "MacOSError",
    "NotSupportedError",
    "PermissionDeniedError",
    "ShortcutNotFoundError",
]
