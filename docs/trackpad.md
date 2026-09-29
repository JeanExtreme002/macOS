# Trackpad

{mod}`macos.trackpad` changes the trackpad settings of System Settings ›
Trackpad: tap to click, the scroll direction and the pointer speed.

```python
import macos

macos.trackpad.set_tap_to_click(True)
macos.trackpad.set_natural_scrolling(False)   # the classic direction
macos.trackpad.set_tracking_speed(0.7)        # from 0.0 to 1.0
```

## Settings

| Read | Change | Values |
|---|---|---|
| {func}`~macos.trackpad.tap_to_click` | {func}`~macos.trackpad.set_tap_to_click` | `True` clicks with a tap, without pressing |
| {func}`~macos.trackpad.natural_scrolling` | {func}`~macos.trackpad.set_natural_scrolling` | `True` moves the content with the fingers; mice follow it too |
| {func}`~macos.trackpad.secondary_click` | {func}`~macos.trackpad.set_secondary_click` | `"two_fingers"`, `"bottom_right"`, `"bottom_left"` (a corner) or `None` |
| {func}`~macos.trackpad.three_finger_drag` | {func}`~macos.trackpad.set_three_finger_drag` | drag windows and text with three fingers, without pressing |
| {func}`~macos.trackpad.tracking_speed` | {func}`~macos.trackpad.set_tracking_speed` | 0.0 (slowest) to 1.0 (fastest), like the slider |

Tap to click and the scroll direction apply at once; the pointer speed at the
next login. Three-finger dragging clashes with the three-finger swipes: set
those to four fingers in System Settings › Trackpad › More Gestures. They cover the built-in trackpad and a Magic Trackpad alike. No
permission is needed. For a mouse's speed, see
{func}`macos.mouse.set_tracking_speed`.

## Reference

- {func}`macos.trackpad.tap_to_click`
- {func}`macos.trackpad.set_tap_to_click`
- {func}`macos.trackpad.natural_scrolling`
- {func}`macos.trackpad.set_natural_scrolling`
- {func}`macos.trackpad.tracking_speed`
- {func}`macos.trackpad.set_tracking_speed`
- {func}`macos.trackpad.three_finger_drag`
- {func}`macos.trackpad.set_three_finger_drag`
- {func}`macos.trackpad.secondary_click`
- {func}`macos.trackpad.set_secondary_click`
