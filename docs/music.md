# Music

{mod}`macos.music` controls Apple Music and Spotify: play, pause, skip, and
what's playing.

```python
import macos

macos.music.now_playing()
# Track(title='Imagine', artist='John Lennon', album='Imagine', duration=183.0,
#       position=12.0, playing=True, app='Music')

macos.music.pause()
macos.music.next()
```

## What's playing

{func}`~macos.music.now_playing` returns the song Music or Spotify is on,
playing or paused, as a {class}`~macos.music.Track`, or `None`. When both run,
it prefers the one playing. It never opens a player: with none running, it
returns `None`.

## Controlling the player

```python
macos.music.play()               # or resume
macos.music.pause()
macos.music.play_pause()         # like the play/pause key
macos.music.next()
macos.music.previous()
macos.music.play(app="Spotify")
```

Without `app`, they control the player that's playing, or the one running.
With none running, {func}`~macos.music.play` opens Music.

The first time, macOS asks to allow the app running Python to control the
player (see [Permissions](permissions.md#automation)).

## Reference

- {func}`macos.music.now_playing`
- {func}`macos.music.play`
- {func}`macos.music.pause`
- {func}`macos.music.play_pause`
- {func}`macos.music.next`
- {func}`macos.music.previous`
- {class}`macos.music.Track`
