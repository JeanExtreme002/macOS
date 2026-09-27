# MacOS

**A Pythonic interface to macOS.** Notifications, clipboard, dark mode, apps, keychain, speech and screenshots, all from one import with **zero dependencies**.

```python
import macos

macos.notify("Build finished", title="CI", sound="Glass")
macos.clipboard.copy("hello")
macos.appearance.is_dark()                 # True
macos.apps.running()                       # [App(name='Finder', ...), ...]
macos.keychain.get("my-app", "alice")      # 's3cret'
macos.say("Done!")
macos.screenshot("screen.png")
```

## Why

Doing any of this from Python today means shelling out to `osascript`, remembering `defaults` keys, or pulling in PyObjC and learning Cocoa. `macos` gives you one small, typed, documented API instead:

- **No dependencies.** Native features call the system frameworks through `ctypes`; the rest wraps tools that ship with every Mac.
- **Pythonic.** Plain functions, dataclasses and real exceptions, not Objective-C selectors or exit codes.
- **Safe by default.** User text is never spliced into shell or AppleScript source, and secrets never touch the process list.
- **Helpful errors.** A missing privacy permission raises `PermissionDeniedError` that tells you where to enable it, instead of quietly failing.

## Install

```bash
pip install macos
```

Requires macOS and Python 3.9+.

## Usage

### Notifications

```python
macos.notify("3 tests failed", title="CI", subtitle="main", sound="Basso")
```

### Clipboard

```python
macos.clipboard.copy("olá 🍎")
macos.clipboard.paste()          # 'olá 🍎' (None if the clipboard holds no text)
macos.clipboard.clear()
macos.clipboard.change_count()   # increases on every change, handy for polling
```

### Appearance

```python
macos.appearance.is_dark()   # True / False
macos.appearance.mode()      # 'dark' or 'light'
macos.appearance.is_auto()   # following the time of day?
```

### Apps

```python
for app in macos.apps.running():             # apps with a Dock icon
    print(app.name, app.bundle_id, app.pid)

macos.apps.running(include_background=True)  # plus agents and menu-bar extras
macos.apps.frontmost()

safari = macos.apps.open("Safari")           # name, bundle id or path
safari.activate()
safari.hide()
safari.quit(timeout=5)                       # wait up to 5s; force=True to force quit
```

### Keychain

```python
macos.keychain.set("my-app", "alice", "s3cret")
macos.keychain.get("my-app", "alice")        # 's3cret' (None if missing)
macos.keychain.delete("my-app", "alice")
```

### Speech

```python
macos.say("Hello from Python")
macos.say("Olá!", voice="Luciana", rate=180, wait=False)
macos.speech.voices()                        # [Voice(name='Albert', locale='en_US', ...), ...]
```

### Screenshots

```python
path = macos.screenshot()                              # temporary PNG
macos.screenshot("area.jpg", region=(0, 0, 800, 600))  # x, y, width, height
macos.screenshot("second.png", display=2, cursor=True)
```

## Permissions

macOS asks for some permissions on behalf of the app running Python (your terminal or IDE), not Python itself:

| Feature | Permission | Where |
|---|---|---|
| `screenshot` | Screen Recording | System Settings › Privacy & Security › Screen & System Audio Recording |
| `notify` | Notifications for *Script Editor* | System Settings › Notifications |

`macos.screen.has_permission()` checks the screenshot permission without prompting; `macos.screen.request_permission()` shows the system prompt.

## Errors

Everything the package raises derives from `macos.MacOSError`:

| Exception | When |
|---|---|
| `NotSupportedError` | Not running on macOS, or a required system tool is missing |
| `PermissionDeniedError` | A privacy permission is missing (also a `PermissionError`) |
| `AppNotFoundError` | No app matches the name (also a `LookupError`) |
| `KeychainError` | The Security framework returned an error status |
| `CommandError` | A system command failed; carries `returncode` and `stderr` |

The package imports on any OS, so it's safe in cross-platform code; the functions raise `NotSupportedError` outside macOS.

## Contributing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest              # unit tests + live tests against your Mac
pytest -m "not live"  # unit tests only
```

The live tests restore your clipboard and delete the Keychain items they create.

## License

[MIT](LICENSE)

---

<sub>Not affiliated with or endorsed by Apple Inc. macOS is a trademark of Apple Inc.</sub>
