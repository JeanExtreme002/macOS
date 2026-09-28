"""Tests against the real system. Skipped outside macOS."""

import os
import time
import uuid
from pathlib import Path

import pytest

import macos
from macos import _objc

pytestmark = pytest.mark.live


def _clipboard_has_content() -> bool:
    with _objc.autorelease_pool():
        types = _objc.send(macos.clipboard._pasteboard(), "types")
        return bool(types) and _objc.send(types, "count", restype=_objc.NSUInteger) > 0


@pytest.fixture
def restore_clipboard():
    before = macos.clipboard.paste()
    if before is None and _clipboard_has_content():
        # Only text can be saved and put back: don't destroy a copied image
        # or file just to run the tests.
        pytest.skip("the clipboard holds non-text content")
    yield
    if before is None:
        macos.clipboard.clear()
    else:
        macos.clipboard.copy(before)


@pytest.mark.usefixtures("restore_clipboard")
def test_clipboard_round_trip():
    text = "olá 🍎 \"quoted\" \\ {}".format(uuid.uuid4())
    count = macos.clipboard.change_count()

    macos.clipboard.copy(text)

    assert macos.clipboard.paste() == text
    assert macos.clipboard.change_count() > count


@pytest.mark.usefixtures("restore_clipboard")
def test_clipboard_clear():
    macos.clipboard.copy("something")
    macos.clipboard.clear()

    assert macos.clipboard.paste() is None


def test_appearance():
    import re

    assert macos.appearance.mode() in ("dark", "light")
    assert macos.appearance.is_dark() == (macos.appearance.mode() == "dark")
    assert isinstance(macos.appearance.is_auto(), bool)
    assert re.fullmatch(r"#[0-9a-f]{6}", macos.appearance.accent_color())


def test_fonts():
    families = macos.system.fonts()

    assert "Helvetica" in families
    assert families == sorted(families, key=str.casefold)
    assert not any(name.startswith(".") for name in families)


def test_keychain_round_trip():
    service = "macos-tests-{}".format(uuid.uuid4())
    try:
        assert macos.keychain.get(service, "user") is None

        macos.keychain.set(service, "user", "sé cret")
        assert macos.keychain.get(service, "user") == "sé cret"

        macos.keychain.set(service, "user", "replaced")
        assert macos.keychain.get(service, "user") == "replaced"
    finally:
        assert macos.keychain.delete(service, "user") is True

    assert macos.keychain.delete(service, "user") is False
    assert macos.keychain.get(service, "user") is None


def test_running_apps():
    everything = macos.apps.running(include_background=True)
    regular = macos.apps.running()

    assert everything, "NSWorkspace returned no applications"
    assert {app.pid for app in regular} <= {app.pid for app in everything}
    assert all(isinstance(app.pid, int) and app.pid > 0 for app in everything)


def test_get_finds_apps_by_bundle_id():
    app = macos.apps.running(include_background=True)[0]
    found = macos.apps.get(app.bundle_id) if app.bundle_id else macos.apps.get(app.name)

    assert found is not None
    assert found.pid == app.pid
    assert found.is_running


def test_locate_ignores_a_folder_with_the_app_name(tmp_path, monkeypatch):
    (tmp_path / "Finder").mkdir()
    monkeypatch.chdir(tmp_path)

    assert macos.apps._locate("Finder") == os.path.realpath("/System/Library/CoreServices/Finder.app")


def test_find_launched_requires_the_same_bundle_path():
    finder = os.path.realpath("/System/Library/CoreServices/Finder.app")

    assert macos.apps._find_launched(finder, "com.apple.finder").bundle_id == "com.apple.finder"
    assert macos.apps._find_launched("/Applications/Another Finder.app", "com.apple.finder") is None


def test_get_unknown_app_returns_none():
    assert macos.apps.get("com.example.definitely-not-installed") is None


def test_open_unknown_app_raises():
    with pytest.raises(macos.AppNotFoundError):
        macos.apps.open("Definitely Not An Installed App {}".format(uuid.uuid4()))


def test_voices_are_installed():
    assert any(voice.name for voice in macos.speech.voices())


def test_screenshot_writes_an_image(tmp_path):
    target = macos.screenshot(tmp_path / "shot.png", region=(0, 0, 50, 50), check_permission=False)

    assert target.exists()
    assert os.path.getsize(target) > 0
    with open(target, "rb") as image:
        assert image.read(8) == b"\x89PNG\r\n\x1a\n"


@pytest.mark.usefixtures("restore_clipboard")
def test_clipboard_keeps_nul_characters():
    macos.clipboard.copy("a\0b")

    assert macos.clipboard.paste() == "a\0b"


def test_get_matches_the_app_file_name_and_path():
    app = next(app for app in macos.apps.running(include_background=True) if app.path and app.path.endswith(".app"))
    file_name = os.path.basename(app.path)

    assert macos.apps.get(file_name).pid == app.pid
    assert macos.apps.get(app.path + "/").pid == app.pid


def test_locate_resolves_bundle_ids_names_and_symlinks():
    finder = "/System/Library/CoreServices/Finder.app"

    assert macos.apps._locate("com.apple.finder") == os.path.realpath(finder)
    assert macos.apps._locate(finder) == os.path.realpath(finder)
    with pytest.raises(macos.AppNotFoundError):
        macos.apps._locate("com.example.definitely-not-installed")


def test_running_apps_from_a_worker_thread():
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(1) as pool:
        in_thread = pool.submit(macos.apps.running, include_background=True).result()

    assert {app.pid for app in in_thread} & {app.pid for app in macos.apps.running(include_background=True)}


