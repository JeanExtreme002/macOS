# pymacos

**A Pythonic interface to macOS.** Notifications, clipboard, dark mode, apps, Keychain, speech and screenshots, all from one import with zero dependencies.

```python
import macos

macos.notify("Build finished", title="CI")
macos.clipboard.copy("hello")
macos.appearance.is_dark()                 # True
macos.apps.open("Safari")                  # App(name='Safari', ...)
macos.keychain.get("my-app", "alice")      # 's3cret'
macos.say("Done!")
macos.screenshot("screen.png")
```

## Install

```bash
pip install pymacos
```

The package is installed as `pymacos` and imported as `macos`.

Requires macOS and Python 3.9+.

## Why

Doing any of this from Python usually means shelling out to `osascript`, remembering `defaults` keys, or pulling in PyObjC and learning Cocoa. `pymacos` gives you one small, typed API instead:

- **No dependencies.** Native features call the system frameworks through `ctypes`; the rest wraps tools that ship with every Mac.
- **Pythonic.** Plain functions, dataclasses and real exceptions, not Objective-C selectors or exit codes.
- **Safe by default.** Your text is never spliced into shell or AppleScript source, and passwords never show up in the process list.
- **Helpful errors.** A missing privacy permission raises an error that says where to enable it, instead of failing silently.

## Documentation

The full guide and API reference are at **[macos.readthedocs.io](https://macos.readthedocs.io)**.

## License

Released under the [MIT License](https://github.com/JeanExtreme002/pymacos/blob/main/LICENSE) — free for personal and commercial use.

<sub>Not affiliated with or endorsed by Apple Inc. macOS is a trademark of Apple Inc.</sub>
