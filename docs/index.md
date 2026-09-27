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

New here? Read [Why macos?](why.md), then start with
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
PyPI <https://pypi.org/project/pymacos/>
```
