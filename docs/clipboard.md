# Clipboard

{mod}`macos.clipboard` reads and writes the system clipboard (the general
pasteboard) as text.

```python
import macos

macos.clipboard.copy("hello")
macos.clipboard.paste()       # 'hello'
macos.clipboard.clear()
macos.clipboard.paste()       # None
```

{func}`~macos.clipboard.paste` returns `None` when the clipboard holds no text,
for example after copying an image.

Unicode round-trips correctly, whatever your terminal's locale is:

```python
macos.clipboard.copy("olá 🍎")
macos.clipboard.paste()        # 'olá 🍎'
```

## Images

{func}`~macos.clipboard.copy_image` puts an image on the clipboard, from a file
or from its bytes. Any format macOS can open works (PNG, JPEG, HEIC, GIF, TIFF,
PDF...):

```python
macos.clipboard.copy_image("chart.png")
macos.clipboard.copy_image(png_bytes)
```

{func}`~macos.clipboard.paste_image` returns the image on the clipboard as PNG
bytes, whatever format it was copied in, or `None` if there is no image:

```python
from pathlib import Path

image = macos.clipboard.paste_image()

if image is not None:
    Path("pasted.png").write_bytes(image)
```

{func}`~macos.clipboard.has_image` checks for an image without converting it.

## Waiting for a copy

{func}`~macos.clipboard.wait_for_change` blocks until something new is copied,
and returns it as text (`None` if it isn't text). With `timeout`, it raises
`TimeoutError` if nothing is copied in time:

```python
print("Copy a link...")
link = macos.clipboard.wait_for_change(timeout=60)
```

## Detecting changes

{func}`~macos.clipboard.change_count` returns a counter that increases every
time any app changes the clipboard. Comparing two readings tells you whether
something new was copied, without reading the contents:

```python
import time
import macos

last = macos.clipboard.change_count()

while True:
    count = macos.clipboard.change_count()

    if count != last:
        last = count
        print("Copied:", macos.clipboard.paste())

    time.sleep(0.5)
```

## Reference

- {func}`macos.clipboard.copy`
- {func}`macos.clipboard.paste`
- {func}`macos.clipboard.clear`
- {func}`macos.clipboard.change_count`
- {func}`macos.clipboard.wait_for_change`
- {func}`macos.clipboard.copy_image`
- {func}`macos.clipboard.paste_image`
- {func}`macos.clipboard.has_image`
