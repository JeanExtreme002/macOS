"""Unit tests for :mod:`macos.time_machine`. They run on any platform."""

from datetime import datetime

import pytest

import macos


def test_time_machine_status(fake_run):
    fake_run.stdout = 'Backup session status:\n{\n    ClientID = "com.apple.backupd";\n    Percent = "0.42";\n'
    fake_run.stdout += "    Running = 1;\n}\n"
    assert macos.time_machine.is_backing_up() is True
    assert macos.time_machine.progress() == 0.42

    fake_run.stdout = 'Backup session status:\n{\n    Percent = "-1";\n    Running = 0;\n}\n'
    assert macos.time_machine.is_backing_up() is False and macos.time_machine.progress() is None


def test_time_machine_destinations_and_last_backup(fake_run):
    fake_run.stdout = "====================================================\nName          : Backup Disk\nKind          : Local\n"
    assert macos.time_machine.destinations() == ["Backup Disk"]
    fake_run.stdout = "/Volumes/.timemachine/ABC/2026-09-28-231004.backup/2026-09-28-231004.backup\n"
    assert macos.time_machine.last_backup() == datetime(2026, 9, 28, 23, 10, 4)
    fake_run.stdout = "Failed to mount backup destination, error: ...\n"  # printed with a success status
    assert macos.time_machine.last_backup() is None

    fake_run.stdout = "tmutil: No destinations configured.\n"
    assert macos.time_machine.destinations() == []
    with pytest.raises(macos.MacOSError, match="no backup disk"):
        macos.time_machine.backup_now()
