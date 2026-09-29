# Defaults

{mod}`macos.defaults` reads and changes the preferences of apps and of the
system, like the `defaults` command, but with Python values: no `-bool` or
`-int` flags to get right.

```python
import macos

macos.defaults.read("com.apple.dock", "autohide")             # True
macos.defaults.write("com.apple.dock", "autohide", True)
macos.defaults.read("NSGlobalDomain", "AppleInterfaceStyle")  # 'Dark'
macos.defaults.delete("com.example.app", "cache-size")
```

A domain is an app's bundle identifier (`"com.apple.finder"`), or
{data}`~macos.defaults.GLOBAL` (`"NSGlobalDomain"`, also spelled `"-g"`) for the
preferences every app shares. No permission is needed.

## Reading

{func}`~macos.defaults.read` returns the value, with its type: `bool`, `int`,
`float`, `str`, `bytes`, {class}`~datetime.datetime`, or lists and dicts of them.
A key that isn't set returns `default` (`None` unless given). Without a key, it
returns the whole domain as a dict, and {func}`~macos.defaults.keys` lists its
keys:

```python
macos.defaults.read("com.apple.screencapture", "type", default="png")
macos.defaults.keys("com.apple.dock")   # ['autohide', 'orientation', 'persistent-apps', ...]
```

## Writing

{func}`~macos.defaults.write` stores the value with its Python type, so `True`
is a boolean and `[1, 2]` an array, and {func}`~macos.defaults.delete` removes
a key:

```python
macos.defaults.write("com.apple.finder", "ShowPathbar", True)
macos.defaults.write("com.example.tool", "servers", ["a.example.com", "b.example.com"])
```

The change reaches the system at once, but most apps only read their
preferences when they start: restart the app to see it. For the Dock, the
Finder and the screenshots, see [Dock](dock.md), [Finder](finder.md) and
[Screen](screen.md), which restart what's needed.

## This Mac only

A few settings are kept per Mac, such as the screen saver's delay:
`defaults -currentHost` reads them. Pass `current_host=True` to any of the
functions for the same:

```python
macos.defaults.read("com.apple.screensaver", "idleTime", current_host=True)   # 1200
```

## Changing settings for a while

{func}`~macos.defaults.restored` puts preferences back exactly as they were
when its block ends, even if it fails; keys that weren't set are deleted
again:

```python
with macos.defaults.restored(("com.apple.finder", "CreateDesktop")):
    macos.finder.set_show_desktop_icons(False)   # a clean desktop for a recording
    record_demo()
# the icons are back
```

Name `(domain, key)` pairs, or a whole domain such as `"com.apple.dock"`.

## Reference

- {func}`macos.defaults.read`
- {func}`macos.defaults.write`
- {func}`macos.defaults.delete`
- {func}`macos.defaults.keys`
- {data}`macos.defaults.GLOBAL`
- {func}`macos.defaults.restored`
