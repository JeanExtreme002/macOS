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

## Reference

- {func}`macos.audio.devices`
- {func}`macos.audio.outputs`
- {func}`macos.audio.inputs`
- {func}`macos.audio.default_output`
- {func}`macos.audio.default_input`
- {func}`macos.audio.set_output`
- {func}`macos.audio.set_input`
- {class}`macos.audio.Device`
