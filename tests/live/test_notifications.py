"""Tests of :mod:`macos.notifications` against the real system. Skipped outside macOS."""

import macos


def test_notifications_is_allowed():
    assert macos.notifications.is_allowed() in (True, False, None)