def _rgb_png(width, height, pixel):
    """A PNG whose color at (x, y) is ``pixel(x, y)``."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def _png(width=4, height=4):
    """A small valid PNG, so the image tests don't depend on screen access."""
    return _rgb_png(width, height, lambda x, y: (255, 0, 0))


_PIXEL_PNG = _png()


@pytest.mark.usefixtures("restore_clipboard")
def test_clipboard_image_round_trip():
    macos.clipboard.copy_image(_PIXEL_PNG)

    assert macos.clipboard.has_image()
    assert macos.clipboard.paste() is None
    assert macos.clipboard.paste_image().startswith(b"\x89PNG\r\n\x1a\n")

    macos.clipboard.copy("text again")
    assert not macos.clipboard.has_image()
    assert macos.clipboard.paste_image() is None


def test_copy_image_rejects_non_images():
    with pytest.raises(ValueError):
        macos.clipboard.copy_image(b"not an image")


def test_battery():
    battery = macos.power.battery()

    if battery is not None:  # desktops, and CI runners, have none
        assert 0 <= battery.percent <= 100
        assert isinstance(battery.charging, bool)
        assert isinstance(battery.plugged_in, bool)


def test_keep_awake_holds_a_power_assertion():
    import subprocess

    reason = "pymacos test {}".format(uuid.uuid4())

    def active():
        return reason in subprocess.run(["pmset", "-g", "assertions"], capture_output=True, text=True).stdout

    with macos.power.keep_awake(reason=reason):
        assert active()
    assert not active()


def test_shortcuts():
    assert isinstance(macos.shortcuts.list(), list)
    with pytest.raises(macos.ShortcutNotFoundError):
        macos.shortcuts.run("Definitely Not A Shortcut {}".format(uuid.uuid4()))


def test_finder_tags(tmp_path):
    path = tmp_path / "tagged.txt"
    path.write_text("hi")

    assert macos.finder.tags(path) == []
    assert macos.finder.add_tags(path, "pymacos-a", "pymacos-b", "pymacos-a") == ["pymacos-a", "pymacos-b"]
    assert macos.finder.remove_tags(path, "pymacos-a", "missing") == ["pymacos-b"]
    macos.finder.set_tags(path, [])
    assert macos.finder.tags(path) == []


def test_finder_trash(tmp_path):
    path = tmp_path / "trash me {}.txt".format(uuid.uuid4())
    path.write_text("bye")

    trashed = macos.finder.trash(path)
    try:
        assert not path.exists()
        assert trashed.exists()
        assert ".Trash" in trashed.parts
    finally:
        trashed.unlink(missing_ok=True)


def test_finder_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        macos.finder.tags(tmp_path / "missing")


def test_notifications_is_allowed():
    assert macos.notifications.is_allowed() in (True, False, None)


def test_volume_round_trip():
    level, muted = macos.volume.get(), macos.volume.is_muted()
    if level is None:
        pytest.skip("the output device has no volume control")
    try:
        macos.volume.set(level)
        assert macos.volume.get() == level
        macos.volume.mute()
        assert macos.volume.is_muted() is True
        assert macos.volume.get() == level  # muting keeps the level
    finally:
        macos.volume.set(level)
        (macos.volume.mute if muted else macos.volume.unmute)()
    assert macos.volume.is_muted() is muted


def test_spotlight_finds_an_app_by_file_name():
    found = macos.spotlight.search_name("Calculator.app", folder="/System/Applications")
    if not found:
        pytest.skip("Spotlight indexing is off")
    assert Path("/System/Applications/Calculator.app") in found


def test_spotlight_limit_and_invalid_query():
    assert len(macos.spotlight.search("kind:app", folder="/System/Applications", limit=1)) <= 1
    with pytest.raises(ValueError):
        macos.spotlight.search("kMDItemFoo ==")


def test_spotlight_metadata():
    data = macos.spotlight.metadata("/System/Applications/Calculator.app")

    assert data["kMDItemFSName"] == "Calculator.app"


def test_system_info():
    import re
    from datetime import timedelta

    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", macos.system.version())
    assert macos.system.build()
    assert macos.system.model()
    assert re.fullmatch(r"[A-Za-z]+\d+,\d+", macos.system.model_identifier())
    assert macos.system.processor()
    assert macos.system.memory() >= 2**30
    assert macos.system.computer_name()
    assert macos.system.uptime() > timedelta(0)
    assert macos.system.idle_time() >= timedelta(0)


def test_displays():
    displays = macos.screen.displays()
    if not displays:
        pytest.skip("no display attached")

    main = displays[0]
    assert main.is_main
    assert main.width > 0 and main.height > 0
    assert main.pixel_width >= main.width
    assert main.scale >= 1


def test_keychain_accounts():
    service = "macos-tests-{}".format(uuid.uuid4())
    try:
        assert macos.keychain.accounts(service) == []
        macos.keychain.set(service, "bob", "1")
        macos.keychain.set(service, "alice", "2")
        assert macos.keychain.accounts(service) == ["alice", "bob"]
    finally:
        macos.keychain.delete(service, "bob")
        macos.keychain.delete(service, "alice")


def test_say_to_a_file(tmp_path):
    for name in ("speech.aiff", "speech.m4a", "speech.wav"):
        target = macos.say("pymacos", output=tmp_path / name)
        assert target.exists() and target.stat().st_size > 0


