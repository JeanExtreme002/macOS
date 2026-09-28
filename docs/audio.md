# Audio

{mod}`macos.audio` lists the audio devices and switches the default output
(speakers, headphones, a display's audio...) and input (microphones), like
System Settings › Sound.

```python
import macos

[device.name for device in macos.audio.outputs()]
# ['MacBook Pro Speakers', "Alice's AirPods Pro", 'LG UltraFine']

macos.audio.default_output()          # Device(name='MacBook Pro Speakers', ...)
macos.audio.set_output("AirPods")     # sound now plays through the AirPods
```

## Devices

{func}`~macos.audio.outputs` returns the devices that play sound,
{func}`~macos.audio.inputs` those that record, and
{func}`~macos.audio.devices` all of them. Each {class}`~macos.audio.Device`
has:

- `name`: as shown in System Settings, in the system's language.
- `uid`: a stable identifier that survives reconnecting the device.
- `transport`: how it's connected, such as `'builtin'`, `'usb'`,
  `'bluetooth'`, `'hdmi'` or `'airplay'`.
- `is_output` and `is_input`: a headset can be both.

## Switching

{func}`~macos.audio.set_output` and {func}`~macos.audio.set_input` take a
{class}`~macos.audio.Device`, its full name, its `uid`, or part of its name when
only one device matches:

```python
macos.audio.set_output("AirPods")                  # part of the name
macos.audio.set_input("MacBook Pro Microphone")
```

A name that matches several devices raises `ValueError`, listing them. For
example, to go back to the built-in speakers after a call:

```python
speakers = next(d for d in macos.audio.outputs() if d.transport == "builtin")
macos.audio.set_output(speakers)
```

## Microphone volume and mute

```python
macos.audio.input_volume()          # 0.75, from 0.0 to 1.0
macos.audio.set_input_volume(0.5)

macos.audio.input_muted()           # False
macos.audio.mute_input()            # every app now hears silence
macos.audio.mute_input(False)
```

They act on the default input, or on `device=`, given as for
{func}`~macos.audio.set_input`. Muting works for every app at once, which
makes a handy "mute me" shortcut in meetings. Microphones without a mute
switch raise {class}`~macos.NotSupportedError`; set their volume to 0
instead. To know whether an app is recording, see
{func}`macos.system.microphone_in_use`.

## Recording the microphone

{func}`~macos.audio.record` records the default input into a file, and returns
when the recording ends:

```python
macos.audio.record("memo.m4a", 30)             # AAC, small
macos.audio.record("take.wav", 10, channels=2)  # uncompressed, stereo
```

The extension sets the format: `.m4a`, `.wav`, `.aiff` or `.caf`. To record
another microphone, switch to it first with {func}`~macos.audio.set_input`.

{func}`~macos.audio.input_level` tells how loud the microphone hears it right
now, from 0.0 (silence) to 1.0: about 0.01 in a quiet room, 0.1 to 0.3 for
someone talking nearby.

```python
import time

while macos.audio.input_level() > 0.05:   # wait for quiet
    time.sleep(1)
```

Both need the [Microphone permission](permissions.md#camera-and-microphone),
which macOS asks for the first time. They keep nothing but the file you ask
for.

## Reference

- {func}`macos.audio.devices`
- {func}`macos.audio.outputs`
- {func}`macos.audio.inputs`
- {func}`macos.audio.default_output`
- {func}`macos.audio.default_input`
- {func}`macos.audio.set_output`
- {func}`macos.audio.set_input`
- {func}`macos.audio.input_volume`
- {func}`macos.audio.set_input_volume`
- {func}`macos.audio.input_muted`
- {func}`macos.audio.mute_input`
- {func}`macos.audio.record`
- {func}`macos.audio.input_level`
- {func}`macos.audio.has_permission`
- {func}`macos.audio.request_permission`
- {class}`macos.audio.Device`
