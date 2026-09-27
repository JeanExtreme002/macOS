"""Tests against the real system. Skipped outside macOS."""

import os
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
    assert macos.appearance.mode() in ("dark", "light")
    assert macos.appearance.is_dark() == (macos.appearance.mode() == "dark")
    assert isinstance(macos.appearance.is_auto(), bool)


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


def _png(width=4, height=4):
    """A small valid PNG, so the image tests don't depend on screen access."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


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
