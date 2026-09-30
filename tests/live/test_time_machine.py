"""Tests of :mod:`macos.time_machine` against the real system. Skipped outside macOS."""

import macos


def test_time_machine_state():
    assert isinstance(macos.time_machine.destinations(), list)
    assert isinstance(macos.time_machine.is_backing_up(), bool)
    progress = macos.time_machine.progress()
    assert progress is None or 0.0 <= progress <= 1.0
    macos.time_machine.last_backup()  # a date, or None without a backup disk


def test_time_machine_exclude_and_include():
    import shutil
    import tempfile
    from pathlib import Path

    # Not in the temporary folder: macOS already leaves it out of backups.
    folder = Path(tempfile.mkdtemp(prefix=".pymacos-test-", dir=Path.home()))
    try:
        (folder / "file.txt").write_text("hi")
        assert macos.time_machine.is_excluded(folder) is False
        macos.time_machine.exclude(folder)
        assert macos.time_machine.is_excluded(folder) is True
        assert macos.time_machine.is_excluded(folder / "file.txt") is True  # what's inside goes too
        macos.time_machine.include(folder)
        assert macos.time_machine.is_excluded(folder) is False
    finally:
        shutil.rmtree(folder)
