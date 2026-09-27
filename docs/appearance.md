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

## Reference

- {func}`macos.appearance.is_dark`
- {func}`macos.appearance.mode`
- {func}`macos.appearance.is_auto`
