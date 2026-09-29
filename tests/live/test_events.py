"""Tests of :mod:`macos.events` against the real system. Skipped outside macOS."""

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
