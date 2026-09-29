"""Unit tests for :mod:`macos.events`. They run on any platform."""

import pytest

import macos
from macos import events


@pytest.fixture(autouse=True)
def no_handlers():
    events._handlers.clear()
    yield
    events._handlers.clear()


def test_events_registry():
    first = events.on("wake", print)
    second = events.on("wake", repr)
    launched = events.on("app_launched", print)

    assert repr(first) == "Handler('wake')"
    first.remove()
    assert events._handlers == [second, launched]
    events.off("wake")
    assert events._handlers == [launched]
    events.off(launched)
    events.off(launched)  # removing twice is harmless
    assert events._handlers == []


def test_events_argument_checks():
    with pytest.raises(ValueError, match="unknown event 'coffee'"):
        events.on("coffee", print)
    with pytest.raises(ValueError, match="unknown event"):
        events.wait("coffee")
    with pytest.raises(ValueError, match="unknown event"):
        events.off("coffee")
    with pytest.raises(ValueError, match="no callbacks registered"):
        events.run()


def test_events_run_calls_the_callbacks_of_each_event(monkeypatch):
    calls = []
    events.on("wake", lambda event: calls.append(("a", event.name)))
    events.on("wake", lambda event: calls.append(("b", event.name)))
    events.on("sleep", lambda event: calls.append(("c", event.name)))
    events.on("sleep", lambda: calls.append(("d", "no arguments")))
    events.on("sleep", print)  # a builtin: it gets the event

    def listen(names, on_event, timeout):
        assert names == ["sleep", "wake"]
        for name in ("wake", "sleep"):
            on_event(macos.events.Event(name))

    monkeypatch.setattr(events, "_listen", listen)
    events.run()

    assert calls == [("a", "wake"), ("b", "wake"), ("c", "sleep"), ("d", "no arguments")]


def test_events_wait_returns_the_awaited_event(monkeypatch):
    def listen(names, on_event, timeout):
        assert names == ["wake"]
        for name in ("wake",):
            if on_event(macos.events.Event(name)):
                return

    monkeypatch.setattr(events, "_listen", listen)
    assert events.wait("wake") == macos.events.Event("wake")
    monkeypatch.setattr(events, "_listen", lambda names, on_event, timeout: None)
    assert events.wait("wake", timeout=0.1) is None


def test_events_names_cover_every_source():
    assert set(events.NAMES) >= {
        "space_changed", "app_hidden", "app_unhidden", "power_connected", "power_disconnected",
        "network_changed", "usb_connected", "usb_disconnected", "displays_changed",
    }  # fmt: skip
    assert events.Event("usb_connected", device="USB Keyboard").device == "USB Keyboard"
