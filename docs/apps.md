# Apps

{mod}`macos.apps` lists, opens, activates and quits applications.

## Listing running apps

```python
import macos

for app in macos.apps.running():
    print(app.name, app.bundle_id, app.pid)
```

By default {func}`~macos.apps.running` returns regular apps, the ones with a
Dock icon. Pass `include_background=True` to also get menu-bar extras, agents
and helper processes:

```python
macos.apps.running(include_background=True)
```

{func}`~macos.apps.frontmost` returns the app that has keyboard focus:

```python
macos.apps.frontmost()   # App(name='Safari', bundle_id='com.apple.Safari', ...)
```

## Finding an app

{func}`~macos.apps.get` finds a running app, or returns `None` if it isn't
running. It accepts any of these:

```python
macos.apps.get("Safari")                          # displayed name
macos.apps.get("com.apple.Safari")                # bundle identifier
macos.apps.get("Safari.app")                      # bundle file name
macos.apps.get("/Applications/Safari.app")        # path (symlinks are fine)
```

Names are compared case-insensitively, against both the displayed name and the
bundle's file name. So `"Calculator"` also finds the app on a Mac set to
Portuguese, where it is displayed as "Calculadora".

## Opening an app

{func}`~macos.apps.open` launches an app, or brings it to the front if it's
already running, and returns it once it's up:

```python
safari = macos.apps.open("Safari")
macos.apps.open("com.apple.Safari")
macos.apps.open("/Applications/Safari.app")
macos.apps.open("Mail", background=True)   # launch without stealing focus
```

It raises {class}`~macos.AppNotFoundError` if no installed app matches, or if
the app doesn't show up within `timeout` seconds (10 by default).

## Controlling an app

{func}`~macos.apps.running`, {func}`~macos.apps.frontmost`,
{func}`~macos.apps.get` and {func}`~macos.apps.open` return
{class}`~macos.apps.App` objects:

```python
app = macos.apps.get("Safari")

app.name, app.bundle_id, app.pid, app.path

app.is_running    # still running?
app.is_active     # frontmost?
app.is_hidden

app.activate()    # bring to the front
app.hide()
app.unhide()
```

## Quitting an app

{meth}`App.quit() <macos.apps.App.quit>` asks the app to quit, like choosing
*Quit* from its menu. The app may show a "save changes?" dialog, or refuse.

```python
app.quit()                    # returns right away
app.quit(timeout=5)           # waits up to 5 s; returns whether it exited
app.quit(force=True)          # like Force Quit: unsaved work is lost
```

For example, a small focus mode:

```python
for name in ("Slack", "Discord", "Mail"):
    app = macos.apps.get(name)
    if app is not None:
        app.quit()
```

## Threads

All functions work from any thread, not only the main one.

## Reference

- {func}`macos.apps.running`
- {func}`macos.apps.frontmost`
- {func}`macos.apps.get`
- {func}`macos.apps.open`
- {class}`macos.apps.App`
