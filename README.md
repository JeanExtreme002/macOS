# pymacos

**A Pythonic interface to macOS.** Notifications, clipboard, keyboard and mouse, dark mode, apps, Keychain, speech, screenshots, battery, volume, Shortcuts, Finder, Spotlight, dialogs, system info, OCR, document scanning, background removal, duplicate photos, images, PDFs, audio devices, Bluetooth, brightness and language tools, all from one import with zero dependencies.

<table>
    <tr>
        <th>docs</th>
        <td>
            <a href="https://macos.readthedocs.io/?badge=latest"><img
                alt="Documentation Status"
                src="https://readthedocs.org/projects/macos/badge/?version=latest"></a>
        </td>
    </tr>
    <tr>
        <th>tests</th>
        <td>
            <a href="https://github.com/JeanExtreme002/pymacos/actions/workflows/python-package.yml"><img
                alt="GitHub Actions build status (lint, tests on macOS and Linux, docs)"
                src="https://github.com/JeanExtreme002/pymacos/actions/workflows/python-package.yml/badge.svg"></a>
            <a href="https://app.codecov.io/gh/JeanExtreme002/pymacos"><img
                alt="Code coverage"
                src="https://codecov.io/gh/JeanExtreme002/pymacos/branch/main/graph/badge.svg"></a>
        </td>
    </tr>
    <tr>
        <th>package</th>
        <td>
            <a href="https://pypi.org/project/pymacos/"><img
                alt="Newest PyPI version"
                src="https://img.shields.io/pypi/v/pymacos.svg"></a>
            <a href="https://pypi.org/project/pymacos/"><img
                alt="Supported Python versions"
                src="https://img.shields.io/pypi/pyversions/pymacos.svg?color=8A2BE2"></a>
            <a href="https://pypi.org/project/pymacos/"><img
                alt="Platform"
                src="https://img.shields.io/badge/platform-macOS-lightgrey.svg"></a>
            <a href="https://pypi.org/project/pymacos/"><img
                alt="Typed"
                src="https://img.shields.io/pypi/types/pymacos.svg"></a>
            <a href="https://github.com/JeanExtreme002/pymacos/blob/main/LICENSE"><img
                alt="License"
                src="https://img.shields.io/pypi/l/pymacos.svg"></a>
        </td>
    </tr>
</table>

```python
import macos

macos.notify("Build finished", title="CI")
macos.say("Done!")

macos.clipboard.copy("hello")
macos.appearance.is_dark()                      # True
macos.screenshot("screen.png")

macos.apps.open("Safari")                       # App(name='Safari', ...)
macos.keychain.get("my-app", "alice")           # 's3cret'

macos.power.battery()                           # Battery(percent=87, charging=True, ...)
macos.shortcuts.run("Translate", input="Olá")   # 'Hello'
macos.finder.trash("old.log")                   # moved to the Trash
```

## Install

```bash
pip install pymacos
```

The package is installed as `pymacos` and imported as `macos`.

Requires macOS and Python 3.9+.

## Why

A notification from plain Python means AppleScript inside a string, which breaks as soon as the message contains a quote:

```python
subprocess.run(["osascript", "-e", 'display notification "Build finished" with title "CI"'])
```

With pymacos:

```python
macos.notify("Build finished", title="CI")
```

Across the whole package:

- No dependencies: no PyObjC, nothing to compile.
- Plain, typed functions that return Python objects.
- Any text is safe: nothing is pasted into shell or AppleScript source.
- Clear errors when macOS is missing a permission, instead of silent failures.

See [Why pymacos?](https://macos.readthedocs.io/en/latest/why.html) for a longer comparison.

## Documentation

The full guide and API reference are at **[macos.readthedocs.io](https://macos.readthedocs.io)**.

## License

Released under the [MIT License](https://github.com/JeanExtreme002/pymacos/blob/main/LICENSE) — free for personal and commercial use.

<sub>Not affiliated with or endorsed by Apple Inc. macOS is a trademark of Apple Inc.</sub>
