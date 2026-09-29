# Screen

{mod}`macos.screen` takes screenshots and tells you about the connected
displays.

## Screenshots

{func}`macos.screenshot` captures the screen to an image file and returns its
path as a {class}`pathlib.Path`.

```python
import macos

macos.screenshot("screen.png")
```

Without a path, the image goes to a temporary PNG file; deleting it is up to
you:

```python
path = macos.screenshot()
...
path.unlink()
```

### Options

```python
macos.screenshot("area.png", region=(0, 0, 800, 600))    # x, y, width, height
macos.screenshot("second.png", display=2)                # another display
macos.screenshot("pointer.png", cursor=True)             # include the mouse pointer
```

- `region` is in points, measured from the top-left corner of the main display.
- `display` counts from `1`, the main display.

The format follows the file extension: `.png`, `.jpg` (or `.jpeg`), `.heic`,
`.tiff`, `.gif` or `.pdf`. Anything else raises `ValueError`.

### Permission

Capturing other apps' windows requires the *Screen Recording* permission.

Without it, macOS silently returns an image with only the wallpaper and the menu bar, so
{func}`~macos.screenshot` checks first and raises
{class}`~macos.PermissionDeniedError`:

```python
if not macos.screen.has_permission():
    macos.screen.request_permission()   # shows the system prompt
```

If a capture without other apps' windows is fine, pass
`check_permission=False` to skip the check. See
[Permissions](permissions.md#screen-recording).

## Finding text on the screen

{func}`~macos.screen.find_text` reads the screen with Vision's text recognition
and returns where some text is, ignoring case, top to bottom. It works in any
app, even on text drawn in images. Each {class}`~macos.screen.TextMatch`
surrounds the matching characters, in points like {func}`macos.mouse.click`
takes, and its `center` is where to click:

```python
match = macos.screen.find_text("Submit")[0]
macos.mouse.click(*match.center)

macos.mouse.click_text("Submit")                    # the same, in one call
macos.screen.wait_for_text("Export complete", timeout=120)
```

{func}`~macos.screen.wait_for_text` looks again every `interval` seconds (0.5
by default) until the text shows up. `region` or `display` limit where to look;
by default, the main display. A search of a whole display takes a second or two.

{func}`~macos.screen.color_at` reads the color of one point, as `'#rrggbb'`:

```python
macos.screen.color_at(100, 200)   # '#34c759'
```

These need the [Screen Recording permission](permissions.md#screen-recording).

## Displays

{func}`~macos.screen.displays` lists the connected displays, the main one (with
the menu bar) first:

```python
for display in macos.screen.displays():
    print(display.name, display.width, display.height, display.scale)
```

```text
Built-in Retina Display 1512 982 2.0
```

Each {class}`~macos.screen.Display` has its size and position in points (the
unit `region` uses), its physical resolution (`pixel_width`, `pixel_height`),
the `scale` (2.0 on Retina displays), the `refresh_rate`, and whether it
`is_main` or `is_builtin`.

## Recording the screen

{func}`~macos.screen.record` records the screen into a `.mov` video, and returns
when the recording ends:

```python
macos.screen.record("demo.mov", 10)                           # 10 seconds
macos.screen.record("part.mov", 5, region=(0, 0, 1280, 800))  # a region
macos.screen.record("talk.mov", 60, audio=True, clicks=True)  # with the microphone and clicks
```

`region` and `display` work as for screenshots. `audio=True` also records the
default microphone, and `clicks=True` shows mouse clicks. It needs the Screen
Recording permission, like screenshots. To make it smaller or an `.mp4`, see
{func}`macos.video.convert`.

## Wallpaper

```python
macos.screen.wallpaper()   # PosixPath('/System/Library/Desktop Pictures/...')
macos.screen.set_wallpaper("mountains.jpg")                         # on every display
macos.screen.set_wallpaper("mountains.jpg", display_id=display.id)  # only one
```

`display_id` is a {class}`~macos.screen.Display` from
{func}`~macos.screen.displays`, or its `id`. It's not the same as
{func}`~macos.screenshot`'s `display`, which counts displays from 1.
{func}`~macos.screen.wallpaper` returns `None` when the desktop isn't showing a
picture file, such as a solid color. macOS keeps using the file you pass to
{func}`~macos.screen.set_wallpaper`, so don't delete it afterwards.

## Brightness

```python
macos.screen.brightness()          # 0.75, from 0.0 to 1.0
macos.screen.set_brightness(0.4)
```

It works on the built-in display and on Apple displays, like the slider in
Control Center. Most external monitors set their brightness with their own
buttons, so they raise {class}`~macos.NotSupportedError`. `display_id` picks a
display, as for the wallpaper.

With *Automatically adjust brightness* on (System Settings › Displays), macOS
keeps adapting it to the room's light afterwards. It uses a private macOS
framework, since there's no public one.

## Night Shift

```python
macos.screen.night_shift()          # False
macos.screen.set_night_shift(True)  # warmer colors now
```

{func}`~macos.screen.night_shift` tells whether it's on right now, turned on
by hand or by its schedule. {func}`~macos.screen.set_night_shift` works like
the switch in Control Center: a schedule set in System Settings › Displays ›
Night Shift still applies afterwards. It uses a private macOS framework,
since there's no public one.

## True Tone

```python
macos.screen.true_tone()           # True
macos.screen.set_true_tone(False)  # exact colors, for photo editing
```

True Tone adapts the display's colors to the room's light. Macs whose
displays don't have it raise {class}`~macos.NotSupportedError`. It uses a
private macOS framework, like Night Shift.

## Locking

```python
macos.screen.lock()
```

It locks the screen at once, like Ctrl-Cmd-Q: apps keep running, and the
user needs their password or Touch ID to come back. It uses a private macOS
framework, since there's no public one.

{func}`~macos.screen.is_locked` tells whether the screen is locked, and
{func}`~macos.screen.is_asleep` whether a display is off to save energy, so a
script can wait for the user to come back:

```python
import time

while macos.screen.is_locked():
    time.sleep(5)
```

## Screen saver

```python
macos.screen.start_screensaver()
```

It starts the screen saver right away, like a hot corner. When the Mac asks
for the password after the screen saver begins (System Settings › Lock Screen),
this also locks it.

## Reference

- {func}`macos.screenshot`
- {func}`macos.screen.has_permission`
- {func}`macos.screen.request_permission`
- {func}`macos.screen.displays`
- {class}`macos.screen.Display`
- {func}`macos.screen.wallpaper`
- {func}`macos.screen.set_wallpaper`
- {func}`macos.screen.record`
- {func}`macos.screen.start_screensaver`
- {func}`macos.screen.brightness`
- {func}`macos.screen.set_brightness`
- {func}`macos.screen.night_shift`
- {func}`macos.screen.set_night_shift`
- {func}`macos.screen.true_tone`
- {func}`macos.screen.set_true_tone`
- {func}`macos.screen.lock`
- {func}`macos.screen.is_locked`
- {func}`macos.screen.is_asleep`
- {func}`macos.screen.find_text`
- {func}`macos.screen.wait_for_text`
- {func}`macos.screen.color_at`
- {class}`macos.screen.TextMatch`
