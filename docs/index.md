# pymacos

**A Pythonic interface to macOS.** Notifications, clipboard, keyboard and
mouse, windows, global hotkeys, dark mode, apps, Keychain, speech, screenshots,
battery, volume, Shortcuts, Finder, Spotlight, dialogs, system info, OCR,
document scanning, background removal, duplicate photos, images, PDFs, videos,
music control, audio devices, Bluetooth, brightness and language tools, all
from one import with zero dependencies.

<table class="badge-table">
  <tr>
    <th>docs</th>
    <td>
      <a href="https://macos.readthedocs.io/?badge=latest"><img alt="Documentation Status" src="https://readthedocs.org/projects/macos/badge/?version=latest"></a>
    </td>
  </tr>
  <tr>
    <th>tests</th>
    <td>
      <a href="https://github.com/JeanExtreme002/pymacos/actions/workflows/python-package.yml"><img alt="GitHub Actions build status" src="https://github.com/JeanExtreme002/pymacos/actions/workflows/python-package.yml/badge.svg"></a>
      <a href="https://app.codecov.io/gh/JeanExtreme002/pymacos"><img alt="Code coverage" src="https://codecov.io/gh/JeanExtreme002/pymacos/branch/main/graph/badge.svg"></a>
    </td>
  </tr>
  <tr>
    <th>package</th>
    <td>
      <a href="https://pypi.org/project/pymacos/"><img alt="Newest PyPI version" src="https://img.shields.io/pypi/v/pymacos.svg"></a>
      <a href="https://pypi.org/project/pymacos/"><img alt="Supported Python versions" src="https://img.shields.io/pypi/pyversions/pymacos.svg?color=8A2BE2"></a>
      <a href="https://pypi.org/project/pymacos/"><img alt="Platform" src="https://img.shields.io/badge/platform-macOS-lightgrey.svg"></a>
      <a href="https://pypi.org/project/pymacos/"><img alt="Typed" src="https://img.shields.io/pypi/types/pymacos.svg"></a>
      <a href="https://github.com/JeanExtreme002/pymacos/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/pymacos.svg"></a>
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

New here? Read [Why pymacos?](why.md), then start with
[Installation](installation.md) and the [Quick Start](quickstart.md).

```{toctree}
:caption: Getting Started
:hidden:

why
installation
quickstart
permissions
```

```{toctree}
:caption: Apps & Automation
:hidden:

apps
clipboard
hotkeys
keyboard
mouse
music
shortcuts
windows
```

```{toctree}
:caption: User Interaction
:hidden:

dialog
notifications
sound
speech
```

```{toctree}
:caption: Files & Documents
:hidden:

finder
image
pdf
spotlight
video
```

```{toctree}
:caption: Intelligence
:hidden:

language
vision
```

```{toctree}
:caption: Security
:hidden:

keychain
```

```{toctree}
:caption: System & Hardware
:hidden:

appearance
audio
bluetooth
network
power
screen
system
volume
```

```{toctree}
:caption: API Reference
:hidden:

api
errors
```

```{toctree}
:caption: Project
:hidden:

contributing
license
GitHub <https://github.com/JeanExtreme002/pymacos>
PyPI <https://pypi.org/project/pymacos/>
```
