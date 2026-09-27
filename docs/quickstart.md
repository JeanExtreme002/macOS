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

## Handle errors

Everything the package raises derives from {class}`~macos.MacOSError`:

```python
try:
    macos.screenshot("screen.png")
except macos.PermissionDeniedError as error:
    print(error)   # says which permission to enable, and where
```

Some features need a privacy permission first. See [Permissions](permissions.md).
