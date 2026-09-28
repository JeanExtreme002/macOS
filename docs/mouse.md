# Mouse

{mod}`macos.mouse` reads where the pointer is, moves it, clicks, drags and
scrolls.

```python
import macos

macos.mouse.position()                     # (512.0, 384.0)
macos.mouse.move(100, 200)
macos.mouse.click()                        # where the pointer is
macos.mouse.click(300, 400, button="right")
macos.mouse.scroll(5)                      # 5 lines down
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
(the default), `"right"` or `"middle"`.

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

## Reference

- {func}`macos.mouse.position`
- {func}`macos.mouse.move`
- {func}`macos.mouse.click`
- {func}`macos.mouse.drag`
- {func}`macos.mouse.scroll`
- {func}`macos.mouse.has_permission`
- {func}`macos.mouse.request_permission`