@pytest.mark.usefixtures("restore_clipboard")
def test_clipboard_wait_for_change():
    import threading

    timer = threading.Timer(0.3, macos.clipboard.copy, args=("changed",))
    timer.start()
    try:
        assert macos.clipboard.wait_for_change(timeout=5, interval=0.05) == "changed"
    finally:
        timer.cancel()


def test_dialogs_close_after_their_timeout():
    try:
        assert macos.dialog.confirm("pymacos test: this closes by itself", timeout=1) is False
        assert macos.dialog.prompt("pymacos test: this closes by itself", timeout=1) is None
        macos.dialog.alert("pymacos test: this closes by itself", timeout=1)
    except macos.CommandError as error:  # e.g. no window server on a CI runner
        pytest.skip("dialogs can't be shown here: {}".format(error))


def test_ocr_reads_a_quick_look_preview(tmp_path):
    note = tmp_path / "note.txt"
    note.write_text("PYMACOS OCR TEST 12345\nsecond line here\n")

    image = macos.finder.thumbnail(note, size=800)
    assert image.startswith(b"\x89PNG")

    lines = macos.vision.lines(image, languages=["en-US"])
    texts = [line.text for line in lines]
    assert "PYMACOS OCR TEST 12345" in texts
    assert texts.index("PYMACOS OCR TEST 12345") < texts.index("second line here")  # top to bottom
    assert all(0 <= line.confidence <= 1 for line in lines)
    assert all(0 <= value <= 1 for line in lines for value in line.box)


def test_ocr_languages_and_errors(tmp_path):
    assert "en-US" in macos.vision.languages()
    with pytest.raises(FileNotFoundError):
        macos.vision.text(tmp_path / "missing.png")
    with pytest.raises(macos.MacOSError):
        macos.vision.text(b"not an image")


def test_thumbnail_rejects_huge_sizes():
    with pytest.raises(ValueError):
        macos.finder.thumbnail("/System/Library/CoreServices/Finder.app", size=100000)


def test_thumbnail_of_an_app_is_its_icon_at_the_requested_size():
    import struct

    image = macos.finder.thumbnail("/System/Library/CoreServices/Finder.app", size=64)
    width, height = struct.unpack(">II", image[16:24])  # the PNG header
    assert max(width, height) == 64


def test_wallpaper_round_trip():
    current = macos.screen.wallpaper()
    if current is None or not current.exists():
        pytest.skip("the desktop picture isn't a file")
    macos.screen.set_wallpaper(current)
    assert macos.screen.wallpaper() == current


def test_default_apps():
    text_editor = macos.apps.default_for("txt")
    if text_editor is None:
        pytest.skip("no app opens text files here")
    assert text_editor.endswith(".app")
    assert macos.apps.default_for(".txt") == text_editor
    assert macos.apps.default_for("public.plain-text") == text_editor
    assert macos.apps.default_for("definitely-not-an-extension") is None
    assert macos.apps.default_for("backup.txt") == text_editor  # a dotted extension, not a type
    browser = macos.apps.default_browser()
    assert browser is None or browser.endswith(".app")


@pytest.mark.usefixtures("restore_clipboard")
def test_clipboard_files_round_trip(tmp_path):
    first, second = tmp_path / "a.txt", tmp_path / "b.txt"
    first.touch()
    second.touch()

    macos.clipboard.copy_files([first, second])
    assert [path.resolve() for path in macos.clipboard.paste_files()] == [first.resolve(), second.resolve()]

    macos.clipboard.copy("text")
    assert macos.clipboard.paste_files() == []


def test_battery_health():
    battery = macos.power.battery()
    if battery is None:
        pytest.skip("no battery")
    assert battery.cycle_count is None or battery.cycle_count >= 0
    assert battery.health is None or 0 < battery.health <= 100


def test_volumes_and_eject(tmp_path):
    import subprocess

    volumes = macos.system.volumes()
    assert volumes[0].path == Path("/") and volumes[0].total > 0

    name = "PymacosTest{}".format(uuid.uuid4().hex[:6])
    image = tmp_path / "test.dmg"
    created = subprocess.run(
        ["hdiutil", "create", "-size", "2m", "-fs", "HFS+", "-volname", name, "-o", str(image), "-quiet"]
    )
    if created.returncode != 0 or subprocess.run(["hdiutil", "attach", str(image), "-quiet"]).returncode != 0:
        pytest.skip("hdiutil can't create or attach disk images here")
    try:
        mounted = [volume for volume in macos.system.volumes() if volume.name == name]
        assert mounted and mounted[0].is_ejectable
        macos.system.eject(name)
        assert name not in [volume.name for volume in macos.system.volumes()]
    finally:
        subprocess.run(["hdiutil", "detach", "/Volumes/{}".format(name), "-quiet"], capture_output=True)


def _text_pdf(folder, pages):
    """A PDF with real text on each page, made by CUPS (every Mac has it)."""
    import subprocess

    source = folder / "pages.txt"
    source.write_text("\f".join(pages) + "\n")
    target = folder / "doc.pdf"
    with open(target, "wb") as output:
        result = subprocess.run(["cupsfilter", str(source)], stdout=output, stderr=subprocess.DEVNULL)
    if result.returncode != 0 or not target.stat().st_size:
        pytest.skip("cupsfilter can't make PDFs here")
    return target


def test_image_convert_resize_and_info(tmp_path):
    source = tmp_path / "original.png"
    source.write_bytes(_png(40, 20))

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
    source.write_bytes(_png(40, 20))
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


