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
