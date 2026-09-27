# Vision

{mod}`macos.vision` reads the text in images (OCR) with Apple's Vision
framework, the engine behind Live Text in Photos and Preview. It runs on the
Mac, offline: nothing to install, no model to download and no permission to
grant.

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

## Reference

- {func}`macos.vision.text`
- {func}`macos.vision.lines`
- {func}`macos.vision.languages`
- {class}`macos.vision.TextLine`
