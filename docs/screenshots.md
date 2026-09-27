# Screenshots

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

## Options

```python
macos.screenshot("area.png", region=(0, 0, 800, 600))   # x, y, width, height
macos.screenshot("second.png", display=2)                # another display
macos.screenshot("pointer.png", cursor=True)             # include the mouse pointer
```

- `region` is in points, measured from the top-left corner of the main display.
- `display` counts from `1`, the main display.

The format follows the file extension: `.png`, `.jpg` (or `.jpeg`), `.heic`,
`.tiff`, `.gif` or `.pdf`. Anything else raises `ValueError`.

## Permission

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

## Reference

- {func}`macos.screenshot`
- {func}`macos.screen.has_permission`
- {func}`macos.screen.request_permission`
