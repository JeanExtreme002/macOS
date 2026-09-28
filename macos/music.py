# -*- coding: utf-8 -*-

"""
Control Apple Music and Spotify: play, pause, skip, and see what's playing.

::

    macos.music.now_playing()      # Track(title='Imagine', artist='John Lennon', ..., playing=True, app='Music')
    macos.music.pause()
    macos.music.next()
    macos.music.play(app="Spotify")

Goes through AppleScript, like the media keys' equivalents in Shortcuts, so
the first time macOS asks to allow the app running Python (your terminal or
IDE) to control the player; if that's denied,
:class:`~macos.errors.PermissionDeniedError` is raised.
"""

from dataclasses import dataclass
from typing import List, Optional

from . import apps
from ._system import run
from .errors import CommandError, MacOSError, PermissionDeniedError

__all__ = ["Track", "now_playing", "play", "pause", "play_pause", "next", "previous"]

PLAYERS = ("Music", "Spotify")
_SEPARATOR = "\x1f"  # ASCII unit separator: never in a song's title


@dataclass(frozen=True)
class Track:
    """The song a player is on."""

    title: str
    artist: str
    album: str
    duration: Optional[float]
    """In seconds, when the player knows it (not for live radio)."""
    position: Optional[float]
    """How far into the song, in seconds."""
    playing: bool
    """``False`` when paused."""
    app: str
    """``'Music'`` or ``'Spotify'``."""


def _osascript(app: str, script: str) -> str:
    try:
        return run(["osascript", "-e", script])
    except CommandError as error:
        if "-1743" in error.stderr:  # errAEEventNotPermitted
            raise PermissionDeniedError(
                "Automation permission is missing: allow the app running Python (your terminal or IDE) to control "
                "{} in System Settings › Privacy & Security › Automation".format(app)
            ) from None
        raise


def _running() -> List[str]:
    names = {app.name for app in apps.running()}
    return [player for player in PLAYERS if player in names]


def _state(app: str) -> str:
    return _osascript(app, 'tell application "{}" to player state as string'.format(app)).strip()


def _player(app: Optional[str]) -> str:
    """``app``, or the running player (the one playing, if both run), or Music."""
    if app is not None:
        if app not in PLAYERS:
            raise ValueError("app must be one of {}, not {!r}".format(", ".join(PLAYERS), app))
        return app
    running = _running()
    playing = [player for player in running if _state(player) == "playing"]
    return (playing or running or ["Music"])[0]


_TRACK = """
tell application "{app}"
    if player state is stopped then return ""
    set sep to ASCII character 31
    set song to current track
    return (name of song) & sep & (artist of song) & sep & (album of song) & sep & ¬
        (duration of song as string) & sep & (player position as string) & sep & (player state as string)
end tell
"""


def _number(text: str) -> Optional[float]:
    try:
        return float(text.strip().replace(",", "."))  # AppleScript writes reals in the user's locale
    except ValueError:
        return None


def now_playing(app: Optional[str] = None) -> Optional[Track]:
    """
    Return the song Music or Spotify is on (playing or paused), or ``None``.

    ``app`` is ``"Music"`` or ``"Spotify"``; by default, the one playing.
    This never opens a player: when none is running, it returns ``None``.
    """
    if app is not None and app not in PLAYERS:
        raise ValueError("app must be one of {}, not {!r}".format(", ".join(PLAYERS), app))
    candidates = [app] if app is not None else _running()
    candidates = [player for player in candidates if player in _running()]
    found: List[Track] = []
    for player in candidates:
        output = _osascript(player, _TRACK.format(app=player)).rstrip("\n")
        if not output:
            continue
        parts = output.split(_SEPARATOR)
        if len(parts) != 6:
            raise MacOSError("{} returned something unexpected: {!r}".format(player, output))
        title, artist, album, duration, position, state = parts
        seconds = _number(duration)
        if seconds is not None and player == "Spotify":
            seconds /= 1000  # Spotify counts milliseconds
        found.append(
            Track(
                title=title,
                artist=artist,
                album=album,
                duration=seconds if seconds else None,
                position=_number(position),
                playing=state.strip() == "playing",
                app=player,
            )
        )
    playing = [track for track in found if track.playing]
    if playing:
        return playing[0]
    return found[0] if found else None


def _command(command: str, app: Optional[str]) -> None:
    player = _player(app)
    _osascript(player, 'tell application "{}" to {}'.format(player, command))


def play(app: Optional[str] = None) -> None:
    """
    Play (or resume), in ``app`` (``"Music"`` or ``"Spotify"``) or the running player.

    With no player running, it opens Music.
    """
    _command("play", app)


def pause(app: Optional[str] = None) -> None:
    """Pause the player that is playing, or ``app``."""
    _command("pause", app)


def play_pause(app: Optional[str] = None) -> None:
    """Play if paused, pause if playing, like the play/pause key."""
    _command("playpause", app)


def next(app: Optional[str] = None) -> None:
    """Skip to the next song."""
    _command("next track", app)


def previous(app: Optional[str] = None) -> None:
    """Go back to the previous song (or the start of this one, as the player decides)."""
    _command("previous track", app)
