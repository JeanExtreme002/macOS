# Volume

{mod}`macos.volume` reads and changes the output volume, like the volume keys.

```python
import macos

macos.volume.get()        # 50
macos.volume.set(30)      # from 0 (silent) to 100

macos.volume.mute()
macos.volume.is_muted()   # True
macos.volume.unmute()
```

Muting keeps the level: after {func}`~macos.volume.unmute`, the volume is back
where it was. {func}`~macos.volume.set` doesn't unmute.

{func}`~macos.volume.set` takes an `int` from 0 to 100, and raises
`ValueError` (or `TypeError`) for anything else.

## Devices without volume control

Some output devices, such as certain HDMI displays and USB audio interfaces,
have no volume control of their own. For them, {func}`~macos.volume.get` and
{func}`~macos.volume.is_muted` return `None`.

## Lowering the volume for a moment

```python
level = macos.volume.get()

if level is None:   # a device without volume control
    macos.say("Quiet announcement")
else:
    macos.volume.set(10)
    try:
        macos.say("Quiet announcement")
    finally:
        macos.volume.set(level)
```

## Reference

- {func}`macos.volume.get`
- {func}`macos.volume.set`
- {func}`macos.volume.mute`
- {func}`macos.volume.unmute`
- {func}`macos.volume.is_muted`
