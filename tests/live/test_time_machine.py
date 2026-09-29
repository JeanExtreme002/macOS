"""Tests of :mod:`macos.time_machine` against the real system. Skipped outside macOS."""

import macos


def test_time_machine_state():
    assert isinstance(macos.time_machine.destinations(), list)
    assert isinstance(macos.time_machine.is_backing_up(), bool)
    progress = macos.time_machine.progress()
    assert progress is None or 0.0 <= progress <= 1.0
    macos.time_machine.last_backup()  # a date, or None without a backup disk
