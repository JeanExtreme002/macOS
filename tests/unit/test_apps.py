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
