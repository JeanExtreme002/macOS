# macos

**A Pythonic interface to macOS.** Notifications, clipboard, dark mode, apps,
Keychain, speech and screenshots, all from one import with zero dependencies.

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

Doing any of this from Python usually means shelling out to `osascript`,
remembering `defaults` keys, or pulling in PyObjC and learning Cocoa. `macos`
gives you one small, typed API instead:

- **No dependencies.** Native features call the system frameworks through
  `ctypes`; the rest wraps tools that ship with every Mac.
- **Pythonic.** Plain functions, dataclasses and real exceptions, not
  Objective-C selectors or exit codes.
- **Safe by default.** Your text is never spliced into shell or AppleScript
  source, and passwords never show up in the process list.
- **Helpful errors.** A missing privacy permission raises an error that says
  where to enable it, instead of failing silently.

Start with [Installation](installation.md) and the [Quick Start](quickstart.md),
then read the page for each feature.

```{admonition} Enjoying macos?
:class: tip

If it saved you a trip to the AppleScript docs, please
**[star it on GitHub](https://github.com/JeanExtreme002/macOS)**. It's the
easiest way to support the project and help others find it.
```

```{toctree}
:caption: Getting Started
:hidden:

installation
quickstart
permissions
```

```{toctree}
:caption: Features
:hidden:

notifications
clipboard
appearance
apps
keychain
speech
screenshots
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
GitHub <https://github.com/JeanExtreme002/macOS>
PyPI <https://pypi.org/project/macos/>
```
