# Appearance

{mod}`macos.appearance` tells you whether the system is in Light or Dark mode.

```python
import macos

macos.appearance.is_dark()   # True
macos.appearance.mode()      # 'dark' or 'light'
macos.appearance.is_auto()   # True if set to Auto
```

The value is read fresh on every call, so a long-running program sees the user
switching modes, or *Auto* switching at sunset, without restarting.

## Matching your output to the system theme

```python
import matplotlib.pyplot as plt
import macos

plt.style.use("dark_background" if macos.appearance.is_dark() else "default")
```

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
- {func}`macos.appearance.wait_for_change`
