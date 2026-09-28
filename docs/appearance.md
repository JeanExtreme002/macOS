# Appearance

{mod}`macos.appearance` tells you whether the system is in Light or Dark mode,
and which accent color the user picked.

```python
import macos

macos.appearance.is_dark()        # True
macos.appearance.mode()           # 'dark' or 'light'
macos.appearance.is_auto()        # True if set to Auto
macos.appearance.accent_color()   # '#007aff'
```

The value is read fresh on every call, so a long-running program sees the user
switching modes, or *Auto* switching at sunset, without restarting.

## Matching your output to the system theme

```python
import matplotlib.pyplot as plt
import macos

plt.style.use("dark_background" if macos.appearance.is_dark() else "default")
```

## Accent color

{func}`~macos.appearance.accent_color` returns the accent color chosen in
System Settings › Appearance, as a hex string. It's the color of buttons,
checkboxes and selections, so a web view or a plot can use it to look at home:

```python
accent = macos.appearance.accent_color()   # '#007aff'
plt.plot(x, y, color=accent)
```

With *Multicolor* selected, it returns the default blue.

## Waiting for a switch

{func}`~macos.appearance.wait_for_change` blocks until the system switches
between Light and Dark mode, and returns the new mode:

```python
while True:
    theme = macos.appearance.wait_for_change()   # 'dark' or 'light'
    restyle(theme)
```

With `timeout`, it raises `TimeoutError` if nothing changes in time.

## Reference

- {func}`macos.appearance.is_dark`
- {func}`macos.appearance.mode`
- {func}`macos.appearance.is_auto`
- {func}`macos.appearance.accent_color`
- {func}`macos.appearance.wait_for_change`
