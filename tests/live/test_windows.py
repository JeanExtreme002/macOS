"""Tests of :mod:`macos.windows` against the real system. Skipped outside macOS."""

import os
import time
import uuid
from pathlib import Path

import pytest

import macos


@pytest.fixture
def test_window():
    """A window of our own, in a helper process, to move around without touching the user's."""
    import subprocess
    import sys

    if not macos.windows.has_permission():
        pytest.skip("no Accessibility permission")
    front = macos.windows.focused()
    title = "pymacos test {}".format(uuid.uuid4().hex[:8])
    helper = Path(__file__).with_name("_window_app.py")
    process = subprocess.Popen([sys.executable, str(helper), title, "20"], stdout=subprocess.PIPE, text=True)
    try:
        process.stdout.readline()
        app = next(app for app in macos.apps.running(include_background=True) if app.pid == process.pid)
        for _ in range(20):
            found = macos.windows.list(app, title=title)
            if found:
                break
            time.sleep(0.1)
        yield found[0]
    finally:
        process.kill()
        process.wait()
        if front is not None:
            try:
                front.focus()  # give the focus back
            except macos.MacOSError:
                pass


def test_windows(test_window):
    window = test_window

    window.set_frame(60, 80, 420, 300)
    time.sleep(0.2)
    assert window.frame == (60, 80, 420, 300)
    window.move(100, 120)
    window.resize(360, 260)
    time.sleep(0.2)
    assert (window.position, window.size) == ((100, 120), (360, 260))

    window.center()
    time.sleep(0.2)
    display = macos.screen.displays()[0]
    x, y, width, height = window.frame
    assert (width, height) == (360, 260)  # the same size
    assert abs(x + width / 2 - (display.x + display.width / 2)) <= 1
    assert abs(y + height / 2 - (display.y + display.height / 2)) <= 1

    assert window.fullscreen is False
    if os.environ.get("CI"):  # it switches to a Space of its own: not on the user's Mac
        window.set_fullscreen()  # returns once the animation is done
        assert window.fullscreen
        window.set_fullscreen(False)
        assert not window.fullscreen

    window.minimize()
    time.sleep(0.8)
    assert window.minimized
    window.restore()
    time.sleep(0.8)
    assert not window.minimized

    window.focus()
    for _ in range(20):
        if macos.windows.focused() == window:
            break
        time.sleep(0.1)
    else:
        # The user (or another app) may have taken the focus meanwhile: the
        # window must at least be its app's main one.
        from macos import _cf

        main = window._read("AXMain")
        with _cf.owned(main):
            assert _cf.to_bool(main)
    assert window in macos.windows.list()

    window.close()
    time.sleep(0.5)
    with pytest.raises(macos.MacOSError):
        window.title