def test_qr_code_round_trip():
    url = "https://github.com/JeanExtreme002/pymacos"
    image = macos.image.qr_code(url, size=300)

    found = macos.vision.barcodes(image)
    assert [(code.payload, code.kind) for code in found] == [(url, "QR")]
    assert macos.vision.faces(image) == []


def test_classify_returns_ranked_labels():
    labels = macos.vision.classify(macos.image.qr_code("pymacos"), min_confidence=0.0, limit=3)

    assert len(labels) <= 3
    assert [confidence for _, confidence in labels] == sorted((c for _, c in labels), reverse=True)


def test_pdf_read_merge_extract_and_render(tmp_path):
    document = _text_pdf(tmp_path, ["Page one says hello", "Page two says ola"])

    assert macos.pdf.page_count(document) == 2
    assert macos.pdf.text(document, pages=[2]) == "Page two says ola"
    assert "Page one says hello" in macos.pdf.text(document)

    merged = macos.pdf.merge([document, document], tmp_path / "merged.pdf")
    assert macos.pdf.page_count(merged) == 4
    reordered = macos.pdf.extract(document, [2, 1], tmp_path / "reordered.pdf")
    assert macos.pdf.text(reordered).startswith("Page two")

    with pytest.raises(ValueError, match="out of range"):
        macos.pdf.text(document, pages=[3])

    page = macos.pdf.render(document, 1, size=2048)
    assert page.startswith(b"\x89PNG")
    assert "Page one says hello" in macos.vision.text(page)


def test_language():
    assert macos.language.detect("Olá, tudo bem com você? Hoje o dia está lindo.") == "pt"
    assert macos.language.detect("   ") is None
    top, probability = macos.language.guess("Bonjour tout le monde, comment allez-vous ?")[0]
    assert top == "fr" and 0 < probability <= 1

    assert macos.language.sentiment("I love this, it is wonderful!") > 0.5
    assert macos.language.sentiment("This is terrible and I hate it.") < -0.5
    assert macos.language.sentiment("") is None


def test_convert_keeps_every_frame_where_the_format_can(tmp_path):
    from macos import _cf

    source = tmp_path / "frame.png"
    source.write_bytes(_png(8, 8))
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
    source.write_bytes(_png(40, 20))
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


def test_pdf_render_is_exact_and_follows_rotation(tmp_path):
    import ctypes
    import struct

    from macos import _objc

    document = _text_pdf(tmp_path, ["A portrait page"])
    for size in (1024, 2048):
        width, height = struct.unpack(">II", macos.pdf.render(document, size=size)[16:24])
        assert max(width, height) == size and height > width

    rotated = tmp_path / "rotated.pdf"
    with macos.pdf._open(document) as opened:
        _objc.send(macos.pdf._page(opened, 1), "setRotation:", 90, argtypes=(ctypes.c_long,), restype=None)
        macos.pdf._save(opened, rotated)
    width, height = struct.unpack(">II", macos.pdf.render(rotated, size=1024)[16:24])
    assert (max(width, height), width > height) == (1024, True)


def test_pdf_passwords(tmp_path):
    from macos import _objc

    document = _text_pdf(tmp_path, ["Secret page"])
    locked = tmp_path / "locked.pdf"
    with macos.pdf._open(document) as opened:
        # PDFKit only encrypts when both a user and an owner password are set.
        options = _objc.send(
            _objc.cls("NSDictionary"),
            "dictionaryWithObjects:forKeys:",
            _objc.nsarray_of([_objc.nsstring("1234"), _objc.nsstring("owner")]),
            _objc.nsarray_of(
                [_objc.nsstring("PDFDocumentUserPasswordOption"), _objc.nsstring("PDFDocumentOwnerPasswordOption")]
            ),
            argtypes=(_objc.id, _objc.id),
        )
        _objc.send(
            opened,
            "writeToFile:withOptions:",
            _objc.nsstring(str(locked)),
            options,
            argtypes=(_objc.id, _objc.id),
            restype=_objc.BOOL,
        )

    with pytest.raises(macos.PermissionDeniedError):
        macos.pdf.text(locked)
    with pytest.raises(macos.PermissionDeniedError, match="wrong password"):
        macos.pdf.text(locked, password="nope")
    assert macos.pdf.text(locked, password="1234") == "Secret page"

    merged = macos.pdf.merge([locked, document], tmp_path / "merged.pdf", password="1234")
    assert macos.pdf.page_count(merged) == 2
    assert macos.pdf.text(merged).startswith("Secret page")  # the result isn't encrypted


def _paper_photo(angle=12):
    """A 300x420 sheet with lines of "text", turned by ``angle`` degrees, on a dark desk."""
    import math

    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def pixel(x, y):
        # (u, v): the point in the sheet's own coordinates, from its centre.
        u = (x - 240) * cos + (y - 320) * sin
        v = -(x - 240) * sin + (y - 320) * cos
        if abs(u) < 150 and abs(v) < 210:
            is_text = -120 < u < 110 and v < 150 and int(v + 180) % 30 < 8
            return (40, 40, 40) if is_text else (245, 245, 240)
        return (70, 45, 30)

    return _rgb_png(480, 640, pixel)


def _size(png):
    import struct

    return struct.unpack(">II", png[16:24])


def test_scan_document():
    scan = macos.vision.scan_document(_paper_photo())

    assert scan is not None
    width, height = _size(scan)
    assert abs(width - 300) < 15 and abs(height - 420) < 15  # the sheet alone, straightened
    assert macos.vision.scan_document(macos.image.qr_code("not a sheet of paper")) is None


