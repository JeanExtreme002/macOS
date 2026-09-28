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
- {func}`macos.screen.start_screensaver`
