# -*- coding: utf-8 -*-

"""
Show notifications in Notification Center.

::

    macos.notify("Build finished")
    macos.notify("3 tests failed", title="CI", subtitle="main", sound="Basso")

Notifications are posted through AppleScript's ``display notification``. The
native ``UNUserNotificationCenter`` API only works from a signed app bundle,
which a Python script isn't, so macOS attributes these notifications to
*Script Editor*. When notifications are turned off for Script Editor, macOS
drops them without any error, so :func:`notify` checks that setting and raises
:class:`~macos.errors.PermissionDeniedError` instead.
"""

import plistlib
import subprocess
from typing import List, Optional

from ._system import require_macos, run as _run
from .errors import PermissionDeniedError

__all__ = ["notify", "is_allowed"]

_SCRIPT_EDITOR = "com.apple.ScriptEditor2"
# The "Allow notifications" switch in System Settings › Notifications. The
# settings format is undocumented; this bit is known from reverse engineering
# (e.g. the ncprefs.py project) and matches what toggling the switch changes.
_ALLOW_NOTIFICATIONS = 1 << 25


def is_allowed() -> Optional[bool]:
    """
    Whether macOS lets Script Editor, and so :func:`macos.notify`, show notifications.

    ``None`` means it can't tell: Script Editor has never posted one yet, or
    the settings couldn't be read. Focus modes such as Do Not Disturb can still
    hide notifications that are allowed.
    """
    require_macos()
    try:
        raw = subprocess.run(["defaults", "export", "com.apple.ncprefs", "-"], capture_output=True, check=True).stdout
        settings = plistlib.loads(raw)
    except Exception:  # best effort: an unreadable format must never break notify()
        return None

    for app in settings.get("apps", []):
        if isinstance(app, dict) and app.get("bundle-id") == _SCRIPT_EDITOR:
            return bool(int(app.get("flags", 0)) & _ALLOW_NOTIFICATIONS)
    return None


def _refuse() -> None:
    raise PermissionDeniedError(
        "macOS would silently drop this notification: notifications are turned off for Script Editor, "
        "which posts them. Turn them on in System Settings › Notifications › Script Editor."
    )


def notify(
    message: str,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    sound: Optional[str] = None,
    check_permission: bool = True,
) -> None:
    """
    Post a notification.

    ``sound`` is the name of a system alert sound, such as ``"Glass"``,
    ``"Ping"`` or ``"Basso"`` (see :func:`macos.sound.names`).

    Raises :class:`~macos.errors.PermissionDeniedError` when notifications are
    turned off for Script Editor, since macOS would silently drop them. Pass
    ``check_permission=False`` to skip that check.
    """
    # The text travels as script arguments (``argv``), never spliced into the
    # AppleScript source, so quotes or backslashes in it can't break or inject
    # into the script.
    values: List[str] = [message]
    statement = "display notification (item 1 of argv)"
    for clause, value in (("with title", title), ("subtitle", subtitle), ("sound name", sound)):
        if value is not None:
            values.append(value)
            statement += " {} (item {} of argv)".format(clause, len(values))

    # "--" ends osascript's options, so text starting with "-" (a message like
    # "-5 degrees", or "-e") is taken as an argument instead of a flag.
    allowed = is_allowed() if check_permission else True
    if allowed is False:
        _refuse()

    _run(["osascript", "-e", "on run argv", "-e", statement, "-e", "end run", "--", *values])

    # The first notification ever registers Script Editor with notifications
    # off, and macOS drops it without a prompt: check again now that it's known.
    if allowed is None and is_allowed() is False:
        _refuse()
