# PDF

{mod}`macos.pdf` reads, merges, splits, rotates and encrypts PDFs, and makes
them from images, with PDFKit, the framework behind Preview. Pages are numbered from 1, like in Preview.

```python
import macos

macos.pdf.page_count("report.pdf")            # 12
macos.pdf.text("report.pdf")                  # all the text
macos.pdf.text("report.pdf", pages=[1, 2])    # only some pages
```

## Document details

{func}`~macos.pdf.metadata` returns what the PDF records about itself:

```python
details = macos.pdf.metadata("report.pdf")
details.title      # 'Quarterly report'
details.author     # 'Alice'
details.created    # datetime.datetime(2024, 5, 1, 10, 30, tzinfo=...)
```

The {class}`~macos.pdf.Metadata` also has the `subject`, the `keywords`, the
`modified` date, the `creator` (the app it was made in) and the `producer`
(the software that wrote the PDF). Missing fields are `None`.

## Merging and splitting

```python
macos.pdf.merge(["january.pdf", "february.pdf"], "q1.pdf")
macos.pdf.extract("report.pdf", [1], "cover.pdf")            # one page
macos.pdf.extract("report.pdf", [3, 1, 2], "reordered.pdf")
```

{func}`~macos.pdf.extract` keeps the pages in the order you give, so it also
reorders pages.

## Rotating pages

```python
macos.pdf.rotate("scan.pdf", 90, "scan.pdf")               # every page, clockwise
macos.pdf.rotate("scan.pdf", -90, "fixed.pdf", pages=[2])  # only page 2, counter-clockwise
```

The output can be the input itself: it's replaced only once the new file is
written.

## Watermarks

{func}`~macos.pdf.watermark` writes a text across every page, diagonally and
see-through:

```python
macos.pdf.watermark("contract.pdf", "DRAFT", "contract-draft.pdf")
macos.pdf.watermark("id.pdf", "Only for Acme Inc.", "id-acme.pdf", color="#d00000", opacity=0.3)
```

The text is sized to fit each page. The pages keep their look and their text,
but not their links or form fields.

## Making PDFs smaller

{func}`~macos.pdf.compress` works like Preview's *Export › Reduce File Size*:
images are scaled down and compressed again, which makes PDFs of scans and
photos several times smaller, while text stays sharp.

```python
macos.pdf.compress("scan.pdf", "scan-small.pdf")
```

Photos lose detail, so keep the original. A PDF with only text has nothing to
shrink: then the output is a copy of it, never a bigger file.

## Grayscale

{func}`~macos.pdf.grayscale` saves a copy in shades of gray, for printing
without color, with the *Gray Tone* filter that ships with macOS:

```python
macos.pdf.grayscale("slides.pdf", "slides-print.pdf")
```

## Rendering pages

{func}`~macos.pdf.render` draws a page as PNG bytes. `size` is the longest side
in pixels (up to 4096):

```python
from pathlib import Path

image = macos.pdf.render("report.pdf", page=1, size=1600)
Path("cover.png").write_bytes(image)
```

## PDFs from images

{func}`~macos.pdf.from_images` makes a PDF with one page per image, in order.
Each page takes its image's size:

```python
macos.pdf.from_images(["page1.jpg", "page2.heic"], "document.pdf")
```

Images can also be bytes, so photos of paper become a PDF scan with
{func}`macos.vision.scan_document`:

```python
pages = [macos.vision.scan_document(photo) for photo in ["receipt.jpg", "contract.jpg"]]
macos.pdf.from_images(pages, "scan.pdf")
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

To encrypt a PDF, {func}`~macos.pdf.encrypt` saves a copy that asks for a
password to open, in Preview, Acrobat and browsers alike:

```python
macos.pdf.encrypt("statement.pdf", "locked.pdf", "1234")
macos.pdf.encrypt("locked.pdf", "relocked.pdf", "new-pass", current_password="1234")
```

## Reference

- {func}`macos.pdf.page_count`
- {func}`macos.pdf.text`
- {func}`macos.pdf.metadata`
- {func}`macos.pdf.merge`
- {func}`macos.pdf.extract`
- {func}`macos.pdf.rotate`
- {func}`macos.pdf.encrypt`
- {func}`macos.pdf.watermark`
- {func}`macos.pdf.compress`
- {func}`macos.pdf.grayscale`
- {func}`macos.pdf.render`
- {func}`macos.pdf.from_images`
- {class}`macos.pdf.Metadata`
