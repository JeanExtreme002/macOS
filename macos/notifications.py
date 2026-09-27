# -*- coding: utf-8 -*-

"""
Show notifications in Notification Center.

::

    macos.notify("Build finished")
    macos.notify("3 tests failed", title="CI", subtitle="main", sound="Basso")

Notifications are posted through AppleScript's ``display notification``. The
native ``UNUserNotificationCenter`` API only works from a signed app bundle,
which a Python script isn't, so macOS attributes these notifications to
*Script Editor*: if none show up, allow notifications for Script Editor in
System Settings › Notifications.
"""

from typing import List, Optional

from ._system import run

__all__ = ["notify"]


def notify(message: str, *, title: Optional[str] = None, subtitle: Optional[str] = None, sound: Optional[str] = None) -> None:
    """
    Post a notification.

    ``sound`` is the name of a system alert sound, such as ``"Glass"``,
    ``"Ping"`` or ``"Basso"`` (see ``/System/Library/Sounds``).
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
    run(["osascript", "-e", "on run argv", "-e", statement, "-e", "end run", "--", *values])