def test_smart_crop():
    photo = _paper_photo()

    assert _size(macos.vision.smart_crop(photo, 200, 100)) == (200, 100)
    assert _size(macos.vision.smart_crop(photo, 100, 300)) == (100, 300)
    # Never scaled up: the largest 2:1 crop of a 480x640 image is 480x240.
    assert _size(macos.vision.smart_crop(photo, 2000, 1000)) == (480, 240)


def test_image_distance_and_duplicates(tmp_path):
    # Feature prints need real, detailed photos: use the wallpapers.
    pictures = sorted(Path("/System/Library/Desktop Pictures").glob("*.heic"))
    if len(pictures) < 2:
        pytest.skip("the desktop pictures aren't installed")
    first, other = pictures[0], pictures[-1]
    copy = macos.image.resize(first, tmp_path / "copy.jpg", width=1200)

    assert macos.vision.image_distance(first, copy) < 0.3 < macos.vision.image_distance(first, other)
    assert macos.vision.duplicates([first, other, copy]) == [[first, copy]]


def test_image_metadata_round_trip(tmp_path):
    from macos import _cf

    source = tmp_path / "plain.png"
    source.write_bytes(_png(40, 20))
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


def test_pdf_from_images(tmp_path, capfd):
    import ctypes

    from macos import _cf

    photo = tmp_path / "photo.png"
    photo.write_bytes(_png(40, 20))
    # The same picture, stored sideways with EXIF orientation 6, as phones do.
    portrait = tmp_path / "portrait.jpg"
    io = macos.image._io()
    with _cf.owned(macos.image._source(photo)) as source, _cf.owned(_cf.from_python({"Orientation": 6})) as options:
        macos.image._write(portrait, "public.jpeg", lambda d: io.CGImageDestinationAddImageFromSource(d, source, 0, options))
    url = "https://github.com/JeanExtreme002/pymacos"

    document = macos.pdf.from_images([photo, portrait, macos.image.qr_code(url, size=300)], tmp_path / "scan.pdf")

    assert macos.pdf.page_count(document) == 3
    with macos.pdf._open(document) as opened:
        sizes = []
        for number in (1, 2):
            bounds = _objc.send(
                macos.pdf._page(opened, number), "boundsForBox:", 0, argtypes=(ctypes.c_long,), restype=_objc.CGRect
            )
            sizes.append((bounds.size.width, bounds.size.height))
    assert sizes == [(40, 20), (20, 40)]  # each page is its picture, upright
    found = macos.vision.barcodes(macos.pdf.render(document, page=3))
    assert [code.payload for code in found] == [url]
    # PDFKit logged "CoreGraphics PDF has logged an error" for images without an orientation.
    assert "CoreGraphics" not in capfd.readouterr().err
    with pytest.raises(ValueError):
        macos.pdf.from_images([b"not an image"], tmp_path / "junk.pdf")
    assert not (tmp_path / "junk.pdf").exists()


def _halves(tmp_path):
    """A 40x20 PNG: red on the left half, blue on the right."""
    path = tmp_path / "halves.png"
    path.write_bytes(_rgb_png(40, 20, lambda x, y: (255, 0, 0) if x < 20 else (0, 0, 255)))
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
    assert _size(macos.vision.smart_crop(portrait, 20, 40)) == (20, 40)


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


def test_pdf_metadata_rotate_and_encrypt(tmp_path):
    import ctypes

    document = _text_pdf(tmp_path, ["Page one says hello", "Page two says ola"])

    details = macos.pdf.metadata(document)
    assert details.created is not None and details.created.tzinfo is not None
    assert details.keywords == []

    # Rotating in place is safe: the output replaces the input only once written.
    assert macos.pdf.rotate(document, 90, document, pages=[2]) == document
    macos.pdf.rotate(document, -180, document)
    with macos.pdf._open(document) as opened:
        rotations = [_objc.send(macos.pdf._page(opened, n), "rotation", restype=ctypes.c_long) for n in (1, 2)]
    assert rotations == [180, 270]

    locked = macos.pdf.encrypt(document, tmp_path / "locked.pdf", "s3cret")
    with pytest.raises(macos.PermissionDeniedError):
        macos.pdf.text(locked)
    assert macos.pdf.text(locked, password="s3cret", pages=[1]) == "Page one says hello"
    changed = macos.pdf.encrypt(locked, tmp_path / "changed.pdf", "other", current_password="s3cret")
    assert macos.pdf.page_count(changed, password="other") == 2


_PARROT = Path("/Library/User Pictures/Animals/Parrot.heic")


def test_remove_background():
    import struct

    if not _PARROT.exists():
        pytest.skip("the sample user pictures aren't installed")
    try:
        cutout = macos.vision.remove_background(_PARROT)
    except macos.NotSupportedError:
        pytest.skip("needs macOS 14")

    width, height, _, color_type = struct.unpack(">IIBB", cutout[16:26])
    assert color_type == 6  # RGBA: the background is transparent
    cropped = macos.vision.remove_background(_PARROT, crop=True)
    cropped_width, cropped_height = struct.unpack(">II", cropped[16:24])
    assert cropped_width <= width and cropped_height <= height
    assert macos.vision.remove_background(macos.image.qr_code("no subject here")) is None


def test_animals_without_any():
    assert macos.vision.animals(macos.image.qr_code("no pets")) == []


def test_audio_devices():
    outputs = macos.audio.outputs()
    if not outputs:
        pytest.skip("no audio output device")
    assert all(device.is_output and device.name and device.uid for device in outputs)
    assert all(device.is_input for device in macos.audio.inputs())

    current = macos.audio.default_output()
    assert current in outputs
    assert macos.audio.set_output(current) == current  # switching to the same device changes nothing
    assert macos.audio.default_output() == current


