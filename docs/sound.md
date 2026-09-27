# Sound

{mod}`macos.sound` plays alert sounds and audio files.

```python
import macos

macos.sound.play("Glass")            # a system alert sound
macos.sound.play("done.mp3")         # an audio file
macos.sound.beep()                   # the alert sound chosen in System Settings
```

## Alert sounds

{func}`~macos.sound.names` lists the sounds you can play by name, the same ones
as in System Settings › Sound:

```python
macos.sound.names()   # ['Basso', 'Blow', 'Bottle', 'Frog', 'Funk', 'Glass', ...]
```

## Audio files

Any format macOS plays works: MP3, AAC/M4A, WAV, AIFF...

```python
macos.sound.play("~/Music/fanfare.m4a", volume=0.5)
```

`volume` goes from 0.0 to 1.0, relative to the system volume (see
[Volume](volume.md) to change that).

## Waiting

{func}`~macos.sound.play` returns when the sound ends. Pass `wait=False` to
return right away while it plays:

```python
macos.sound.play("Submarine", wait=False)
start_long_task()
```

## Reference

- {func}`macos.sound.play`
- {func}`macos.sound.beep`
- {func}`macos.sound.names`
