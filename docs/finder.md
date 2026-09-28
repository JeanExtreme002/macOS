# Finder

{mod}`macos.finder` reveals files, moves them to the Trash, manages their
tags and follows aliases, the same way Finder does.

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

## Aliases

A Finder alias (*File › Make Alias*) points to a file or folder and keeps
finding it after it's moved or renamed. Unlike a symbolic link, Python can't
follow it: `os.path.realpath()` and `Path.resolve()` return the alias itself.
{func}`~macos.finder.resolve_alias` returns the original:

```python
macos.finder.resolve_alias("calibre alias")   # PosixPath('/Applications/calibre.app')
macos.finder.is_alias("calibre alias")        # True
```

{func}`~macos.finder.resolve_alias` also follows symbolic links, and aliases
of aliases, and returns any other path as it is, so it's safe to call on
every path. It raises `FileNotFoundError` when the original was deleted.

{func}`~macos.finder.make_alias` creates one, next to the original and named
`"<name> alias"` as Finder does, or at the path or in the folder you pass:

```python
macos.finder.make_alias("report.pdf")                 # report.pdf alias
macos.finder.make_alias("report.pdf", "~/Desktop")    # ~/Desktop/report.pdf alias
```

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
- {func}`macos.finder.is_alias`
- {func}`macos.finder.resolve_alias`
- {func}`macos.finder.make_alias`
