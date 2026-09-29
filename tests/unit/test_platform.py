"""Unit tests for platform guards: NotSupportedError outside macOS."""

import sys
from datetime import datetime

import pytest

import macos
from macos import _system


def test_missing_command_raises_not_supported(fake_run, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(_system.subprocess, "run", missing)

    with pytest.raises(macos.NotSupportedError, match="'say' command was not found"):
        macos.say("x")


def test_other_platforms_raise_not_supported(monkeypatch):
    monkeypatch.setattr(_system.sys, "platform", "linux")

    with pytest.raises(macos.NotSupportedError, match="only works on macOS"):
        macos.say("x")


@pytest.mark.skipif(sys.platform == "darwin", reason="checks behaviour outside macOS")
@pytest.mark.parametrize(
    "call",
    [
        lambda: macos.notify("x"),
        lambda: macos.say("x"),
        lambda: macos.say("x", wait=False),
        lambda: macos.speech.voices(),
        lambda: macos.screenshot(),
        lambda: macos.screen.has_permission(),
        lambda: macos.clipboard.copy("x"),
        lambda: macos.clipboard.paste(),
        lambda: macos.appearance.is_dark(),
        lambda: macos.apps.running(),
        lambda: macos.apps.frontmost(),
        lambda: macos.apps.get("Safari"),
        lambda: macos.apps.open("Safari"),
        lambda: macos.apps.App("Safari", None, 1, None).quit(),
        lambda: macos.keychain.get("service", "account"),
        lambda: macos.keychain.set("service", "account", "password"),
        lambda: macos.power.battery(),
        lambda: macos.power.keep_awake().__enter__(),
        lambda: macos.shortcuts.list(),
        lambda: macos.shortcuts.run("Shortcut"),
        lambda: macos.finder.tags(__file__),
        lambda: macos.finder.trash(__file__),
        lambda: macos.finder.reveal(__file__),
        lambda: macos.clipboard.copy_image(b"image"),
        lambda: macos.clipboard.paste_image(),
        lambda: macos.notifications.is_allowed(),
        lambda: macos.volume.get(),
        lambda: macos.volume.set(10),
        lambda: macos.volume.mute(),
        lambda: macos.spotlight.search("kind:pdf"),
        lambda: macos.spotlight.search_name("report"),
        lambda: macos.spotlight.metadata(__file__),
        lambda: macos.dialog.alert("x"),
        lambda: macos.dialog.confirm("x"),
        lambda: macos.dialog.prompt("x"),
        lambda: macos.dialog.choose(["a"]),
        lambda: macos.dialog.choose_file(),
        lambda: macos.system.version(),
        lambda: macos.system.model_identifier(),
        lambda: macos.system.uptime(),
        lambda: macos.system.idle_time(),
        lambda: macos.screen.displays(),
        lambda: macos.power.sleep(),
        lambda: macos.keychain.accounts("service"),
        lambda: macos.say("x", output="speech.aiff"),
        lambda: macos.vision.text(b"image"),
        lambda: macos.vision.languages(),
        lambda: macos.screen.wallpaper(),
        lambda: macos.screen.set_wallpaper(__file__),
        lambda: macos.open("https://python.org"),
        lambda: macos.open_with(__file__, "Preview"),
        lambda: macos.apps.default_for("pdf"),
        lambda: macos.apps.default_browser(),
        lambda: macos.clipboard.copy_files([__file__]),
        lambda: macos.clipboard.paste_files(),
        lambda: macos.finder.thumbnail(__file__),
        lambda: macos.finder.is_alias(__file__),
        lambda: macos.finder.resolve_alias(__file__),
        lambda: macos.finder.make_alias(__file__, "elsewhere"),
        lambda: macos.video.info(__file__),
        lambda: macos.video.frame(__file__),
        lambda: macos.video.convert(__file__, "out.mp4"),
        lambda: macos.screen.record("out.mov", 1),
        lambda: macos.windows.list(),
        lambda: macos.windows.focused(),
        lambda: macos.windows.has_permission(),
        lambda: macos.hotkeys.run(timeout=0.1),
        lambda: macos.hotkeys.wait("f19", timeout=0.1),
        lambda: macos.hotkeys.has_permission(),
        lambda: macos.music.now_playing(),
        lambda: macos.music.play(),
        lambda: macos.vision.horizon(b"image"),
        lambda: macos.image.straighten(__file__, "out.png"),
        lambda: macos.pdf.watermark(__file__, "DRAFT", "out.pdf"),
        lambda: macos.pdf.compress(__file__, "out.pdf"),
        lambda: macos.pdf.grayscale(__file__, "out.pdf"),
        lambda: macos.video.to_gif(__file__, "out.gif"),
        lambda: macos.music.volume(),
        lambda: macos.music.set_volume(50),
        lambda: macos.music.seek(10),
        lambda: macos.camera.devices(),
        lambda: macos.camera.photo(),
        lambda: macos.camera.record("out.mov", 1),
        lambda: macos.camera.has_permission(),
        lambda: macos.camera.request_permission(),
        lambda: macos.audio.record("out.m4a", 1),
        lambda: macos.audio.input_level(),
        lambda: macos.audio.has_permission(),
        lambda: macos.audio.request_permission(),
        lambda: macos.system.volumes(),
        lambda: macos.system.eject("Backup"),
        lambda: macos.image.info(__file__),
        lambda: macos.image.convert(__file__, "out.png"),
        lambda: macos.image.qr_code("x"),
        lambda: macos.pdf.page_count(__file__),
        lambda: macos.pdf.text(__file__),
        lambda: macos.vision.barcodes(b"image"),
        lambda: macos.vision.classify(b"image"),
        lambda: macos.vision.faces(b"image"),
        lambda: macos.language.detect("Olá"),
        lambda: macos.language.sentiment("Olá"),
        lambda: macos.vision.remove_background(b"image"),
        lambda: macos.vision.animals(b"image"),
        lambda: macos.audio.outputs(),
        lambda: macos.audio.default_output(),
        lambda: macos.audio.set_output("Speakers"),
        lambda: macos.language.similarity("car", "automobile"),
        lambda: macos.language.embedding("hello"),
        lambda: macos.language.entities("Tim Cook"),
        lambda: macos.language.keywords("battery life"),
        lambda: macos.sound.play("Glass"),
        lambda: macos.sound.beep(),
        lambda: macos.sound.names(),
        lambda: macos.network.is_online(),
        lambda: macos.network.ip(),
        lambda: macos.network.wifi_power(),
        lambda: macos.network.set_wifi_power(True),
        lambda: macos.appearance.wait_for_change(timeout=0.1),
        lambda: macos.appearance.accent_color(),
        lambda: macos.image.metadata(__file__),
        lambda: macos.image.taken_at(__file__),
        lambda: macos.image.location(__file__),
        lambda: macos.image.strip_metadata(__file__, "out.jpg"),
        lambda: macos.pdf.from_images([__file__], "out.pdf"),
        lambda: macos.vision.scan_document(b"image"),
        lambda: macos.vision.image_distance(b"image", b"image"),
        lambda: macos.vision.duplicates([b"image", b"image"]),
        lambda: macos.vision.smart_crop(b"image", 100, 100),
        lambda: macos.system.fonts(),
        lambda: macos.screen.start_screensaver(),
        lambda: macos.image.set_taken_at(__file__, datetime(2024, 5, 1)),
        lambda: macos.image.set_location(__file__, 0.0, 0.0),
        lambda: macos.image.crop(__file__, "out.png", (0, 0, 1, 1)),
        lambda: macos.image.rotate(__file__, "out.png", 90),
        lambda: macos.image.flip(__file__, "out.png"),
        lambda: macos.image.blur_faces(__file__, "out.png"),
        lambda: macos.image.dominant_colors(__file__),
        lambda: macos.vision.best_shot([b"image"]),
        lambda: macos.pdf.metadata(__file__),
        lambda: macos.pdf.rotate(__file__, 90, "out.pdf"),
        lambda: macos.pdf.encrypt(__file__, "out.pdf", "secret"),
        lambda: macos.keyboard.type("x"),
        lambda: macos.keyboard.press("enter"),
        lambda: macos.keyboard.has_permission(),
        lambda: macos.keyboard.brightness(),
        lambda: macos.keyboard.set_brightness(0.5),
        lambda: macos.keyboard.auto_brightness(),
        lambda: macos.keyboard.set_auto_brightness(True),
        lambda: macos.mouse.position(),
        lambda: macos.mouse.move(1, 1),
        lambda: macos.mouse.click(),
        lambda: macos.mouse.drag(1, 1),
        lambda: macos.mouse.scroll(1),
        lambda: macos.screen.brightness(),
        lambda: macos.screen.set_brightness(0.5),
        lambda: macos.bluetooth.power(),
        lambda: macos.bluetooth.set_power(True),
        lambda: macos.bluetooth.devices(),
        lambda: macos.bluetooth.connect("AirPods"),
        lambda: macos.bluetooth.disconnect("AirPods"),
        lambda: macos.keyboard.hold("shift").__enter__(),
        lambda: macos.keyboard.layouts(),
        lambda: macos.keyboard.layout(),
        lambda: macos.keyboard.set_layout("ABC"),
        lambda: macos.screen.night_shift(),
        lambda: macos.screen.set_night_shift(True),
        lambda: macos.appearance.set_mode("dark"),
        lambda: macos.system.thermal_state(),
        lambda: macos.system.lid_closed(),
        lambda: macos.system.camera_in_use(),
        lambda: macos.system.microphone_in_use(),
        lambda: macos.power.low_power_mode(),
        lambda: macos.screen.lock(),
        lambda: macos.screen.true_tone(),
        lambda: macos.screen.set_true_tone(True),
        lambda: macos.screen.is_locked(),
        lambda: macos.screen.is_asleep(),
        lambda: macos.keyboard.caps_lock(),
        lambda: macos.audio.input_volume(),
        lambda: macos.audio.set_input_volume(0.5),
        lambda: macos.audio.input_muted(),
        lambda: macos.audio.mute_input(),
        lambda: macos.audio.info(__file__),
        lambda: macos.audio.convert(__file__, "out.m4a"),
        lambda: macos.audio.trim(__file__, "out.m4a", 1),
        lambda: macos.audio.concat([__file__], "out.m4a"),
        lambda: macos.audio.fade(__file__, "out.m4a", fade_in=1),
        lambda: macos.audio.gain(__file__, "out.m4a", 3),
        lambda: macos.audio.reverse(__file__, "out.m4a"),
        lambda: macos.audio.speed(__file__, "out.m4a", 1.5),
        lambda: macos.audio.classify(__file__),
        lambda: macos.audio.record_until_silence("out.m4a"),
        lambda: macos.image.enhance(__file__, "out.png"),
        lambda: macos.image.effect(__file__, "out.png", "noir"),
        lambda: macos.image.blur_background(__file__, "out.png"),
        lambda: macos.image.replace_background(__file__, __file__, "out.png"),
        lambda: macos.image.watermark(__file__, "out.png", "draft"),
        lambda: macos.image.contact_sheet([__file__], "out.png"),
        lambda: macos.vision.aesthetics(b"image"),
        lambda: macos.vision.body_pose(b"image"),
        lambda: macos.vision.hand_pose(b"image"),
        lambda: macos.video.trim(__file__, "out.mov", 1),
        lambda: macos.video.concat([__file__], "out.mov"),
        lambda: macos.video.speed(__file__, "out.mov", 2),
        lambda: macos.video.rotate(__file__, "out.mov", 90),
        lambda: macos.video.crop(__file__, "out.mov", (0, 0, 10, 10)),
        lambda: macos.video.reverse(__file__, "out.mov"),
        lambda: macos.video.mute(__file__, "out.mov"),
        lambda: macos.video.add_audio(__file__, __file__, "out.mov"),
        lambda: macos.video.add_language_track(__file__, __file__, "out.mov", "en"),
        lambda: macos.video.from_images([__file__], "out.mov"),
        lambda: macos.video.frames(__file__),
    ],
)
def test_every_feature_raises_not_supported_outside_macos(call):
    with pytest.raises(macos.NotSupportedError):
        call()


def test_missing_private_classes_are_not_supported(monkeypatch):
    from contextlib import nullcontext

    def missing(name):
        raise LookupError("Objective-C class {!r} is not loaded".format(name))

    monkeypatch.setattr(macos._objc, "cls", missing)
    monkeypatch.setattr(macos._objc, "autorelease_pool", nullcontext)
    for module in (macos.keyboard, macos.screen):
        monkeypatch.setattr(module, "private_framework", lambda name: None)
        monkeypatch.setattr(module, "framework", lambda name: None)

    with pytest.raises(macos.NotSupportedError, match="keyboard backlight"):
        macos.keyboard.brightness()
    with pytest.raises(macos.NotSupportedError, match="Night Shift"):
        macos.screen.night_shift()
    with pytest.raises(macos.NotSupportedError, match="True Tone"):
        macos.screen.true_tone()
