"""Unit tests for :mod:`macos.apps`. They run on any platform."""

import sys
from pathlib import Path

import pytest

import macos


def test_open_passes_urls_through_and_checks_paths(fake_run, tmp_path):
    macos.open("https://python.org", background=True)
    assert fake_run.args == ["open", "-g", "--", "https://python.org"]

    macos.open(tmp_path)
    assert fake_run.args == ["open", "--", str(tmp_path)]

    with pytest.raises(FileNotFoundError):
        macos.open(tmp_path / "missing.pdf")


def test_open_with_resolves_the_app(fake_run, monkeypatch, tmp_path):
    monkeypatch.setattr(macos.apps, "_locate", lambda app: "/Applications/{}.app".format(app))
    target = tmp_path / "photo.png"
    target.touch()

    macos.apps.open_with(target, "Preview")
    assert fake_run.args == ["open", "-a", "/Applications/Preview.app", "--", str(target)]
    assert macos.open_with is macos.apps.open_with  # the short name


def test_open_with_reports_failures_as_app_not_found(fake_run, monkeypatch, tmp_path):
    monkeypatch.setattr(macos.apps, "_locate", lambda app: "/Applications/Nope.app")
    fake_run.returncode, fake_run.stderr = 1, "LSOpenURLsWithRole() failed"

    with pytest.raises(macos.AppNotFoundError, match="could not open"):
        macos.open_with(tmp_path, "Nope")


def test_login_items(fake_run, monkeypatch):
    from macos import apps

    fake_run.stdout = "Rectangle\x1f/Applications/Rectangle.app\x1eBackup\x1fmissing value\x1e\n"
    assert apps.login_items() == [
        apps.LoginItem("Rectangle", "/Applications/Rectangle.app"),
        apps.LoginItem("Backup", None),
    ]
    monkeypatch.setattr(apps, "_locate", lambda name: "/Applications/Rectangle.app")
    monkeypatch.setattr(apps.os.path, "realpath", lambda path: path)
    assert apps.add_login_item("Rectangle").name == "Rectangle"  # already there: nothing added
    assert "make login item" not in fake_run.args[2]
    assert apps.remove_login_item("Rectangle") is True
    assert fake_run.args[3:] == ["--", "/Applications/Rectangle.app"]  # removed by path


def test_install_from_dmg_checks_the_destination(tmp_path):
    with pytest.raises(NotADirectoryError):
        macos.apps.install_from_dmg(tmp_path / "Tool.dmg", destination=tmp_path / "missing")


def test_install_from_dmg_keeps_the_old_app_when_the_copy_fails(monkeypatch, tmp_path):
    from macos import apps, system

    volume = tmp_path / "Volume"
    (volume / "Tool.app" / "Contents").mkdir(parents=True)
    installed = tmp_path / "Applications" / "Tool.app"
    (installed / "Contents").mkdir(parents=True)
    (installed / "Contents" / "old").write_text("old version")
    monkeypatch.setattr(system, "mount_image", lambda image: volume)
    monkeypatch.setattr(system, "unmount_image", lambda mounted, force=False: None)

    def failing_copy(args):
        Path(args[-1]).mkdir()  # a partial copy
        raise macos.CommandError(args, 1, "No space left on device")

    monkeypatch.setattr(apps, "_run", failing_copy)
    with pytest.raises(macos.CommandError):
        apps.install_from_dmg(tmp_path / "Tool.dmg", destination=tmp_path / "Applications", replace=True)
    assert (installed / "Contents" / "old").read_text() == "old version"  # still installed
    assert sorted(path.name for path in (tmp_path / "Applications").iterdir()) == ["Tool.app"]  # no leftovers


@pytest.mark.skipif(sys.platform != "darwin", reason="extended attributes as macOS keeps them")
def test_unquarantine(tmp_path):
    import subprocess

    app = tmp_path / "Tool.app"
    (app / "Contents").mkdir(parents=True)
    binary = app / "Contents" / "tool"
    binary.write_text("")
    for path in (app, binary):
        subprocess.run(["/usr/bin/xattr", "-w", "com.apple.quarantine", "0081;00000000;Safari;", str(path)], check=True)

    assert macos.apps.is_quarantined(app) and macos.apps.is_quarantined(binary)
    assert macos.apps.unquarantine(app) == 2
    assert not macos.apps.is_quarantined(app) and not macos.apps.is_quarantined(binary)
    assert macos.apps.unquarantine(app) == 0
    with pytest.raises(FileNotFoundError):
        macos.apps.is_quarantined(tmp_path / "missing.app")


@pytest.mark.skipif(sys.platform != "darwin", reason="extended attributes as macOS keeps them")
def test_is_quarantined_reports_errors_other_than_a_missing_mark(tmp_path, monkeypatch):
    import ctypes
    import errno

    file = tmp_path / "file"
    file.write_text("")

    class Failing:
        def getxattr(self, *args):
            ctypes.set_errno(errno.EACCES)
            return -1

    monkeypatch.setattr(macos.apps, "_libc", lambda: Failing())
    with pytest.raises(PermissionError):
        macos.apps.is_quarantined(file)


@pytest.mark.skipif(sys.platform != "darwin", reason="extended attributes as macOS keeps them")
def test_unquarantine_keeps_the_error_and_stops_at_unreadable_folders(tmp_path, monkeypatch):
    import ctypes
    import errno

    app = tmp_path / "Tool.app"
    (app / "Contents").mkdir(parents=True)

    class Failing:
        def removexattr(self, *args):
            ctypes.set_errno(errno.EIO)
            return -1

    monkeypatch.setattr(macos.apps, "_libc", lambda: Failing())
    with pytest.raises(OSError) as raised:
        macos.apps.unquarantine(app)
    assert raised.value.errno == errno.EIO and not isinstance(raised.value, PermissionError)

    monkeypatch.undo()
    locked = app / "Contents" / "Locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        with pytest.raises(PermissionError):
            macos.apps.unquarantine(app)
    finally:
        locked.chmod(0o755)
