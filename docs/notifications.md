# Notifications

Post a notification to Notification Center with {func}`macos.notify`:

```python
import macos

macos.notify("Build finished")
```

Add a title, a subtitle and a sound:

```python
macos.notify("3 tests failed", title="CI", subtitle="main", sound="Basso")
```

`sound` is the name of a system alert sound, such as `"Basso"`, `"Glass"`,
`"Ping"` or `"Submarine"`. The full list is in `/System/Library/Sounds`.

## Getting notified when a script finishes

```python
import macos

def main():
    ...

try:
    main()
except Exception as error:
    macos.notify(str(error), title="Script failed", sound="Basso")
    raise
else:
    macos.notify("All done", title="Script finished", sound="Glass")
```

## How it works

The notification is posted through AppleScript's `display notification`. The
native API (`UNUserNotificationCenter`) only works from a signed app bundle,
which a Python script isn't. The text is passed to AppleScript as arguments,
never pasted into the script source, so quotes or backslashes in it are safe.

Because of this, macOS shows the notification as coming from *Script Editor*.
If nothing appears, see [Permissions](permissions.md#notifications).

## Reference

- {func}`macos.notify`
