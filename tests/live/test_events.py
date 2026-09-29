"""Tests of :mod:`macos.events` against the real system. Skipped outside macOS."""

import subprocess
import sys
import threading
import time

import macos
from macos import _objc


def _post_wake(delay):
    """Post a wake notification to this process's workspace center: the Mac itself stays awake."""

    def post():
        time.sleep(delay)
        center = _objc.send(_objc.send(_objc.cls("NSWorkspace"), "sharedWorkspace"), "notificationCenter")
        _objc.send(
            center,
            "postNotificationName:object:",
            _objc.nsstring("NSWorkspaceDidWakeNotification"),
            None,
            argtypes=(_objc.id, _objc.id),
            restype=None,
        )

    threading.Thread(target=post).start()


def test_events_wait_and_run():
    _post_wake(0.5)
    assert macos.events.wait("wake", timeout=10) == macos.events.Event("wake")
    assert macos.events.wait("wake", timeout=0.3) is None

    seen = []
    handler = macos.events.on("wake", lambda event: (seen.append(event.name), macos.events.stop()))
    try:
        _post_wake(0.5)
        macos.events.run(timeout=10)
    finally:
        handler.remove()
    assert seen == ["wake"]


def test_events_get_distributed_notifications_from_other_processes(monkeypatch):
    """Like the system's (the screen locking), posted by another process without asking to deliver immediately."""
    from macos import events

    monkeypatch.setitem(events._NOTIFICATIONS, "test_ping", (events._DISTRIBUTED, "com.github.pymacos.test-ping"))
    events._notification_names.cache_clear()

    poster = (
        "import time; from macos import _objc; time.sleep(0.5); "
        "center = _objc.send(_objc.cls('NSDistributedNotificationCenter'), 'defaultCenter'); "
        "_objc.send(center, 'postNotificationName:object:userInfo:deliverImmediately:', "
        "_objc.nsstring('com.github.pymacos.test-ping'), None, None, False, "
        "argtypes=(_objc.id, _objc.id, _objc.id, _objc.BOOL), restype=None)"
    )

    def post():
        subprocess.run([sys.executable, "-c", poster], check=True)

    threading.Thread(target=post).start()
    try:
        assert events.wait("test_ping", timeout=10) == events.Event("test_ping")
    finally:
        events._notification_names.cache_clear()