def test_similarity_and_embeddings():
    # Two words are too short to detect their language: say it.
    assert macos.language.similarity("car", "automobile", language="en") > macos.language.similarity(
        "car", "banana", language="en"
    )
    try:  # macOS only has the models for the languages it uses (CI runners: English)
        assert macos.language.similarity("carro", "automóvel", language="pt") > macos.language.similarity(
            "carro", "banana", language="pt"
        )
    except macos.NotSupportedError:
        pass
    question = "How do I change my password?"
    assert macos.language.similarity(question, "I forgot the password of my account") > macos.language.similarity(
        question, "What time does the store open?"
    )
    vector = macos.language.embedding("I like dogs", language="en")
    assert len(vector) > 100 and vector == macos.language.embedding("I like dogs", language="en")


def test_entities():
    found = macos.language.entities("Yesterday Tim Cook visited New York with engineers from Apple.")
    assert ("Tim Cook", "person", 10) in [(entity.text, entity.kind, entity.start) for entity in found]
    assert "New York" in [entity.text for entity in found if entity.kind == "place"]
    assert macos.language.entities("   ") == []

    try:  # accents and positions in a non-English text, where the model is installed
        found = macos.language.entities("Tim Cook visitou São Paulo com a Apple ontem 🙂.", language="pt")
    except macos.NotSupportedError:
        return
    assert ("São Paulo", "place", 17) in [(entity.text, entity.kind, entity.start) for entity in found]


def test_entities_without_the_language_model():
    with pytest.raises(macos.NotSupportedError):
        macos.language.entities("東京でティム・クックに会いました", language="ja")


def test_sound():
    import time

    assert "Glass" in macos.sound.names()
    start = time.monotonic()
    macos.sound.play("Tink", volume=0.0)  # silent
    assert time.monotonic() - start > 0.1  # waited for the sound to end
    with pytest.raises(ValueError):
        macos.sound.play("Definitely Not A Sound")


def test_network():
    import re

    assert isinstance(macos.network.is_online(), bool)
    address = macos.network.ip()
    assert address is None or re.fullmatch(r"\d+\.\d+\.\d+\.\d+", address)
    try:
        assert isinstance(macos.network.wifi_power(), bool)
    except macos.NotSupportedError:
        pass  # no Wi-Fi, as on some CI runners


def test_appearance_wait_for_change_times_out():
    with pytest.raises(TimeoutError):
        macos.appearance.wait_for_change(timeout=0.3, interval=0.1)


def test_keywords():
    text = "The new MacBook Pro has amazing battery life and the displays are gorgeous."

    assert macos.language.keywords(text, language="en") == ["MacBook", "Pro", "battery", "life", "displays"]
    assert "display" in macos.language.keywords(text, language="en", lemmas=True)
    assert "has" in macos.language.keywords(text, language="en", verbs=True)
    assert macos.language.keywords("   ") == []
    with pytest.raises(macos.NotSupportedError):
        macos.language.keywords("東京でティム・クックに会いました", language="ja")


def test_mouse_position_is_on_a_display():
    x, y = macos.mouse.position()

    assert isinstance(x, float) and isinstance(y, float)
    left = min(display.x for display in macos.screen.displays())
    top = min(display.y for display in macos.screen.displays())
    right = max(display.x + display.width for display in macos.screen.displays())
    bottom = max(display.y + display.height for display in macos.screen.displays())
    assert left <= x <= right and top <= y <= bottom


def test_keyboard_and_mouse_permission():
    if macos.mouse.has_permission():
        # Moving the pointer where it already is changes nothing.
        macos.mouse.move(*macos.mouse.position())
    else:
        # The events would be dropped silently: better to say so.
        with pytest.raises(macos.PermissionDeniedError):
            macos.keyboard.press("shift")
        with pytest.raises(macos.PermissionDeniedError):
            macos.mouse.move(*macos.mouse.position())
    assert macos.keyboard.has_permission() == macos.mouse.has_permission()


def test_display_brightness():
    try:
        current = macos.screen.brightness()
    except macos.NotSupportedError:
        pytest.skip("no display with a brightness macOS controls")
    assert 0.0 <= current <= 1.0
    macos.screen.set_brightness(current)  # the same value: nothing changes
    assert abs(macos.screen.brightness() - current) < 0.01


def test_keyboard_backlight():
    try:
        current = macos.keyboard.brightness()
    except macos.NotSupportedError:
        pytest.skip("no keyboard backlight")
    automatic = macos.keyboard.auto_brightness()
    assert 0.0 <= current <= 1.0
    macos.keyboard.set_brightness(current)
    macos.keyboard.set_auto_brightness(automatic)
    assert macos.keyboard.auto_brightness() == automatic


def test_bluetooth():
    try:
        on = macos.bluetooth.power()
    except macos.NotSupportedError:
        pytest.skip("no Bluetooth")
    assert isinstance(on, bool)
    found = macos.bluetooth.devices()
    assert all(isinstance(device, macos.bluetooth.Device) and device.address for device in found)
    assert len({device.address for device in found}) == len(found)


def test_keyboard_layouts():
    enabled = macos.keyboard.layouts()
    current = macos.keyboard.layout()

    assert enabled and all(isinstance(name, str) and name for name in enabled)
    if current in enabled:  # an input method can be current without being a layout
        assert macos.keyboard.set_layout(current) == current  # the same layout: nothing changes
        assert macos.keyboard.layout() == current
    with pytest.raises(ValueError, match="no enabled keyboard layout"):
        macos.keyboard.set_layout("No Such Layout {}".format(uuid.uuid4()))


