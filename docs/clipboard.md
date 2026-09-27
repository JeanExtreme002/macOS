# Clipboard

{mod}`macos.clipboard` reads and writes the system clipboard (the general
pasteboard) as text.

```python
import macos

macos.clipboard.copy("hello")
macos.clipboard.paste()      # 'hello'
macos.clipboard.clear()
macos.clipboard.paste()      # None
```

{func}`~macos.clipboard.paste` returns `None` when the clipboard holds no text,
for example after copying an image.

Unicode round-trips correctly, whatever your terminal's locale is:

```python
macos.clipboard.copy("olá 🍎")
macos.clipboard.paste()      # 'olá 🍎'
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
