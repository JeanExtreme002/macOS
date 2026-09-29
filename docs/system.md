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

## Disk images

{func}`~macos.system.mount_image` mounts a `.dmg` (or `.iso`) without opening a
Finder window, and returns where; {func}`~macos.system.unmount_image` unmounts it:

```python
mounted = macos.system.mount_image("~/Downloads/Tool.dmg")   # PosixPath('/Volumes/Tool')
print(list(mounted.iterdir()))
macos.system.unmount_image(mounted)
```

A license the image shows first is accepted. To install the app it holds, see
{func}`macos.apps.install_from_dmg`.

## Software updates

{func}`~macos.system.available_updates` lists the updates Software Update offers,
as {class}`~macos.system.Update` objects:

```python
for update in macos.system.available_updates():
    print(update.title, update.version, "(restart)" if update.restart else "")
```

It asks Apple's servers, so it takes a while (often 10 to 30 seconds).

## Processor and memory

{func}`~macos.system.cpu_usage` measures how busy the processor is over a short
`interval`, from 0.0 to 1.0, all cores together, and
{func}`~macos.system.memory_usage` how the memory is used, as Activity Monitor
counts it:

```python
macos.system.cpu_usage()            # 0.23
memory = macos.system.memory_usage()
print(memory.percent, memory.used // 2**30, "GB used of", memory.total // 2**30)
```

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

{func}`~macos.system.wait_for_idle` waits until nobody has touched the Mac for a
while, and {func}`~macos.system.wait_for_activity` until someone does:

```python
macos.system.wait_for_idle(timedelta(minutes=10))
run_heavy_job()

macos.system.wait_for_activity()
macos.say("Welcome back")
```

## System settings

| Read | Change | Values |
|---|---|---|
| {func}`~macos.system.ds_store_on_network` | {func}`~macos.system.set_ds_store_on_network` | `False` stops Finder leaving `.DS_Store` files on network shares |
| {func}`~macos.system.ds_store_on_usb` | {func}`~macos.system.set_ds_store_on_usb` | the same on USB drives and other external disks |
| {func}`~macos.system.keep_windows_on_quit` | {func}`~macos.system.set_keep_windows_on_quit` | `True` makes apps reopen the windows they had |
| {func}`~macos.system.save_to_icloud_by_default` | {func}`~macos.system.set_save_to_icloud_by_default` | iCloud Drive offered first when saving a new document |
| {func}`~macos.system.expanded_save_dialog` | {func}`~macos.system.set_expanded_save_dialog` | the Save dialog opened with the sidebar and every folder |
| {func}`~macos.system.measurement_units` | {func}`~macos.system.set_measurement_units` | `"metric"` or `"us"` |
| {func}`~macos.system.temperature_unit` | {func}`~macos.system.set_temperature_unit` | `"celsius"` or `"fahrenheit"` |
| {func}`~macos.system.open_photos_on_device_connect` | {func}`~macos.system.set_open_photos_on_device_connect` | `False` stops Photos opening when an iPhone or a camera is connected |
| {func}`~macos.system.battery_percentage_shown` | {func}`~macos.system.set_show_battery_percentage` | the percentage next to the battery in the menu bar |

```python
macos.system.set_ds_store_on_network(False)      # colleagues on the share will thank you
macos.system.set_show_battery_percentage(True)
```

The `.DS_Store` settings take effect at the next login; the others at once or
when apps are reopened. No permission is needed.

{func}`~macos.system.set_clock_format` changes the menu bar's clock; the
options left out stay as they are:

```python
macos.system.set_clock_format(seconds=True, date="always")   # date: "auto", "always" or "never"
macos.system.clock_format()   # {'seconds': True, 'day_of_week': True, 'am_pm': True, 'analog': False, 'date': 'always'}
```

It also takes `day_of_week`, `am_pm` and `analog`. Whether it's 12 or 24 hours
follows System Settings › General › Date & Time.

## The menu bar

{func}`~macos.system.set_menu_bar_items` shows or hides Control Center's icons
in the menu bar, and {func}`~macos.system.set_menu_bar_spacing` puts them
closer together, so more fit beside the notch:

```python
macos.system.set_menu_bar_items(bluetooth=True, now_playing=False, focus=False)
macos.system.menu_bar_items()            # {'wifi': True, 'bluetooth': True, 'now_playing': False, ...}
macos.system.set_menu_bar_spacing(6)     # at the next login; None for macOS's own
```

The icons are in {data}`~macos.system.MENU_BAR_ITEMS`, and apply at once.

## Security

{func}`~macos.system.security_status` tells whether the Mac's protections are
on, without an administrator's password, to check a fleet of Macs against
a security policy:

```python
macos.system.security_status()
# SecurityStatus(filevault=True, firewall=False, gatekeeper=True, sip=True)
```

Each is `None` when macOS doesn't say.

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
- {func}`macos.system.wait_for_idle`
- {func}`macos.system.wait_for_activity`
- {func}`macos.system.mount_image`
- {func}`macos.system.unmount_image`
- {func}`macos.system.available_updates`
- {class}`macos.system.Update`
- {func}`macos.system.cpu_usage`
- {func}`macos.system.memory_usage`
- {class}`macos.system.MemoryUsage`
- {func}`macos.system.ds_store_on_network`
- {func}`macos.system.set_ds_store_on_network`
- {func}`macos.system.ds_store_on_usb`
- {func}`macos.system.set_ds_store_on_usb`
- {func}`macos.system.keep_windows_on_quit`
- {func}`macos.system.set_keep_windows_on_quit`
- {func}`macos.system.battery_percentage_shown`
- {func}`macos.system.set_show_battery_percentage`
- {func}`macos.system.save_to_icloud_by_default`
- {func}`macos.system.set_save_to_icloud_by_default`
- {func}`macos.system.expanded_save_dialog`
- {func}`macos.system.set_expanded_save_dialog`
- {func}`macos.system.clock_format`
- {func}`macos.system.set_clock_format`
- {func}`macos.system.measurement_units`
- {func}`macos.system.set_measurement_units`
- {func}`macos.system.temperature_unit`
- {func}`macos.system.set_temperature_unit`
- {func}`macos.system.open_photos_on_device_connect`
- {func}`macos.system.set_open_photos_on_device_connect`
- {func}`macos.system.menu_bar_spacing`
- {func}`macos.system.set_menu_bar_spacing`
- {data}`macos.system.MENU_BAR_ITEMS`
- {func}`macos.system.menu_bar_items`
- {func}`macos.system.set_menu_bar_items`
- {class}`macos.system.SecurityStatus`
- {func}`macos.system.security_status`