def test_night_shift():
    try:
        on = macos.screen.night_shift()
    except macos.NotSupportedError:
        pytest.skip("no Night Shift")
    macos.screen.set_night_shift(on)  # the same state: nothing changes
    assert macos.screen.night_shift() == on


@pytest.mark.skipif(bool(os.environ.get("CI")), reason="the Automation prompt would block a CI runner")
def test_set_mode_to_the_current_mode():
    current = macos.appearance.mode()

    macos.appearance.set_mode(current)

    assert macos.appearance.mode() == current


def test_thermal_state_and_lid():
    assert macos.system.thermal_state() in ("nominal", "fair", "serious", "critical")
    try:
        assert isinstance(macos.system.lid_closed(), bool)
    except macos.NotSupportedError:
        pass  # a desktop Mac


def test_camera_microphone_and_power_state():
    assert isinstance(macos.system.camera_in_use(), bool)
    assert isinstance(macos.system.microphone_in_use(), bool)
    assert isinstance(macos.power.low_power_mode(), bool)
    assert isinstance(macos.keyboard.caps_lock(), bool)


def test_microphone_volume_and_mute():
    if macos.audio.default_input() is None:
        pytest.skip("no microphone")
    try:
        volume = macos.audio.input_volume()
    except macos.NotSupportedError:
        pytest.skip("the microphone has no adjustable volume")
    assert 0.0 <= volume <= 1.0
    macos.audio.set_input_volume(volume)  # the same value: nothing changes
    assert abs(macos.audio.input_volume() - volume) < 0.01
    try:
        muted = macos.audio.input_muted()
    except macos.NotSupportedError:
        return
    macos.audio.mute_input(muted)
    assert macos.audio.input_muted() == muted


def test_true_tone_lock_and_sleep_state():
    try:
        on = macos.screen.true_tone()
    except macos.NotSupportedError:
        on = None
    if on is not None:
        macos.screen.set_true_tone(on)  # the same state: nothing changes
        assert macos.screen.true_tone() == on
    assert isinstance(macos.screen.is_locked(), bool)
    assert macos.screen.is_asleep() is False  # the tests run on a display that is on


def test_finder_aliases(tmp_path):
    original = tmp_path / "report.pdf"
    original.write_text("x")
    folder = tmp_path / "Folder"
    folder.mkdir()

    alias = macos.finder.make_alias(original)
    assert alias == tmp_path / "report.pdf alias"
    assert macos.finder.is_alias(alias) and not macos.finder.is_alias(original)
    assert macos.finder.resolve_alias(alias).name == "report.pdf"
    assert macos.finder.resolve_alias(original) == original  # not an alias: as it is
    # Python itself sees a plain file.
    assert Path(os.path.realpath(alias)).name == "report.pdf alias"

    inside = macos.finder.make_alias(original, folder)
    assert inside == folder / "report.pdf alias"
    assert macos.finder.resolve_alias(macos.finder.make_alias(folder, tmp_path / "To folder")).name == "Folder"
    assert macos.finder.resolve_alias(macos.finder.make_alias(alias, tmp_path / "Alias of alias")).name == "report.pdf"
    link = tmp_path / "link"
    link.symlink_to(alias)
    assert not macos.finder.is_alias(link)
    assert macos.finder.resolve_alias(link).name == "report.pdf"

    # A disk has no name of its own: the alias takes the one Finder shows.
    disk = macos.finder.make_alias("/", tmp_path)
    assert disk.name.endswith(" alias") and disk.name != " alias"
    assert macos.finder.resolve_alias(disk) == Path("/")

    # An alias follows its original when it's moved and renamed...
    original.rename(folder / "moved.pdf")
    assert macos.finder.resolve_alias(alias).name == "moved.pdf"
    # ...but not when it's deleted.
    (folder / "moved.pdf").unlink()
    with pytest.raises(FileNotFoundError, match="original of the alias"):
        macos.finder.resolve_alias(alias)


_WALLPAPER_MOVIE = Path("/System/Library/Desktop Pictures/.wallpapers/Sequoia Sunrise/Sequoia Sunrise.mov")


@pytest.fixture
def movie():
    if not _WALLPAPER_MOVIE.exists():
        pytest.skip("the video wallpapers aren't installed")
    return _WALLPAPER_MOVIE


def test_video_info_frame_and_convert(movie, tmp_path):
    import struct

    details = macos.video.info(movie)
    assert details.duration > 10 and details.width > details.height > 0 and details.codec

    thumbnail = macos.video.frame(movie, at=2.0, size=320)
    assert max(struct.unpack(">II", thumbnail[16:24])) == 320
    with pytest.raises(ValueError, match="past the end"):
        macos.video.frame(movie, at=details.duration + 10)

    clip = macos.video.convert(movie, tmp_path / "clip.mp4", height=480, duration=1)
    small = macos.video.info(clip)
    assert (small.codec, round(small.duration)) == ("h264", 1)
    assert small.width <= 640 and small.height <= 480
    with pytest.raises(ValueError, match="no sound"):
        macos.video.convert(clip, tmp_path / "sound.m4a")


def test_video_convert_keeps_only_the_sound(tmp_path):
    import subprocess

    speech = tmp_path / "speech.aiff"
    subprocess.run(["say", "-o", str(speech), "hello"], check=True)

    sound = macos.video.convert(speech, tmp_path / "speech.m4a")

    details = macos.video.info(sound)
    assert details.has_audio and details.width == 0 and details.duration > 0


