# Permissions

macOS protects some features behind privacy permissions. They are granted to
the **app running Python** (Terminal, iTerm, VS Code, PyCharm...), not to Python
itself, so a script can work in one terminal and not in another.

| Feature | Permission | Where to enable it |
|---|---|---|
| {func}`macos.screenshot` | Screen Recording | System Settings › Privacy & Security › Screen & System Audio Recording |
| {func}`macos.notify` | Notifications for *Script Editor* | System Settings › Notifications › Script Editor |
| {mod}`macos.keyboard` typing and keys, {mod}`macos.mouse` moving, clicking and scrolling | Accessibility | System Settings › Privacy & Security › Accessibility |
| {func}`macos.bluetooth.connect`, {func}`~macos.bluetooth.disconnect` | Bluetooth (asked the first time) | System Settings › Privacy & Security › Bluetooth |

The other features (clipboard, appearance, apps, Keychain, speech, power,
Shortcuts, Finder, volume, Spotlight, dialogs, system info, Vision, images,
PDFs, language, audio devices, sounds, network, brightness, the keyboard
backlight, the mouse position, listing Bluetooth devices) need no permission.

## Screen Recording

Without this permission macOS doesn't fail: it returns a screenshot that shows
only the wallpaper and the menu bar. `pymacos` checks first and raises
{class}`~macos.PermissionDeniedError` instead.

```python
macos.screen.has_permission()       # check without prompting
macos.screen.request_permission()   # show the system prompt
```

After granting it in System Settings, **restart the app running Python**; macOS
only applies the change to newly started processes.

## Accessibility

Sending keystrokes and mouse events lets a script control any app, so macOS
asks for the Accessibility permission. Without it macOS silently drops the
events; {mod}`macos.keyboard` and {mod}`macos.mouse` check first and raise
{class}`~macos.PermissionDeniedError` instead.

```python
macos.keyboard.has_permission()       # check without prompting (the same for macos.mouse)
macos.keyboard.request_permission()   # show the system prompt
```

As with Screen Recording, **restart the app running Python** after allowing it.

## Notifications

Notifications are posted through AppleScript, so macOS attributes them to *Script Editor*.

When notifications for Script Editor are turned off, macOS drops them without
an error, so {func}`macos.notify` raises {class}`~macos.PermissionDeniedError`
instead. Turn them on in System Settings › Notifications › Script Editor. If
Script Editor isn't listed there yet, open Script Editor, run
`display notification "hi"` once and accept the prompt.

Also check that a Focus mode (such as Do Not Disturb) isn't hiding them.

## Keychain

Reading an item that another app created may make macOS ask the user to allow
access. If the user denies it, {mod}`macos.keychain` raises
{class}`~macos.PermissionDeniedError`. Items created by your script can be read
back by it without a prompt.
