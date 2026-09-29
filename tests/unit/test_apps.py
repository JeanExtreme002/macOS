"""Unit tests for :mod:`macos.apps`. They run on any platform."""

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
