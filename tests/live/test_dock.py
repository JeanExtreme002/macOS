"""Tests of :mod:`macos.dock` against the real system. Skipped outside macOS."""

import subprocess
import time

import macos
from tests.helpers import SETTINGS


def test_dock_reads_its_settings():
    assert macos.dock.position() in ("left", "bottom", "right")
    assert 16 <= macos.dock.size() <= 128
    assert isinstance(macos.dock.autohide(), bool)
    assert all(app.name for app in macos.dock.apps())


@SETTINGS
def test_dock_add_and_remove_an_app():
    before = macos.defaults.read("com.apple.dock", "persistent-apps")
    try:
        added = macos.dock.add_app("Chess")
        assert added.bundle_id == "com.apple.Chess" and any(app.path == added.path for app in macos.dock.apps())
        assert macos.dock.remove_app("com.apple.Chess") is True
        assert not any(app.path == added.path for app in macos.dock.apps())
    finally:
        macos.defaults.write("com.apple.dock", "persistent-apps", before)
        macos.dock.restart()
        # Leave a Dock restarted the ordinary way, as a quitting one saves its (restored) state.
        subprocess.run(["killall", "Dock"])
        time.sleep(3)
