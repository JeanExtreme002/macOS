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

## Read text in an image

```python
macos.vision.text("receipt.png")
```

## Convert an iPhone photo

```python
macos.image.convert("IMG_0042.heic", "IMG_0042.jpg")
```

## Read a PDF

```python
macos.pdf.text("report.pdf")
```

## Remove a photo's background

```python
from pathlib import Path

image = macos.vision.remove_background("dog.jpg")
Path("cutout.png").write_bytes(image)
```

## Scan a document

```python
scan = macos.vision.scan_document("receipt.jpg")   # a photo of the receipt
macos.pdf.from_images([scan], "receipt.pdf")
```

## Find duplicate photos

```python
photos = sorted(Path("~/Pictures").expanduser().glob("*.jpg"))
macos.vision.duplicates(photos)   # [[PosixPath('IMG_1.jpg'), PosixPath('IMG_1 copy.jpg')]]
```

## Switch the audio output

```python
macos.audio.set_output("AirPods")
```

## Type and click

```python
macos.keyboard.type("Hello from Python")
macos.keyboard.press("cmd+s")
macos.mouse.click(300, 400)
```

These need the [Accessibility permission](permissions.md#accessibility).

## Check your AirPods' battery

```python
for device in macos.bluetooth.devices():
    print(device.name, device.battery)   # AirPods Pro {'left': 90, 'right': 85, 'case': 40}
```

## Arrange windows

```python
window = macos.windows.focused()
window.set_frame(0, 25, 1280, 800)
```

## React to a global shortcut

```python
macos.hotkeys.register("ctrl+option+s", lambda: macos.screenshot("shot.png"))
macos.hotkeys.run()
```

## Record the screen and share it

```python
macos.screen.record("demo.mov", 10)
macos.video.convert("demo.mov", "demo.mp4", quality="medium")
```

## Control the music

```python
macos.music.now_playing()   # Track(title='Imagine', artist='John Lennon', ...)
macos.music.next()
```

## Open a file with an app

```python
macos.apps.open_with("report.pdf", "Preview")
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
