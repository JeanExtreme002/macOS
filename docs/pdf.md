# PDF

{mod}`macos.pdf` reads, merges and splits PDFs with PDFKit, the framework
behind Preview. Pages are numbered from 1, like in Preview.

```python
import macos

macos.pdf.page_count("report.pdf")            # 12
macos.pdf.text("report.pdf")                  # all the text
macos.pdf.text("report.pdf", pages=[1, 2])    # only some pages
```

## Merging and splitting

```python
macos.pdf.merge(["january.pdf", "february.pdf"], "q1.pdf")
macos.pdf.extract("report.pdf", [1], "cover.pdf")            # one page
macos.pdf.extract("report.pdf", [3, 1, 2], "reordered.pdf")
```

{func}`~macos.pdf.extract` keeps the pages in the order you give, so it also
reorders pages.

## Rendering pages

{func}`~macos.pdf.render` draws a page as PNG bytes. `size` is the longest side
in pixels (up to 4096):

```python
from pathlib import Path

image = macos.pdf.render("report.pdf", page=1, size=1600)
Path("cover.png").write_bytes(image)
```

## Scanned PDFs

Scanned documents are images with no text layer, so {func}`~macos.pdf.text`
returns empty text for them. Render the page and read it with
[OCR](vision.md) instead:

```python
macos.vision.text(macos.pdf.render("scan.pdf", page=1, size=2048))
```

Use a large `size`: text drawn small is hard to read.

## Encrypted PDFs

Pass `password` to open an encrypted PDF. Without it, or with the wrong one,
the functions raise {class}`~macos.PermissionDeniedError`:

```python
macos.pdf.text("statement.pdf", password="1234")
macos.pdf.merge(["statement.pdf", "cover.pdf"], "all.pdf", password="1234")
```

{func}`~macos.pdf.merge` uses the password for every encrypted input, so they
must share it. The files it writes are not encrypted.

## Reference

- {func}`macos.pdf.page_count`
- {func}`macos.pdf.text`
- {func}`macos.pdf.merge`
- {func}`macos.pdf.extract`
- {func}`macos.pdf.render`
