# Images

{mod}`macos.image` reads, converts and resizes images, including the HEIC
photos from iPhones, reads and removes their metadata, and generates QR codes. It uses ImageIO, the framework
behind Preview and Photos, so there's no Pillow or C library to install.

```python
import macos

macos.image.info("IMG_0042.heic")
# ImageInfo(width=4032, height=3024, format='heic', has_alpha=False, orientation=6, dpi=72.0)

macos.image.convert("IMG_0042.heic", "IMG_0042.jpg")
macos.image.resize("IMG_0042.heic", "small.jpg", width=800)
```

## Converting

{func}`~macos.image.convert` writes the format of the output's extension:
`.jpg`, `.png`, `.heic`, `.tiff`, `.gif` or `.bmp`. It reads anything macOS
opens, WebP, AVIF and camera RAW files included.

```python
macos.image.convert("photo.heic", "photo.jpg", quality=0.8)   # quality: 0.0 to 1.0
macos.image.convert("scan.tiff", "scan.png")
```

Metadata such as the date, camera and orientation is kept. Animated GIFs and
multi-page TIFFs keep all their frames when converted to GIF or TIFF; the other
formats hold a single image, so they get the first frame. To convert a whole
folder of iPhone photos:

```python
from pathlib import Path

for photo in Path("~/Downloads").expanduser().glob("*.heic"):
    macos.image.convert(photo, photo.with_suffix(".jpg"))
```

## Resizing

{func}`~macos.image.resize` scales an image to fit a width, a height or both,
keeping its proportions:

```python
macos.image.resize("photo.jpg", "thumb.jpg", width=300)
macos.image.resize("photo.jpg", "fit.png", width=1024, height=1024)
```

Photos taken in portrait are turned upright first, following their EXIF
orientation. The metadata (date, camera, location, DPI) is kept. Images are
only scaled down: a size larger than the original keeps the original size.

## Image details

{func}`~macos.image.info` returns an {class}`~macos.image.ImageInfo` with the
`width` and `height` in pixels, the `format` (`'jpeg'`, `'png'`, `'heic'`...),
whether it `has_alpha` (transparency), the EXIF `orientation` and the `dpi`.

## Metadata

{func}`~macos.image.taken_at` and {func}`~macos.image.location` read when and
where a photo was taken, from its EXIF and GPS data:

```python
macos.image.taken_at("IMG_0042.heic")   # datetime.datetime(2024, 5, 1, 10, 30)
macos.image.location("IMG_0042.heic")   # (-22.9519, -43.2105): latitude, longitude
```

Both return `None` when the image doesn't record it, as with screenshots and
most images from the web. The date is the camera's local time, without a time
zone. {func}`~macos.image.metadata` returns everything the file records, as
nested dictionaries (`'{Exif}'`, `'{GPS}'`, `'{TIFF}'`...):

```python
macos.image.metadata("IMG_0042.heic")["{TIFF}"]["Model"]   # 'iPhone 15 Pro'
```

## Removing metadata

iPhone photos record where they were taken. Before sharing one,
{func}`~macos.image.strip_metadata` saves a copy without the location, the
date, the camera or the editing software:

```python
macos.image.strip_metadata("IMG_0042.heic", "share.jpg")
```

Only the orientation is kept, so the picture still shows upright. As with
{func}`~macos.image.convert`, the output's extension sets the format.

## QR codes

{func}`~macos.image.qr_code` generates a QR code as PNG bytes:

```python
from pathlib import Path

image = macos.image.qr_code("https://python.org", size=512)
Path("site.png").write_bytes(image)
```

`correction` sets how much damage the code survives: `"L"`, `"M"` (the
default), `"Q"` or `"H"`. To read QR codes, see {func}`macos.vision.barcodes`.

## Reference

- {func}`macos.image.info`
- {func}`macos.image.metadata`
- {func}`macos.image.taken_at`
- {func}`macos.image.location`
- {func}`macos.image.strip_metadata`
- {func}`macos.image.convert`
- {func}`macos.image.resize`
- {func}`macos.image.qr_code`
- {class}`macos.image.ImageInfo`
