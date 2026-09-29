# Mouse

{mod}`macos.mouse` reads where the pointer is, moves it, clicks, drags and
scrolls.

```python
import macos

macos.mouse.position()                       # (512.0, 384.0)
macos.mouse.move(100, 200)

macos.mouse.click()                          # where the pointer is
macos.mouse.click(300, 400, button="right")

macos.mouse.scroll(5)                        # 5 lines down
```

Positions are in points from the top-left corner of the main display, the
same as {func}`macos.screenshot`'s `region` and {class}`macos.screen.Display`.
Reading the position needs no permission; everything else needs the
[Accessibility permission](permissions.md#accessibility).

## Moving and clicking

```python
macos.mouse.move(800, 600, duration=0.5)   # glide there in half a second
macos.mouse.click(button="middle")
macos.mouse.click(400, 300, count=2)       # double-click
```

Apps see a real mouse: hover effects and tooltips react. `button` is `"left"`
(the default), `"right"` or `"middle"`. For a Shift-click or a Cmd-click, hold
the key with {func}`macos.keyboard.hold`:

```python
with macos.keyboard.hold("cmd"):
    macos.mouse.click(200, 300)
```

## Clicking on text

{func}`~macos.mouse.click_text` finds some text on the screen and clicks its
middle, so a script doesn't depend on where a button is:

```python
macos.mouse.click_text("Accept")
macos.mouse.click_text("Download", timeout=30)   # wait for it to show up first
```

It raises {class}`~macos.MacOSError` when the text isn't on the screen. It needs
the [Screen Recording permission](permissions.md#screen-recording) too. See
{func}`macos.screen.find_text` for how the text is found.

## Dragging

{func}`~macos.mouse.drag` holds a button from where the pointer is to another
point, to move windows, select text or drop files:

```python
macos.mouse.move(100, 100)
macos.mouse.drag(500, 100, duration=0.5)
```

The button is always released at the end, even if the drag is interrupted.

## Scrolling

{func}`~macos.mouse.scroll` scrolls what is under the pointer by a number of
lines. Positive values scroll down, towards the end, and negative values up;
`horizontal=True` scrolls right (positive) or left (negative):

```python
macos.mouse.scroll(10)
macos.mouse.scroll(-3, horizontal=True)
```

## Watching clicks

{func}`~macos.mouse.watch` yields a {class}`~macos.mouse.Click` each time a mouse
button goes down, in any app, with where, which button, and whether it's a
double-click:

```python
for click in macos.mouse.watch():
    print(click.x, click.y, click.button, click.count)
```

It only listens: the clicks still reach the apps. It needs the [Input Monitoring
permission](permissions.md#input-monitoring).

## Pointer speed

{func}`~macos.mouse.set_tracking_speed` sets how fast the pointer moves with a
mouse, from 0.0 to 1.0, like the slider in System Settings › Mouse; it takes
effect at the next login. For the trackpad, see [Trackpad](trackpad.md).

```python
macos.mouse.tracking_speed()        # 0.333
macos.mouse.set_tracking_speed(0.8)
```

## Reference

- {func}`macos.mouse.position`
- {func}`macos.mouse.move`
- {func}`macos.mouse.click`
- {func}`macos.mouse.drag`
- {func}`macos.mouse.scroll`
- {func}`macos.mouse.has_permission`
- {func}`macos.mouse.request_permission`
- {func}`macos.mouse.click_text`
- {func}`macos.mouse.watch`
- {class}`macos.mouse.Click`
- {func}`macos.mouse.tracking_speed`
- {func}`macos.mouse.set_tracking_speed`
