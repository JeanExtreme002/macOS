# -*- coding: utf-8 -*-

"""
Start Time Machine backups and follow them.

::

    macos.time_machine.destinations()     # ['Backup Disk']
    macos.time_machine.backup_now()
    macos.time_machine.is_backing_up()    # True
    macos.time_machine.progress()         # 0.42
    macos.time_machine.last_backup()      # datetime.datetime(2026, 9, 28, 23, 10, 4)

Goes through the ``tmutil`` command that ships with macOS. Reading the last
backup needs its disk to be connected, and may need Full Disk Access for the
app running Python.
"""

import re
from datetime import datetime
from typing import List, Optional

from ._system import require_macos, run as _run
from .errors import CommandError, MacOSError

__all__ = ["destinations", "backup_now", "stop_backup", "is_backing_up", "progress", "last_backup"]

_BACKUP_NAME = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{6})")


def destinations() -> List[str]:
    """The names of the disks Time Machine backs up to; ``[]`` when none is set up."""
    require_macos()
    try:
        output = _run(["tmutil", "destinationinfo"])
    except CommandError as error:
        if "No destinations configured" in error.stderr:
            return []
        raise
    return [match.strip() for match in re.findall(r"^Name\s*:\s*(.+)$", output, re.M)]


def backup_now(*, wait: bool = False) -> None:
    """
    Start a backup, like *Back Up Now* in the Time Machine menu.

    Returns at once, unless ``wait=True``: then it returns when the backup is done.
    """
    if not destinations():
        raise MacOSError("Time Machine has no backup disk: set one up in System Settings › General › Time Machine")
    _run(["tmutil", "startbackup", *(["--block"] if wait else [])])


def stop_backup() -> None:
    """Stop the backup in progress, like *Skip This Backup*."""
    require_macos()
    _run(["tmutil", "stopbackup"])


def _status() -> str:
    require_macos()
    return _run(["tmutil", "status"])


def is_backing_up() -> bool:
    """Whether a backup is in progress."""
    return bool(re.search(r"\bRunning\s*=\s*1\s*;", _status()))


def progress() -> Optional[float]:
    """How far the backup in progress is, from 0.0 to 1.0; ``None`` when none is, or while it's getting ready."""
    status = _status()
    if not re.search(r"\bRunning\s*=\s*1\s*;", status):
        return None
    found = re.search(r'\bPercent\s*=\s*"?(-?[0-9.]+)"?\s*;', status)
    if not found or float(found.group(1)) < 0:
        return None
    return min(1.0, float(found.group(1)))


def last_backup() -> Optional[datetime]:
    """When the latest backup was made, or ``None`` (no backup yet, or its disk isn't connected)."""
    require_macos()
    try:
        output = _run(["tmutil", "latestbackup"])
    except CommandError:
        return None
    # tmutil prints the backup's path, named after its date; its errors come with a success status.
    found = _BACKUP_NAME.findall(output)
    return datetime.strptime(found[-1], "%Y-%m-%d-%H%M%S") if found else None
