# Power

{mod}`macos.power` reads the battery and keeps the Mac awake while your code
runs.

## Battery

```python
import macos

battery = macos.power.battery()
battery.percent          # 87
battery.charging         # True
battery.plugged_in       # True
battery.time_remaining   # datetime.timedelta(seconds=2700), or None
battery.cycle_count      # 532
battery.health           # 80 (percent of the original capacity)
```

{func}`~macos.power.battery` returns `None` on a Mac without a battery, such as
a Mac mini or an iMac.

`health` is the battery's maximum capacity compared with when it was new, the
same number as System Settings › Battery › Battery Health.

`time_remaining` is the time until the battery is empty, or until it's full
while charging. It's `None` while macOS is still estimating it, and when the
battery is full and plugged in.

## Low Power Mode

```python
macos.power.low_power_mode()   # True when on (System Settings › Battery)
```

Low Power Mode makes the Mac slower to save energy, so a long job can check
it and lighten its work, like {func}`macos.system.thermal_state`.

## Keeping the Mac awake

{func}`~macos.power.keep_awake` stops the Mac from going to sleep while a block
runs, like the `caffeinate` command:

```python
with macos.power.keep_awake():
    train_model()   # takes hours; the Mac won't sleep meanwhile
```

It also works as a decorator:

```python
@macos.power.keep_awake()
def backup():
    ...
```

By default the display can still turn off. Pass `display=True` to keep it on
too, for example while showing a dashboard:

```python
with macos.power.keep_awake(display=True):
    run_dashboard()
```

The `reason` argument names the request in `pmset -g assertions` and in
Activity Monitor. Closing a laptop's lid still puts it to sleep.

## Sleeping

```python
macos.power.sleep()           # put the Mac to sleep now
macos.power.sleep_display()   # turn the display off; the Mac keeps running
```

With the default setting (a password is required right after the display turns
off), {func}`~macos.power.sleep_display` also locks the screen.

## The charger

{func}`~macos.power.adapter` tells about the charger the Mac is plugged into,
or `None` on battery:

```python
macos.power.adapter()   # Adapter(watts=96, name='96W USB-C Power Adapter', manufacturer='Apple Inc.', ...)
```

A charger weaker than the Mac's own charges it slowly, or not at all while
it's busy.

## Reference

- {func}`macos.power.battery`
- {func}`macos.power.low_power_mode`
- {class}`macos.power.Battery`
- {func}`macos.power.keep_awake`
- {func}`macos.power.sleep`
- {func}`macos.power.sleep_display`
- {class}`macos.power.Adapter`
- {func}`macos.power.adapter`
