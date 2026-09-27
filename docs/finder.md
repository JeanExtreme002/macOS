# Finder

{mod}`macos.finder` reveals files, moves them to the Trash and manages their
tags, the same way Finder does.

## Revealing a file

```python
import macos

macos.finder.reveal("report.pdf")   # opens a Finder window with it selected
```

## Moving to the Trash

{func}`~macos.finder.trash` moves a file or folder to the Trash and returns
where it ended up:

```python
macos.finder.trash("old.log")   # PosixPath('/Users/alice/.Trash/old.log')
```

Unlike {func}`os.remove` or {func}`shutil.rmtree`, nothing is deleted: the item
can be restored from the Trash with *Put Back*.

## Tags

```python
macos.finder.tags("report.pdf")                       # []
macos.finder.add_tags("report.pdf", "Work", "Red")    # ['Work', 'Red']
macos.finder.remove_tags("report.pdf", "Red")         # ['Work']
macos.finder.set_tags("report.pdf", ["Done"])         # replace them all
macos.finder.set_tags("report.pdf", [])               # remove them all
```

Tags show up in Finder's sidebar and are searchable in Spotlight. Finder's
default tags are named after colors (`"Red"`, `"Orange"`, `"Yellow"`,
`"Green"`, `"Blue"`, `"Purple"`, `"Gray"`).

All functions raise `FileNotFoundError` when the path doesn't exist.

## Thumbnails

{func}`~macos.finder.thumbnail` returns a preview of a file as PNG bytes, like
the ones Finder shows. Documents, images, videos and PDFs get a preview of their
content (through Quick Look); apps, folders and other files get their icon:

```python
from pathlib import Path

Path("preview.png").write_bytes(macos.finder.thumbnail("report.pdf", size=512))
```

`size` is the largest side, in pixels: 256 by default, up to 4096.

## Reference

- {func}`macos.finder.reveal`
- {func}`macos.finder.trash`
- {func}`macos.finder.tags`
- {func}`macos.finder.set_tags`
- {func}`macos.finder.add_tags`
- {func}`macos.finder.remove_tags`
- {func}`macos.finder.thumbnail`
