"""Unit tests for :mod:`macos.windows`. They run on any platform."""

import macos


def test_set_fullscreen_asks_again_when_macos_drops_the_request(monkeypatch):
    class Window(macos.windows.Window):
        """A window whose first full screen request is dropped, as during an animation."""

        def __init__(self):
            self._element, self.app, self.pid = 0, "Test", 1
            self.state, self.requests = True, 0

        @property
        def fullscreen(self):
            return self.state

        def _set_flag(self, attribute, on, what):
            self.requests += 1
            if self.requests >= 2:
                self.state = on

    monkeypatch.setattr(macos.windows, "_FULL_SCREEN_RETRY", 0.05)
    monkeypatch.setattr(macos.windows, "_FULL_SCREEN_ANIMATION", 0)
    window = Window()

    window.set_fullscreen(False)

    assert window.fullscreen is False and window.requests == 2


def test_windows_wait_for(monkeypatch):
    windows = macos.windows
    answers = iter([[], [], ["the window"]])
    monkeypatch.setattr(windows, "list", lambda app=None, title=None: next(answers))
    monkeypatch.setattr(windows.time, "sleep", lambda seconds: None)

    assert windows.wait_for("TextEdit", title="Save") == "the window"
    monkeypatch.setattr(windows, "list", lambda app=None, title=None: [])
    assert windows.wait_for(title="Save", timeout=0) is None


def test_tile_grid():
    from macos.windows import _grid

    area = (0, 25, 1200, 800)
    assert _grid(1, area, None, 0) == [(0, 25, 1200, 800)]
    assert _grid(2, area, None, 0) == [(0, 25, 600, 800), (600, 25, 600, 800)]
    # Three windows: two on top, and the last one alone below, as wide as the display.
    assert _grid(3, area, None, 0) == [(0, 25, 600, 400), (600, 25, 600, 400), (0, 425, 1200, 400)]
    assert _grid(3, area, 3, 0) == [(0, 25, 400, 800), (400, 25, 400, 800), (800, 25, 400, 800)]
    assert _grid(2, area, 1, 10) == [(10, 35, 1180, 385), (10, 430, 1180, 385)]  # gaps around and between
    assert _grid(2, area, 5, 0) == _grid(2, area, None, 0)  # no more columns than windows
    assert _grid(0, area, None, 0) == []


class _FakeWindow:
    def __init__(self, x, y):
        self.frame = (x, y, 300, 200)

    @property
    def position(self):
        return self.frame[:2]

    def set_frame(self, x, y, width, height):
        self.frame = (x, y, width, height)


def test_tile_keeps_each_display_and_the_order(monkeypatch):
    import pytest

    from macos import windows

    monkeypatch.setattr(windows, "_usable_areas", lambda: [(0, 25, 1000, 800), (1000, 0, 800, 600)])
    right, left, other = _FakeWindow(500, 100), _FakeWindow(20, 100), _FakeWindow(1100, 50)

    windows.tile([right, left, other])

    assert left.frame == (0, 25, 500, 800) and right.frame == (500, 25, 500, 800)  # by where they were
    lower = _FakeWindow(0, 600)
    windows.tile([lower, right, left], display=1)
    assert [window.frame[:2] for window in (left, right, lower)] == [(0, 25), (500, 25), (0, 425)]  # reading order
    assert other.frame == (1000, 0, 800, 600)  # alone on the second display

    windows.tile([right, left, other], display=2, gap=10)
    assert all(1000 <= window.frame[0] < 1800 for window in (right, left, other))

    with pytest.raises(ValueError, match="no display 3"):
        windows.tile([left], display=3)
    with pytest.raises(ValueError, match="columns must be at least 1"):
        windows.tile([left], columns=0)
