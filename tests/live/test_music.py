"""Tests of :mod:`macos.music` against the real system. Skipped outside macOS."""

import macos


def test_now_playing_never_opens_the_player():
    running = {app.name for app in macos.apps.running()}

    track = macos.music.now_playing()

    assert track is None or track.app in macos.music.PLAYERS
    assert {app.name for app in macos.apps.running()} & set(macos.music.PLAYERS) == running & set(macos.music.PLAYERS)
