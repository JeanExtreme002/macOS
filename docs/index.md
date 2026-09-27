# pymacos

**A Pythonic interface to macOS.** Notifications, clipboard, dark mode, apps,
Keychain, speech, screenshots, battery, Shortcuts and Finder, all from one
import with zero dependencies.

```python
import macos

macos.notify("Build finished", title="CI")
macos.clipboard.copy("hello")
macos.appearance.is_dark()                 # True
macos.apps.open("Safari")                  # App(name='Safari', ...)
macos.keychain.get("my-app", "alice")      # 's3cret'
macos.say("Done!")
macos.screenshot("screen.png")
macos.power.battery()                      # Battery(percent=87, charging=True, ...)
macos.shortcuts.run("Translate", input="Olá")
macos.finder.trash("old.log")
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
:caption: Features
:hidden:

notifications
clipboard
appearance
apps
keychain
speech
screenshots
power
shortcuts
finder
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
