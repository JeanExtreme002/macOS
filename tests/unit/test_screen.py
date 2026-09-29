"""Unit tests for :mod:`macos.screen`. They run on any platform."""

import subprocess
import sys

import pytest

import macos
from macos import _system, screen


def test_screenshot_arguments(fake_run, tmp_path):
    target = macos.screenshot(tmp_path / "shot.JPG", region=(1, 2, 30, 40), display=2, cursor=True, check_permission=False)

    assert target == (tmp_path / "shot.JPG").resolve()
    assert fake_run.args == ["screencapture", "-x", "-t", "jpg", "-C", "-R1,2,30,40", "-D2", str(target)]


def test_screenshot_defaults_to_a_temporary_png(fake_run):
    target = macos.screenshot(check_permission=False)
    try:
        assert target.suffix == ".png"
        assert fake_run.args[-1] == str(target)
    finally:
        target.unlink()


def test_screenshot_rejects_unknown_format(fake_run, tmp_path):
    with pytest.raises(ValueError, match="unsupported image format"):
        macos.screenshot(tmp_path / "shot.bmp", check_permission=False)


def test_screenshot_raises_without_permission(fake_run, monkeypatch, tmp_path):
    monkeypatch.setattr(screen, "has_permission", lambda: False)

    with pytest.raises(macos.PermissionDeniedError, match="Screen Recording"):
        macos.screenshot(tmp_path / "shot.png")
    assert fake_run.calls == []


def test_failed_screenshot_removes_its_temporary_file(fake_run, monkeypatch, tmp_path):
    fake_run.returncode = 1
    monkeypatch.setattr(screen.tempfile, "tempdir", str(tmp_path))

    with pytest.raises(macos.CommandError):
        macos.screenshot(display=9, check_permission=False)

    assert list(tmp_path.iterdir()) == []


def test_start_screensaver(fake_run):
    macos.screen.start_screensaver()

    assert fake_run.args == ["open", "-a", "ScreenSaverEngine"]


def test_lock(monkeypatch):
    from types import SimpleNamespace

    calls = []

    def lock_now():
        calls.append("lock")
        return login.status

    login = SimpleNamespace(status=0, SACLockScreenImmediate=lock_now)
    monkeypatch.setattr(macos.screen, "private_framework", lambda name: login)

    macos.screen.lock()
    assert calls == ["lock"]

    login.status = 1
    with pytest.raises(macos.MacOSError, match="could not lock"):
        macos.screen.lock()


@pytest.mark.skipif(sys.platform != "darwin", reason="builds real Core Foundation dictionaries")
@pytest.mark.parametrize(
    "session, locked", [({"kCGSSessionOnConsoleKey": True}, False), ({"CGSSessionScreenIsLocked": True}, True)]
)
def test_is_locked_reads_the_session(monkeypatch, session, locked):
    from types import SimpleNamespace

    from macos import _cf

    graphics = SimpleNamespace(CGSessionCopyCurrentDictionary=lambda: _cf.from_python(session))
    monkeypatch.setattr(macos.screen, "framework", lambda name: graphics)

    assert macos.screen.is_locked() is locked


def test_screen_record_command(fake_run, monkeypatch, tmp_path):
    target = tmp_path / "demo.mov"
    monkeypatch.setattr(macos.screen, "has_permission", lambda: True)

    def record(args, **kwargs):
        fake_run(args, **kwargs)
        target.write_bytes(b"movie")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(_system.subprocess, "run", record)

    assert macos.screen.record(target, 2.4, region=(0, 0, 800, 600), display=2, audio=True, clicks=True) == target
    assert fake_run.args == ["screencapture", "-x", "-v", "-V2", "-R0,0,800,600", "-D2", "-g", "-k", str(target)]


def test_screen_record_needs_the_permission(fake_run, monkeypatch, tmp_path):
    monkeypatch.setattr(macos.screen, "has_permission", lambda: False)

    with pytest.raises(macos.PermissionDeniedError, match="Screen Recording"):
        macos.screen.record(tmp_path / "demo.mov", 1)


def test_screen_argument_checks(tmp_path):
    with pytest.raises(ValueError, match="0.0 to 1.0"):
        macos.screen.set_brightness(1.5)
    with pytest.raises(ValueError, match="positive"):
        macos.screen.record(tmp_path / "out.mov", 0)
    with pytest.raises(ValueError, match=".mov"):
        macos.screen.record(tmp_path / "out.mp4", 1)


def test_find_text_maps_the_boxes_to_the_screen(monkeypatch, tmp_path):
    from macos import vision

    shot = tmp_path / "shot.png"
    shot.write_bytes(b"png")
    main = screen.Display(1, "Main", 1000, 800, 0, 0, 2000, 1600, 2.0, 60.0, True, False)
    side = screen.Display(2, "Side", 500, 400, 1000, -100, 500, 400, 1.0, 60.0, False, False)
    monkeypatch.setattr(screen, "displays", lambda: [main, side])

    def capture(**kwargs):
        shot.write_bytes(b"png")
        return shot

    monkeypatch.setattr(screen, "screenshot", capture)
    boxes = [("Click Submit below", (0.5, 0.25, 0.1, 0.05))]
    monkeypatch.setattr(vision, "_occurrences", lambda image, text, languages: boxes)

    match = screen.find_text("submit")[0]
    assert (match.text, match.x, match.y, match.width, match.height) == ("Click Submit below", 500, 200, 100, 40)
    assert match.center == (550, 220)
    assert not shot.exists()  # the capture is deleted
    on_side = screen.find_text("x", display=2)[0]
    assert (on_side.x, on_side.y) == (1250, 0)  # the side display starts at (1000, -100)
    in_region = screen.find_text("x", region=(100, 100, 200, 100))[0]
    assert (in_region.x, in_region.y) == (200, 125)
    with pytest.raises(ValueError, match="no display 3"):
        screen.find_text("x", display=3)


def test_wait_for_text(monkeypatch):
    results = iter([[], [], [screen.TextMatch("OK", 1, 2, 3, 4)]])
    monkeypatch.setattr(screen, "find_text", lambda *args, **kwargs: next(results))
    monkeypatch.setattr(screen.time, "sleep", lambda seconds: None)

    assert screen.wait_for_text("ok") == screen.TextMatch("OK", 1, 2, 3, 4)
    monkeypatch.setattr(screen, "find_text", lambda *args, **kwargs: [])
    assert screen.wait_for_text("ok", timeout=0) is None


def test_find_text_argument_checks():
    with pytest.raises(ValueError, match="empty"):
        screen.find_text("  ")
    with pytest.raises(ValueError, match="interval"):
        screen.wait_for_text("ok", interval=0)
