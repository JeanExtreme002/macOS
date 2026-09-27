# Vision

{mod}`macos.vision` analyzes images with Apple's Vision framework: it reads
text (OCR), QR codes and barcodes, says what an image shows and finds faces. It
runs on the Mac, offline: nothing to install, no model to download and no
permission to grant.

## Reading text

```python
import macos

macos.vision.text("receipt.png")
# 'Coffee Shop\nTotal: R$ 42,00\nThank you!'
```

The image can be a path or the bytes of an image file, in any format macOS
opens (PNG, JPEG, HEIC, TIFF, PDF...). That makes it easy to combine with other
features:

```python
macos.vision.text(macos.clipboard.paste_image())      # text of a copied image
macos.vision.text(macos.screenshot(region=(0, 0, 800, 600)))
```

## Languages

By default Vision detects the language. When you know it, pass `languages`,
most likely first. This improves accents and language-specific characters:

```python
macos.vision.text("nota.jpg", languages=["pt-BR", "en-US"])
```

{func}`~macos.vision.languages` lists the supported codes:

```python
macos.vision.languages()   # ['en-US', 'fr-FR', 'it-IT', 'de-DE', 'es-ES', 'pt-BR', ...]
```

## Lines, confidence and position

{func}`~macos.vision.lines` returns each line with how confident Vision is and
where it is in the image:

```python
for line in macos.vision.lines("slide.png"):
    print(line.text, line.confidence, line.box)
```

```text
Quarterly results 1.0 (0.08, 0.10, 0.52, 0.09)
Revenue grew 12% 0.98 (0.08, 0.25, 0.41, 0.06)
```

`box` is `(x, y, width, height)` as fractions of the image size, measured from
the top-left corner, so it works whatever the image's resolution.

## Speed

Recognition is accurate by default. `fast=True` is a few times faster but
less precise, and it doesn't correct words with a dictionary:

```python
macos.vision.text("page.png", fast=True)
```

## QR codes and barcodes

{func}`~macos.vision.barcodes` reads QR codes and barcodes (EAN, UPC, Code 128,
PDF417, Aztec, Data Matrix...):

```python
for code in macos.vision.barcodes("poster.jpg"):
    print(code.kind, code.payload)   # QR https://python.org
```

Each {class}`~macos.vision.Barcode` has its `payload`, its `kind` (`'QR'`,
`'EAN13'`...) and its `box`. To make a QR code, see {func}`macos.image.qr_code`.

## What's in an image

{func}`~macos.vision.classify` returns labels for what an image shows, most
likely first:

```python
macos.vision.classify("holiday.jpg")
# [('outdoor', 0.85), ('sky', 0.84), ('cloudy', 0.74)]
```

Labels are English words from Vision's own list of over a thousand categories.
`limit` (5 by default) and `min_confidence` (0.1) decide how many come back.

## Faces

{func}`~macos.vision.faces` returns a box for each face found. It locates faces;
it doesn't recognize people.

```python
len(macos.vision.faces("team.jpg"))   # 4
```

## Removing the background

{func}`~macos.vision.remove_background` cuts out the subject of a photo (a
person, an animal, an object) and returns it as a PNG with a transparent
background, like *Lift Subject from Background* in Photos:

```python
from pathlib import Path

Path("cutout.png").write_bytes(macos.vision.remove_background("dog.jpg"))
Path("tight.png").write_bytes(macos.vision.remove_background("dog.jpg", crop=True))
```

By default the result keeps the photo's size; `crop=True` trims it to the
subject. It returns `None` when nothing stands out, and needs macOS 14 or later.

## Cats and dogs

{func}`~macos.vision.animals` finds cats and dogs, the only animals Vision
recognizes:

```python
for animal in macos.vision.animals("garden.jpg"):
    print(animal.kind, animal.confidence)   # dog 0.93
```

## Reference

- {func}`macos.vision.text`
- {func}`macos.vision.lines`
- {func}`macos.vision.languages`
- {class}`macos.vision.TextLine`
- {func}`macos.vision.barcodes`
- {class}`macos.vision.Barcode`
- {func}`macos.vision.classify`
- {func}`macos.vision.faces`
- {func}`macos.vision.remove_background`
- {func}`macos.vision.animals`
- {class}`macos.vision.Animal`
