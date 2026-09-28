# System

{mod}`macos.system` tells you about the Mac your code runs on.

```python
import macos

macos.system.version()            # '15.6.1'
macos.system.build()              # '24G90'
macos.system.model()              # 'MacBook Pro'
macos.system.model_identifier()   # 'Mac14,9'
macos.system.processor()          # 'Apple M2 Pro'
macos.system.memory()             # 17179869184 (bytes)
macos.system.computer_name()      # "Alice's MacBook Pro"
macos.system.uptime()             # datetime.timedelta(days=3, seconds=7200)
macos.system.idle_time()          # datetime.timedelta(seconds=312)
```

{func}`~macos.system.memory` is in bytes: divide by `2**30` for GB.
{func}`~macos.system.uptime` counts from the last restart, including the time
the Mac spent asleep.

## Volumes

{func}`~macos.system.volumes` lists the mounted volumes that Finder shows, and {func}`~macos.system.eject` ejects one:

```python
for volume in macos.system.volumes():
    print(volume.name, volume.free // 2**30, "GB free")

macos.system.eject("Backup")         # by name, by path, or a Volume
```

Each {class}`~macos.system.Volume` has its `name`, mount `path`, `total` and
`free` space in bytes, and whether it `is_internal`, `is_removable` (USB sticks,
SD cards) or `is_ejectable`.

{func}`~macos.system.eject` only accepts ejectable
volumes; when two share a name, pass the path.

## Fonts

{func}`~macos.system.fonts` lists the installed font families, sorted, as apps
show them in their font menus:

```python
families = macos.system.fonts()   # ['Academy Engraved LET', 'American Typewriter', ...]
font = "Avenir" if "Avenir" in families else "Helvetica"
```

## Heat and lid

```python
macos.system.thermal_state()   # 'nominal', 'fair', 'serious' or 'critical'
macos.system.lid_closed()      # True in clamshell mode
```

At `'serious'`, macOS slows the processor down to cool it, so a long job can
wait for it to cool:

```python
import time

while macos.system.thermal_state() in ("serious", "critical"):
    time.sleep(60)
```

{func}`~macos.system.lid_closed` tells whether a MacBook runs with its lid
closed, on an external display. On a Mac without a lid it raises
{class}`~macos.NotSupportedError`.

## Camera and microphone in use

```python
macos.system.camera_in_use()       # True during a video call
macos.system.microphone_in_use()   # True while an app records
```

They match the green camera light and the orange microphone dot in the menu
bar. They don't tell which app, and need no permission. An "on air" light in a
few lines:

```python
import time

while True:
    busy = macos.system.camera_in_use() or macos.system.microphone_in_use()
    set_light(busy)   # your smart plug, LED...
    time.sleep(5)
```

## Running while the user is away

{func}`~macos.system.idle_time` is the time since the last keyboard, mouse or
trackpad input. It lets a script do heavy work only when nobody is using the
Mac:

```python
import time
from datetime import timedelta

while True:
    if macos.system.idle_time() > timedelta(minutes=10):
        run_heavy_job()
    time.sleep(60)
```

## Reference

- {func}`macos.system.version`
- {func}`macos.system.build`
- {func}`macos.system.model`
- {func}`macos.system.model_identifier`
- {func}`macos.system.processor`
- {func}`macos.system.memory`
- {func}`macos.system.computer_name`
- {func}`macos.system.uptime`
- {func}`macos.system.idle_time`
- {func}`macos.system.volumes`
- {func}`macos.system.eject`
- {func}`macos.system.fonts`
- {func}`macos.system.thermal_state`
- {func}`macos.system.lid_closed`
- {func}`macos.system.camera_in_use`
- {func}`macos.system.microphone_in_use`
- {class}`macos.system.Volume`
