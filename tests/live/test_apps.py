"""Tests of :mod:`macos.apps` against the real system. Skipped outside macOS."""

import os
import uuid

import pytest

import macos


def test_running_apps():
    everything = macos.apps.running(include_background=True)
    regular = macos.apps.running()

    assert everything, "NSWorkspace returned no applications"
    assert {app.pid for app in regular} <= {app.pid for app in everything}
    assert all(isinstance(app.pid, int) and app.pid > 0 for app in everything)


def test_get_finds_apps_by_bundle_id():
    app = macos.apps.running(include_background=True)[0]
    found = macos.apps.get(app.bundle_id) if app.bundle_id else macos.apps.get(app.name)

    assert found is not None
    assert found.pid == app.pid
    assert found.is_running


def test_locate_ignores_a_folder_with_the_app_name(tmp_path, monkeypatch):
    (tmp_path / "Finder").mkdir()
    monkeypatch.chdir(tmp_path)

    assert macos.apps._locate("Finder") == os.path.realpath("/System/Library/CoreServices/Finder.app")


def test_find_launched_requires_the_same_bundle_path():
    finder = os.path.realpath("/System/Library/CoreServices/Finder.app")

    assert macos.apps._find_launched(finder, "com.apple.finder").bundle_id == "com.apple.finder"
    assert macos.apps._find_launched("/Applications/Another Finder.app", "com.apple.finder") is None


def test_get_unknown_app_returns_none():
    assert macos.apps.get("com.example.definitely-not-installed") is None


def test_open_unknown_app_raises():
    with pytest.raises(macos.AppNotFoundError):
        macos.apps.open("Definitely Not An Installed App {}".format(uuid.uuid4()))


def test_get_matches_the_app_file_name_and_path():
    app = next(app for app in macos.apps.running(include_background=True) if app.path and app.path.endswith(".app"))
    file_name = os.path.basename(app.path)

    assert macos.apps.get(file_name).pid == app.pid
    assert macos.apps.get(app.path + "/").pid == app.pid


def test_locate_resolves_bundle_ids_names_and_symlinks():
    finder = "/System/Library/CoreServices/Finder.app"

    assert macos.apps._locate("com.apple.finder") == os.path.realpath(finder)
    assert macos.apps._locate(finder) == os.path.realpath(finder)
    with pytest.raises(macos.AppNotFoundError):
        macos.apps._locate("com.example.definitely-not-installed")


def test_running_apps_from_a_worker_thread():
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(1) as pool:
        in_thread = pool.submit(macos.apps.running, include_background=True).result()

    assert {app.pid for app in in_thread} & {app.pid for app in macos.apps.running(include_background=True)}


def test_default_apps():
    text_editor = macos.apps.default_for("txt")
    if text_editor is None:
        pytest.skip("no app opens text files here")
    assert text_editor.endswith(".app")
    assert macos.apps.default_for(".txt") == text_editor
    assert macos.apps.default_for("public.plain-text") == text_editor
    assert macos.apps.default_for("definitely-not-an-extension") is None
    assert macos.apps.default_for("backup.txt") == text_editor  # a dotted extension, not a type
    browser = macos.apps.default_browser()
    assert browser is None or browser.endswith(".app")
