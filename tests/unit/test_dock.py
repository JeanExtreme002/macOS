"""Unit tests for :mod:`macos.dock`. They run on any platform."""

import pytest

import macos
from macos import dock


@pytest.fixture
def dock_settings(monkeypatch, tmp_path):
    """The Dock's preferences in a dict, and the restarts counted."""
    store = {
        "persistent-apps": [
            {"tile-data": {"file-data": {"_CFURLString": "file:///Applications/Safari.app/", "_CFURLStringType": 15},
                           "file-label": "Safari", "bundle-identifier": "com.apple.Safari"}, "tile-type": "file-tile"},
        ],
        "tilesize": 48.0,
    }  # fmt: skip
    restarts = []
    monkeypatch.setattr(dock.defaults, "read", lambda domain, key=None, default=None: store.get(key, default))
    monkeypatch.setattr(dock.defaults, "write", lambda domain, key, value: store.__setitem__(key, value))
    monkeypatch.setattr(dock, "restart", lambda: restarts.append(1))
    monkeypatch.setattr(dock.os.path, "realpath", lambda path: path)
    app = tmp_path / "Code.app"
    app.mkdir()
    monkeypatch.setattr(dock._apps, "_locate", lambda name: str(app))
    monkeypatch.setattr(dock._apps, "_bundle_id", lambda path: "com.example.code")
    return store, restarts, app


def test_dock_settings(dock_settings):
    store, restarts, _ = dock_settings

    assert (macos.dock.size(), macos.dock.position(), macos.dock.autohide()) == (48, "bottom", False)
    macos.dock.set_autohide(True)
    macos.dock.set_size(64)
    macos.dock.set_position("left")
    assert (store["autohide"], store["tilesize"], store["orientation"]) == (True, 64.0, "left")
    assert len(restarts) == 3
    with pytest.raises(ValueError, match="16 to 128"):
        macos.dock.set_size(200)
    with pytest.raises(ValueError, match="'left', 'bottom' or 'right'"):
        macos.dock.set_position("top")


def test_dock_apps(dock_settings):
    store, restarts, app = dock_settings

    assert [(entry.name, entry.bundle_id) for entry in macos.dock.apps()] == [("Safari", "com.apple.Safari")]
    added = macos.dock.add_app("Code", index=0)
    assert (added.name, added.bundle_id, added.path) == ("Code", "com.example.code", app)
    assert [entry.name for entry in macos.dock.apps()] == ["Code", "Safari"]
    assert store["persistent-apps"][0]["tile-data"]["file-data"]["_CFURLString"].startswith("file://")
    macos.dock.add_app("Code")  # already there: not twice
    assert [entry.name for entry in macos.dock.apps()] == ["Code", "Safari"] and len(restarts) == 1
    assert macos.dock.remove_app("safari") is True and macos.dock.remove_app("Safari") is False
    assert [entry.name for entry in macos.dock.apps()] == ["Code"]