def test_screen_record(tmp_path):
    if not macos.screen.has_permission():
        pytest.skip("no Screen Recording permission")
    target = tmp_path / "screen.mov"
    try:
        macos.screen.record(target, 1, region=(0, 0, 160, 100))
        details = macos.video.info(target)
        assert details.duration > 0 and details.width >= 160
    finally:
        target.unlink(missing_ok=True)  # don't keep a picture of the screen around


@pytest.fixture
def test_window():
    """A window of our own, in a helper process, to move around without touching the user's."""
    import subprocess
    import sys

    if not macos.windows.has_permission():
        pytest.skip("no Accessibility permission")
    front = macos.windows.focused()
    title = "pymacos test {}".format(uuid.uuid4().hex[:8])
    helper = Path(__file__).with_name("_window_app.py")
    process = subprocess.Popen([sys.executable, str(helper), title, "20"], stdout=subprocess.PIPE, text=True)
    try:
        process.stdout.readline()
        app = next(app for app in macos.apps.running(include_background=True) if app.pid == process.pid)
        for _ in range(20):
            found = macos.windows.list(app, title=title)
            if found:
                break
            time.sleep(0.1)
        yield found[0]
    finally:
        process.kill()
        process.wait()
        if front is not None:
            try:
                front.focus()  # give the focus back
            except macos.MacOSError:
                pass


def test_windows(test_window):
    window = test_window

    window.set_frame(60, 80, 420, 300)
    time.sleep(0.2)
    assert window.frame == (60, 80, 420, 300)
    window.move(100, 120)
    window.resize(360, 260)
    time.sleep(0.2)
    assert (window.position, window.size) == ((100, 120), (360, 260))

    window.minimize()
    time.sleep(0.8)
    assert window.minimized
    window.restore()
    time.sleep(0.8)
    assert not window.minimized

    window.focus()
    for _ in range(20):
        if macos.windows.focused() == window:
            break
        time.sleep(0.1)
    else:
        # The user (or another app) may have taken the focus meanwhile: the
        # window must at least be its app's main one.
        from macos import _cf

        main = window._read("AXMain")
        with _cf.owned(main):
            assert _cf.to_bool(main)
    assert window in macos.windows.list()

    window.close()
    time.sleep(0.5)
    with pytest.raises(macos.MacOSError):
        window.title


def test_hotkeys():
    import threading

    if not (macos.hotkeys.has_permission() and macos.keyboard.has_permission()):
        pytest.skip("needs the Input Monitoring and Accessibility permissions")
    combination = "ctrl+option+cmd+f19"  # no app uses it
    calls = []

    def press_twice():
        for _ in range(2):
            macos.keyboard.press(combination)
            time.sleep(0.2)

    macos.hotkeys.register(combination, lambda: calls.append(1))
    try:
        threading.Timer(0.3, press_twice).start()
        macos.hotkeys.run(timeout=1.5)
        assert calls == [1, 1]
    finally:
        macos.hotkeys.unregister(combination)

    threading.Timer(0.3, lambda: macos.keyboard.press(combination)).start()
    assert macos.hotkeys.wait(combination, timeout=3) is True
    assert macos.hotkeys.wait(combination, timeout=0.3) is False


def test_now_playing_never_opens_the_player():
    running = {app.name for app in macos.apps.running()}

    track = macos.music.now_playing()

    assert track is None or track.app in macos.music.PLAYERS
    assert {app.name for app in macos.apps.running()} & set(macos.music.PLAYERS) == running & set(macos.music.PLAYERS)


def test_horizon_and_straighten(movie, tmp_path):
    frame = tmp_path / "sunrise.png"
    frame.write_bytes(macos.video.frame(movie, at=20))
    tilt = macos.vision.horizon(frame)
    if tilt is None:
        pytest.skip("Vision doesn't see this frame's horizon here")

    level = macos.image.straighten(frame, tmp_path / "level.png")

    assert macos.vision.horizon(level) is None  # level now
    original, fixed = macos.image.info(frame), macos.image.info(level)
    assert fixed.width < original.width  # cropped, so no empty corners
    assert abs(fixed.width / fixed.height - original.width / original.height) < 0.01
    assert macos.vision.horizon(macos.image.qr_code("no horizon")) is None


def test_pdf_watermark_and_compress(tmp_path):
    document = _text_pdf(tmp_path, ["Page one says hello", "Page two says ola"])
    macos.pdf.rotate(document, 90, document, pages=[2])

    marked = macos.pdf.watermark(document, "CONFIDENTIAL", tmp_path / "marked.pdf", color="#d00000")

    assert macos.pdf.page_count(marked) == 2
    assert macos.pdf.text(marked, pages=[1]).split("\n") == ["Page one says hello", "CONFIDENTIAL"]
    import struct

    width, height = struct.unpack(">II", macos.pdf.render(marked, page=2, size=400)[16:24])
    assert width > height  # the turned page still shows turned

    # Noise: what a scan or photo looks like to a compressor.
    noisy = tmp_path / "noise.png"
    noisy.write_bytes(_rgb_png(800, 600, lambda x, y: ((x * 7919 + y * 104729) % 251, (x * y) % 247, (x + y * 31) % 241)))
    photos = macos.pdf.from_images([noisy], tmp_path / "photo.pdf")
    smaller = macos.pdf.compress(photos, tmp_path / "small.pdf")
    assert smaller.stat().st_size < photos.stat().st_size / 2
    assert macos.pdf.page_count(smaller) == 1
