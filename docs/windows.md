# Windows

{mod}`macos.windows` lists the windows of the running apps, and moves,
resizes, focuses, minimizes and closes them, like window managers such as
Rectangle.

```python
import macos

for window in macos.windows.list("Safari"):
    print(window.title, window.frame)   # GitHub (0, 25, 1440, 875)

window = macos.windows.focused()       # the window in front
window.set_frame(0, 25, 1280, 800)
```

It needs the [Accessibility permission](permissions.md#accessibility), the same
one {mod}`macos.keyboard` and {mod}`macos.mouse` need.

## Finding windows

{func}`~macos.windows.list` returns the windows of every app, or of one app
given by name or as an {class}`~macos.apps.App`. `title` keeps the windows
whose title contains it:

```python
macos.windows.list()                              # every app's windows
macos.windows.list("Preview", title="invoice")    # Preview's invoice windows
```

{func}`~macos.windows.focused` returns the window keystrokes go to.

## Moving and resizing

Positions and sizes are in points from the top-left corner of the main
display, like {func}`macos.screenshot`'s `region`:

```python
window.move(0, 25)
window.resize(1280, 800)
window.set_frame(0, 25, 1280, 800)   # both at once

# Left half of the main display, like a tiling window manager:
display = macos.screen.displays()[0]
window.set_frame(display.x, display.y + 25, display.width // 2, display.height - 25)
```

{meth}`~macos.windows.Window.center` centers a window on the display it's on,
keeping its size:

```python
window.center()
```

Apps may refuse a size below their minimum and keep the closest one they
accept. {attr}`~macos.windows.Window.title`,
{attr}`~macos.windows.Window.frame` and the other attributes are read fresh
each time, so they follow the user moving the window.

## Focusing, minimizing and closing

```python
window.focus()      # to the front, with its app, ready for keystrokes
window.minimize()   # into the Dock
window.restore()
window.close()      # like its red button
```

{meth}`~macos.windows.Window.close` works like the red button: the app may ask
to save changes first.

## Full screen

```python
window.fullscreen             # False
window.set_fullscreen()       # like its green button
window.set_fullscreen(False)
```

macOS animates it into a Space of its own; {meth}`~macos.windows.Window.set_fullscreen`
returns once that's done, after a second or two.
Windows whose app doesn't allow full screen raise {class}`~macos.MacOSError`.

## Capturing a window

{meth}`Window.screenshot() <macos.windows.Window.screenshot>` captures just that
window, even when others cover it, without its shadow unless `shadow=True`:

```python
window = macos.windows.list("Safari")[0]
window.screenshot("safari.png")
```

It needs the [Screen Recording permission](permissions.md#screen-recording).

## Waiting for a window

{func}`~macos.windows.wait_for` waits until a window shows up, after an action
that opens one:

```python
macos.keyboard.press("cmd+s")
dialog = macos.windows.wait_for("TextEdit", title="Save", timeout=5)
```

## Reference

- {func}`macos.windows.list`
- {func}`macos.windows.focused`
- {class}`macos.windows.Window`
- {func}`macos.windows.has_permission`
- {func}`macos.windows.request_permission`
- {func}`macos.windows.wait_for`
