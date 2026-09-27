# Quick Start

Everything lives under a single import:

```python
import macos
```

## Show a notification

```python
macos.notify("3 tests failed", title="CI", sound="Basso")
```

## Copy and paste text

```python
macos.clipboard.copy("hello")
macos.clipboard.paste()        # 'hello'
```

## Check for Dark mode

```python
if macos.appearance.is_dark():
    theme = "dark"
```

## Work with apps

```python
safari = macos.apps.open("Safari")
print(safari.name, safari.pid)
safari.quit()
```

## Store a password

```python
macos.keychain.set("my-app", "alice", "s3cret")
macos.keychain.get("my-app", "alice")     # 's3cret'
```

## Speak

```python
macos.say("Hello from Python")
```

## Take a screenshot

```python
path = macos.screenshot("screen.png")
```

## Check the battery and stay awake

```python
battery = macos.power.battery()   # None on a Mac without a battery
if battery is not None:
    print(battery.percent)

with macos.power.keep_awake():
    long_task()
```

## Run a shortcut

```python
macos.shortcuts.run("Translate", input="Olá")
```

## Trash and tag files

```python
macos.finder.add_tags("report.pdf", "Work")
macos.finder.trash("old.log")
```

## Change the volume

```python
macos.volume.set(30)
```

## Search with Spotlight

```python
macos.spotlight.search("kind:pdf invoice")
```

## Ask the user

```python
if macos.dialog.confirm("Continue?"):
    name = macos.dialog.prompt("Your name:")
```

## Handle errors

Everything the package raises derives from {class}`~macos.MacOSError`:

```python
try:
    macos.screenshot("screen.png")
except macos.PermissionDeniedError as error:
    print(error)   # says which permission to enable, and where
```

Some features need a privacy permission first. See [Permissions](permissions.md).
