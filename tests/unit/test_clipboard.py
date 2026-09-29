"""Unit tests for :mod:`macos.clipboard`. They run on any platform."""

import pytest

import macos


def test_clipboard_wait_for_change(monkeypatch):
    counts = iter([1, 1, 1, 2])
    monkeypatch.setattr(macos.clipboard, "change_count", lambda: next(counts))
    monkeypatch.setattr(macos.clipboard, "_is_empty", lambda: False)
    monkeypatch.setattr(macos.clipboard, "paste", lambda: "new text")

    assert macos.clipboard.wait_for_change(interval=0.001) == "new text"


def test_clipboard_wait_for_change_waits_for_the_content_after_a_clear(monkeypatch):
    # The count moves when the copying app clears the clipboard, before it
    # writes the text: reading at that point would give None.
    counts = iter([1, 2, 2, 2])
    empty = iter([True, True, False])
    monkeypatch.setattr(macos.clipboard, "change_count", lambda: next(counts))
    monkeypatch.setattr(macos.clipboard, "_is_empty", lambda: next(empty))
    monkeypatch.setattr(macos.clipboard, "paste", lambda: "written")

    assert macos.clipboard.wait_for_change(interval=0.001) == "written"


def test_clipboard_wait_for_change_times_out(monkeypatch):
    monkeypatch.setattr(macos.clipboard, "change_count", lambda: 1)

    with pytest.raises(TimeoutError):
        macos.clipboard.wait_for_change(timeout=0.01, interval=0.001)


def test_clipboard_wait_for_change_never_sleeps_past_the_timeout(monkeypatch):
    import time

    monkeypatch.setattr(macos.clipboard, "change_count", lambda: 1)
    start = time.monotonic()

    with pytest.raises(TimeoutError):
        macos.clipboard.wait_for_change(timeout=0.05, interval=10)
    assert time.monotonic() - start < 1


def test_copy_files_needs_paths():
    with pytest.raises(ValueError):
        macos.clipboard.copy_files([])


def test_clipboard_watch_yields_each_copy(monkeypatch):
    clipboard = macos.clipboard
    # (change count, empty, content), one per check: a copy clears, then writes.
    states = iter([(1, False, None), (1, False, None), (2, True, None), (3, False, "one"), (3, False, "one"), (4, False, None)])
    current = {}

    def read():
        current["state"] = next(states, (4, False, None))
        return current["state"][0]

    monkeypatch.setattr(clipboard, "change_count", read)
    monkeypatch.setattr(clipboard, "_is_empty", lambda: current["state"][1])
    monkeypatch.setattr(clipboard, "paste", lambda: current["state"][2])
    monkeypatch.setattr(clipboard.time, "sleep", lambda seconds: None)

    watched = clipboard.watch()
    assert next(watched) == "one"
    assert next(watched) is None  # something that isn't text
    watched.close()
    with pytest.raises(ValueError, match="interval"):
        next(clipboard.watch(interval=0))
