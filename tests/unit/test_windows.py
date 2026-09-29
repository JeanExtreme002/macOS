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
