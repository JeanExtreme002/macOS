# Permissions

macOS protects some features behind privacy permissions. They are granted to
the **app running Python** (Terminal, iTerm, VS Code, PyCharm...), not to Python
itself, so a script can work in one terminal and not in another.

| Feature | Permission | Where to enable it |
|---|---|---|
| {func}`macos.screenshot` | Screen Recording | System Settings › Privacy & Security › Screen & System Audio Recording |
| {func}`macos.notify` | Notifications for *Script Editor* | System Settings › Notifications › Script Editor |

The other features (clipboard, appearance, apps, Keychain, speech) need no
permission.

## Screen Recording

Without this permission macOS doesn't fail: it returns a screenshot that shows
only the wallpaper and the menu bar. `macos` checks first and raises
{class}`~macos.PermissionDeniedError` instead.

```python
macos.screen.has_permission()       # check without prompting
macos.screen.request_permission()   # show the system prompt
```

After granting it in System Settings, **restart the app running Python**; macOS
only applies the change to newly started processes.

## Notifications

Notifications are posted through AppleScript, so macOS attributes them to *Script Editor*.

If {func}`macos.notify` runs without errors but nothing shows
up, notifications for Script Editor are turned off. If Script Editor isn't
listed in System Settings › Notifications yet, open Script Editor, run
`display notification "hi"` once and accept the prompt.

Also check that a Focus mode (such as Do Not Disturb) isn't hiding them.

## Keychain

Reading an item that another app created may make macOS ask the user to allow
access. If the user denies it, {mod}`macos.keychain` raises
{class}`~macos.PermissionDeniedError`. Items created by your script can be read
back by it without a prompt.
