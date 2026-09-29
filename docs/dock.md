# Dock

{mod}`macos.dock` configures the Dock: hide it, size it, move it, and choose
the apps kept in it. Handy to set up a new Mac from a script.

```python
import macos

macos.dock.set_autohide(True)
macos.dock.set_size(48)            # icons of 48 points
macos.dock.set_position("left")
macos.dock.add_app("Visual Studio Code")
macos.dock.remove_app("Podcasts")
```

Each change restarts the Dock to apply it: it disappears for a second. No
permission is needed.

## Settings

| Read | Change | Values |
|---|---|---|
| {func}`~macos.dock.autohide` | {func}`~macos.dock.set_autohide` | `True` hides it until the pointer reaches the edge |
| {func}`~macos.dock.size` | {func}`~macos.dock.set_size` | 16 to 128 points, like the Size slider |
| {func}`~macos.dock.position` | {func}`~macos.dock.set_position` | `"left"`, `"bottom"` or `"right"` |
| {func}`~macos.dock.autohide_delay` | {func}`~macos.dock.set_autohide_delay` | seconds a hidden Dock waits to show; `0` shows it at once |
| {func}`~macos.dock.magnification` | {func}`~macos.dock.set_magnification` | the size icons grow to under the pointer, or `None` |
| {func}`~macos.dock.show_recents` | {func}`~macos.dock.set_show_recents` | recent apps in their own section |
| {func}`~macos.dock.minimize_effect` | {func}`~macos.dock.set_minimize_effect` | `"genie"` or `"scale"` |

## Hot corners

{func}`~macos.dock.set_hot_corner` makes moving the pointer into a corner of
the screen do something, like System Settings › Desktop & Dock › Hot Corners:

```python
macos.dock.set_hot_corner("bottom_right", "lock_screen")
macos.dock.set_hot_corner("top_left", None)   # nothing
macos.dock.hot_corners()   # {'top_left': None, 'top_right': 'notification_center', ...}
```

The corners are `"top_left"`, `"top_right"`, `"bottom_left"` and
`"bottom_right"`; the actions, in {data}`~macos.dock.HOT_CORNER_ACTIONS`:
`"mission_control"`, `"app_windows"`, `"desktop"`, `"notification_center"`,
`"launchpad"`, `"quick_note"`, `"start_screensaver"`, `"disable_screensaver"`,
`"display_sleep"` and `"lock_screen"`.

## Apps in the Dock

{func}`~macos.dock.apps` lists the apps kept in the Dock, in order, as
{class}`~macos.dock.DockApp` objects with their `name`, `path` and `bundle_id`.
Finder, always first, isn't listed, nor are the running apps that aren't kept.

```python
[app.name for app in macos.dock.apps()]   # ['Safari', 'Mail', 'Music', ...]

macos.dock.add_app("Terminal", index=0)   # first, right after Finder
macos.dock.remove_app("com.apple.Maps")   # by name, bundle ID or path
```

{func}`~macos.dock.add_app` finds the app as {func}`macos.apps.open` does, and
doesn't add it twice. {func}`~macos.dock.remove_app` takes it out of the Dock;
the app stays installed.

## Reference

- {func}`macos.dock.autohide`
- {func}`macos.dock.set_autohide`
- {func}`macos.dock.size`
- {func}`macos.dock.set_size`
- {func}`macos.dock.position`
- {func}`macos.dock.set_position`
- {func}`macos.dock.apps`
- {func}`macos.dock.add_app`
- {func}`macos.dock.remove_app`
- {func}`macos.dock.restart`
- {class}`macos.dock.DockApp`
- {data}`macos.dock.HOT_CORNER_ACTIONS`
- {func}`macos.dock.hot_corners`
- {func}`macos.dock.set_hot_corner`
- {func}`macos.dock.autohide_delay`
- {func}`macos.dock.set_autohide_delay`
- {func}`macos.dock.magnification`
- {func}`macos.dock.set_magnification`
- {func}`macos.dock.show_recents`
- {func}`macos.dock.set_show_recents`
- {func}`macos.dock.minimize_effect`
- {func}`macos.dock.set_minimize_effect`
