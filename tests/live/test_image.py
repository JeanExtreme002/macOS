"""Tests of :mod:`macos.image` against the real system. Skipped outside macOS."""

import pytest

import macos
from tests.helpers import png_size, rgb_png, small_png


def test_image_convert_resize_and_info(tmp_path):
    source = tmp_path / "original.png"
    source.write_bytes(small_png(40, 20))

    heic = macos.image.convert(source, tmp_path / "photo.heic")
    assert macos.image.info(heic).format == "heic"
    jpeg = macos.image.convert(heic, tmp_path / "photo.jpg", quality=0.7)
    info = macos.image.info(jpeg)
    assert (info.width, info.height, info.format) == (40, 20, "jpeg")

    small = macos.image.resize(jpeg, tmp_path / "small.png", width=10)
    assert (macos.image.info(small).width, macos.image.info(small).height) == (10, 5)
    same = macos.image.resize(jpeg, tmp_path / "same.png", width=400)  # never scaled up
    assert macos.image.info(same).width == 40

    junk = tmp_path / "junk.jpg"
    junk.write_text("not an image")
    with pytest.raises(ValueError):
        macos.image.info(junk)


def test_resize_turns_photos_upright(tmp_path):
    # A 40x20 image marked as rotated a quarter turn (EXIF orientation 6),
    # like a portrait photo from a phone.
    from macos import _cf

    source = tmp_path / "wide.png"
    source.write_bytes(small_png(40, 20))
    rotated = tmp_path / "rotated.jpg"
    io = macos.image._io()
    with _cf.owned(macos.image._source(source)) as image_source:
        options = macos.image._options({"kCGImagePropertyOrientation": 6})
        with _cf.owned(options):
            macos.image._write(
                rotated, "public.jpeg", lambda d: io.CGImageDestinationAddImageFromSource(d, image_source, 0, options)
            )
    assert macos.image.info(rotated).orientation == 6

    upright = macos.image.resize(rotated, tmp_path / "upright.png", height=40)
    assert (macos.image.info(upright).width, macos.image.info(upright).height) == (20, 40)


def test_convert_keeps_every_frame_where_the_format_can(tmp_path):
    from macos import _cf

    source = tmp_path / "frame.png"
    source.write_bytes(small_png(8, 8))
    io = macos.image._io()
    with _cf.owned(macos.image._source(source)) as image_source:
        macos.image._write(
            tmp_path / "anim.gif",
            "com.compuserve.gif",
            lambda d: [io.CGImageDestinationAddImageFromSource(d, image_source, 0, None) for _ in range(3)],
            3,
        )

    def frames(path):
        with _cf.owned(macos.image._source(path)) as opened:
            return io.CGImageSourceGetCount(opened)

    assert frames(macos.image.convert(tmp_path / "anim.gif", tmp_path / "anim.tiff")) == 3
    assert frames(macos.image.convert(tmp_path / "anim.gif", tmp_path / "first.png")) == 1


def test_resize_keeps_metadata(tmp_path):
    from macos import _cf

    source = tmp_path / "plain.png"
    source.write_bytes(small_png(40, 20))
    photo = tmp_path / "photo.jpg"
    io = macos.image._io()
    with _cf.owned(macos.image._source(source)) as image_source:
        options = macos.image._options({"kCGImagePropertyDPIWidth": 300, "kCGImagePropertyDPIHeight": 300})
        with _cf.owned(options):
            macos.image._write(
                photo, "public.jpeg", lambda d: io.CGImageDestinationAddImageFromSource(d, image_source, 0, options)
            )

    small = macos.image.info(macos.image.resize(photo, tmp_path / "small.jpg", width=10))
    assert (small.width, small.dpi, small.orientation) == (10, 300.0, 1)


def test_image_metadata_round_trip(tmp_path):
    from macos import _cf

    source = tmp_path / "plain.png"
    source.write_bytes(small_png(40, 20))
    photo = tmp_path / "photo.jpg"
    properties = {
        "Orientation": 6,
        "{Exif}": {"DateTimeOriginal": "2024:05:01 10:30:00"},
        "{GPS}": {"Latitude": 22.95, "LatitudeRef": "S", "Longitude": 43.21, "LongitudeRef": "W"},
    }
    io = macos.image._io()
    with _cf.owned(macos.image._source(source)) as image_source, _cf.owned(_cf.from_python(properties)) as options:
        macos.image._write(photo, "public.jpeg", lambda d: io.CGImageDestinationAddImageFromSource(d, image_source, 0, options))

    assert macos.image.metadata(photo)["{GPS}"]["LatitudeRef"] == "S"
    assert macos.image.taken_at(photo).isoformat() == "2024-05-01T10:30:00"
    latitude, longitude = macos.image.location(photo)
    assert (round(latitude, 2), round(longitude, 2)) == (-22.95, -43.21)

    clean = macos.image.strip_metadata(photo, tmp_path / "clean.jpg")
    assert macos.image.location(clean) is None
    assert macos.image.taken_at(clean) is None
    assert "{GPS}" not in macos.image.metadata(clean)
    assert macos.image.info(clean).orientation == 6  # still shows upright

    assert macos.image.taken_at(source) is None and macos.image.location(source) is None


def _halves(tmp_path):
    """A 40x20 PNG: red on the left half, blue on the right."""
    path = tmp_path / "halves.png"
    path.write_bytes(rgb_png(40, 20, lambda x, y: (255, 0, 0) if x < 20 else (0, 0, 255)))
    return path


