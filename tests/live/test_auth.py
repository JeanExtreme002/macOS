"""Tests of :mod:`macos.auth` against the real system. Skipped outside macOS."""

import macos


def test_auth_is_available():
    assert macos.auth.is_available() in (True, False)
    if not macos.auth.is_available(only_touch_id=True):
        # Without Touch ID, asking for it alone fails before showing anything.
        try:
            macos.auth.confirm("test", only_touch_id=True)
        except macos.NotSupportedError:
            pass
