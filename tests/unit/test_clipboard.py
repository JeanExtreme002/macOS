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