def _corner_color(path, tmp_path, box):
    corner = macos.image.crop(path, tmp_path / "corner.png", box)
    return macos.image.dominant_colors(corner, count=1)[0]


def test_image_edits(tmp_path):
    image = _halves(tmp_path)
    red, blue = "#ff0000", "#0000ff"

    assert set(macos.image.dominant_colors(image)) == {red, blue}
    assert _corner_color(image, tmp_path, (0, 0, 5, 5)) == red

    right = macos.image.crop(image, tmp_path / "right.png", (25, 5, 10, 10))
    assert (macos.image.info(right).width, macos.image.info(right).height) == (10, 10)
    assert macos.image.dominant_colors(right) == [blue]
    with pytest.raises(ValueError, match="doesn't fit"):
        macos.image.crop(image, tmp_path / "out.png", (30, 0, 20, 5))

    # A quarter turn clockwise puts the left (red) half on top.
    turned = macos.image.rotate(image, tmp_path / "turned.png", 90)
    assert (macos.image.info(turned).width, macos.image.info(turned).height) == (20, 40)
    assert _corner_color(turned, tmp_path, (0, 0, 5, 5)) == red
    back = macos.image.rotate(turned, tmp_path / "back.png", -90)
    assert _corner_color(back, tmp_path, (0, 0, 5, 5)) == red

    mirrored = macos.image.flip(image, tmp_path / "mirrored.png")
    assert _corner_color(mirrored, tmp_path, (0, 0, 5, 5)) == blue
    upside_down = macos.image.flip(image, tmp_path / "upside-down.png", direction="vertical")
    assert _corner_color(upside_down, tmp_path, (0, 0, 5, 5)) == red


def test_image_edits_work_on_the_upright_picture(tmp_path):
    from macos import _cf

    # The red/blue image stored as is, but tagged with EXIF orientation 6: it
    # shows turned a quarter clockwise (20x40, red on top), as phone photos do.
    portrait = tmp_path / "portrait.png"
    io = macos.image._io()
    with _cf.owned(macos.image._source(_halves(tmp_path))) as source, _cf.owned(
        _cf.from_python({"Orientation": 6})
    ) as options:
        macos.image._write(portrait, "public.png", lambda d: io.CGImageDestinationAddImageFromSource(d, source, 0, options))

    mirrored = macos.image.flip(portrait, tmp_path / "mirrored.png")
    assert (macos.image.info(mirrored).width, macos.image.info(mirrored).height) == (20, 40)
    assert macos.image.info(mirrored).orientation == 1
    assert _corner_color(mirrored, tmp_path, (0, 0, 5, 5)) == "#ff0000"
    assert png_size(macos.vision.smart_crop(portrait, 20, 40)) == (20, 40)


def test_blur_faces_and_best_shot_without_faces(tmp_path):
    image = _halves(tmp_path)

    copy = macos.image.blur_faces(image, tmp_path / "copy.png")

    assert (macos.image.info(copy).width, macos.image.info(copy).height) == (40, 20)
    assert set(macos.image.dominant_colors(copy)) == {"#ff0000", "#0000ff"}  # nothing to blur
    assert macos.vision.best_shot([image, copy]) is None


@pytest.mark.parametrize("extension", [".jpg", ".heic"])
def test_set_taken_at_and_location(tmp_path, extension):
    from datetime import datetime, timedelta, timezone

    photo = macos.image.convert(_halves(tmp_path), tmp_path / ("photo" + extension))
    when = datetime(2024, 5, 1, 10, 30, tzinfo=timezone(timedelta(hours=-3)))

    assert macos.image.set_taken_at(photo, when) == photo
    macos.image.set_location(photo, -22.95, -43.21)

    assert macos.image.taken_at(photo) == when
    latitude, longitude = macos.image.location(photo)
    assert (round(latitude, 2), round(longitude, 2)) == (-22.95, -43.21)
    assert macos.image.info(photo).width == 40

    copy = macos.image.set_location(photo, 48.85, 2.35, output=tmp_path / ("copy" + extension))
    assert macos.image.location(photo)[0] < 0  # the original is left alone
    assert macos.image.location(copy)[0] > 0
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(["halves.png", "photo" + extension, "copy" + extension])


def test_image_editing(tmp_path):
    image = macos.image
    colorful = _halves(tmp_path)
    assert image.info(image.enhance(colorful, tmp_path / "enhanced.png")).width == 40
    for color in image.dominant_colors(image.effect(colorful, tmp_path / "noir.png", "noir")):
        assert int(color[1:3], 16) == int(color[3:5], 16) == int(color[5:7], 16)  # shades of gray

    big = tmp_path / "big.png"
    big.write_bytes(rgb_png(400, 200, lambda x, y: (20, 40, 160)))
    stamped = image.watermark(big, tmp_path / "stamped.png", "SAMPLE", color="#ffffff", opacity=0.8)
    assert len(image.dominant_colors(stamped)) > 1  # the text shows on the plain blue
    with pytest.raises(ValueError, match="no person"):
        image.blur_background(big, tmp_path / "blurred.png")

    sheet = image.contact_sheet([colorful, big, colorful], tmp_path / "sheet.png", columns=2, size=100, gap=10)
    assert (image.info(sheet).width, image.info(sheet).height) == (230, 230)
