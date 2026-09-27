"""Unit tests for the command-backed features. They run on any platform."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import macos
from macos import _system, screen


def test_notify_passes_text_as_arguments(fake_run):
    macos.notify('say "hi" \\ end', title="T", sound="Glass")

    args = fake_run.args
    assert args[0] == "osascript"
    assert "display notification (item 1 of argv) with title (item 2 of argv) sound name (item 3 of argv)" in args
    assert args[-3:] == ['say "hi" \\ end', "T", "Glass"]


def test_notify_message_only(fake_run):
    macos.notify("hello")

    assert "display notification (item 1 of argv)" in fake_run.args
    assert fake_run.args[-1] == "hello"


def test_say_reads_text_from_stdin(fake_run):
    macos.say("-not an option", voice="Luciana", rate=180)

    assert fake_run.args == ["say", "-v", "Luciana", "-r", "180", "-f", "-"]
    assert fake_run.calls[-1]["input"] == "-not an option"


def test_voices_parses_names_with_spaces(fake_run):
    fake_run.stdout = (
        "Albert              en_US    # Hello! My name is Albert.\n"
        "Eddy (English (US)) en_US    # Hello! My name is Eddy.\n"
        "Luciana             pt_BR    # Olá, meu nome é Luciana.\n"
    )

    voices = macos.speech.voices()

    assert [v.name for v in voices] == ["Albert", "Eddy (English (US))", "Luciana"]
    assert voices[2].locale == "pt_BR"
    assert voices[2].sample == "Olá, meu nome é Luciana."


def test_screenshot_arguments(fake_run, tmp_path):
    target = macos.screenshot(tmp_path / "shot.JPG", region=(1, 2, 30, 40), display=2, cursor=True, check_permission=False)

    assert target == (tmp_path / "shot.JPG").resolve()
    assert fake_run.args == ["screencapture", "-x", "-t", "jpg", "-C", "-R1,2,30,40", "-D2", str(target)]


def test_screenshot_defaults_to_a_temporary_png(fake_run):
    target = macos.screenshot(check_permission=False)
    try:
        assert target.suffix == ".png"
        assert fake_run.args[-1] == str(target)
    finally:
        target.unlink()


def test_screenshot_rejects_unknown_format(fake_run, tmp_path):
    with pytest.raises(ValueError, match="unsupported image format"):
        macos.screenshot(tmp_path / "shot.bmp", check_permission=False)


def test_screenshot_raises_without_permission(fake_run, monkeypatch, tmp_path):
    monkeypatch.setattr(screen, "has_permission", lambda: False)

    with pytest.raises(macos.PermissionDeniedError, match="Screen Recording"):
        macos.screenshot(tmp_path / "shot.png")
    assert fake_run.calls == []


def test_failed_command_raises_command_error(fake_run):
    fake_run.returncode = 1
    fake_run.stderr = "execution error\n"

    with pytest.raises(macos.CommandError) as info:
        macos.notify("x")

    assert info.value.returncode == 1
    assert info.value.stderr == "execution error"
    assert isinstance(info.value, macos.MacOSError)


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


@pytest.mark.parametrize(
    "error",
    [
        macos.CommandError(["say", "-v", "x"], 1, "boom\n"),
        macos.KeychainError(-25300, "The item could not be found."),
        macos.KeychainError(-25300),
    ],
)
def test_errors_survive_pickling(error):
    import pickle

    copy = pickle.loads(pickle.dumps(error))

    assert type(copy) is type(error)
    assert str(copy) == str(error)
    assert vars(copy) == vars(error)


def test_error_messages():
    assert str(macos.CommandError(["say"], 1, "boom\n")) == "'say' exited with status 1: boom"
    assert str(macos.KeychainError(-25300)) == "Keychain error (OSStatus -25300)"


def test_permission_error_is_also_the_builtin():
    assert issubclass(macos.PermissionDeniedError, PermissionError)
    assert issubclass(macos.AppNotFoundError, LookupError)


def test_notify_ends_options_before_user_text(fake_run):
    macos.notify("-5 degrees", title="-e")

    args = fake_run.args
    assert args[-3:] == ["--", "-5 degrees", "-e"]


def test_say_without_waiting_reaps_the_process(fake_run, monkeypatch):
    started = []

    class FakeStdin:
        def __init__(self):
            self.data, self.closed = b"", False

        def write(self, data):
            self.data += data

        def close(self):
            self.closed = True

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.args = args
            self.stdin = FakeStdin()
            self.waited = False
            started.append(self)

        def wait(self):
            self.waited = True

    monkeypatch.setattr(macos.speech.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(macos.speech.threading, "Thread", _ImmediateThread)

    macos.say("-hi", wait=False)

    process = started[0]
    assert process.args == ["say", "-f", "-"]
    # The text is written and stdin closed before say() returns.
    assert process.stdin.data == b"-hi" and process.stdin.closed
    assert process.waited


def test_say_without_waiting_reports_a_missing_command(fake_run, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(macos.speech.subprocess, "Popen", missing)

    with pytest.raises(macos.NotSupportedError):
        macos.say("x", wait=False)


def test_failed_screenshot_removes_its_temporary_file(fake_run, monkeypatch, tmp_path):
    fake_run.returncode = 1
    monkeypatch.setattr(screen.tempfile, "tempdir", str(tmp_path))

    with pytest.raises(macos.CommandError):
        macos.screenshot(display=9, check_permission=False)

    assert list(tmp_path.iterdir()) == []


# Outside macOS the platform guard (NotSupportedError) rightly fires first.
@pytest.mark.skipif(sys.platform != "darwin", reason="loads the Security framework")
@pytest.mark.parametrize("service, account", [("svc\0x", "alice"), ("svc", "al\0ice")])
def test_keychain_rejects_nul_characters(service, account):
    with pytest.raises(ValueError, match="NUL"):
        macos.keychain.get(service, account)


class _ImmediateThread:
    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


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
    ],
)
def test_every_feature_raises_not_supported_outside_macos(call):
    with pytest.raises(macos.NotSupportedError):
        call()


class _Commands:
    """A fake ``subprocess.run`` that answers each command from a table."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, args, **kwargs):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["shortcuts", "run"]:
            for flag, path in zip(args, args[1:]):
                if flag == "--input-path" and path.endswith(".txt"):
                    self.text_input = open(path, encoding="utf-8").read()
        key = " ".join(args[:3]) if args[:2] == ["shortcuts", "list"] else args[1]
        returncode, stdout, stderr = self.answers.get(key, (0, "", ""))
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)


@pytest.fixture
def commands(fake_run, monkeypatch):
    fake = _Commands({})
    monkeypatch.setattr(_system.subprocess, "run", fake)
    return fake


def test_shortcut_text_input_goes_through_a_temporary_file(commands):
    commands.answers["run"] = (0, "Hello\n", "")

    assert macos.shortcuts.run("Translate", input="Olá") == "Hello"

    args = commands.calls[-1]
    assert args[:3] == ["shortcuts", "run", "Translate"]
    assert commands.text_input == "Olá"
    assert not os.path.exists(args[args.index("--input-path") + 1])


def test_shortcut_file_inputs_and_output(commands, tmp_path):
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    first.touch()
    second.touch()

    assert macos.shortcuts.run("Make GIF", input=[first, second], output=tmp_path / "out.gif") is None
    assert commands.calls[-1] == [
        "shortcuts", "run", "Make GIF",
        "--input-path", str(first), "--input-path", str(second),
        "--output-path", str(tmp_path / "out.gif"),
    ]


def test_shortcut_missing_input_file(commands, tmp_path):
    with pytest.raises(FileNotFoundError):
        macos.shortcuts.run("Resize", input=tmp_path / "missing.png")
    assert commands.calls == []


def test_shortcut_not_found_checks_the_list(commands):
    commands.answers["run"] = (1, "", "Error: Não foi possível encontrar o atalho")  # localized
    commands.answers["shortcuts list --show-identifiers"] = (0, "Other (1234-ABCD)\n", "")

    with pytest.raises(macos.ShortcutNotFoundError) as info:
        macos.shortcuts.run("Missing")
    assert isinstance(info.value, LookupError)


def test_shortcut_failure_of_an_existing_shortcut_is_a_command_error(commands):
    commands.answers["run"] = (1, "", "Error: something else")
    commands.answers["shortcuts list --show-identifiers"] = (0, "Broken (1234-ABCD)\n", "")

    with pytest.raises(macos.CommandError) as info:
        macos.shortcuts.run("Broken")
    assert not isinstance(info.value, macos.ShortcutNotFoundError)


def test_shortcut_list(commands):
    commands.answers["shortcuts list --folder-name"] = (0, "One\nTwo\n\n", "")

    assert macos.shortcuts.list(folder="Work") == ["One", "Two"]
    assert commands.calls[-1] == ["shortcuts", "list", "--folder-name", "Work"]


def test_finder_reveal(fake_run, tmp_path):
    macos.finder.reveal(tmp_path)

    assert fake_run.args == ["open", "-R", str(tmp_path)]


def test_notify_refuses_when_notifications_are_off(fake_run, monkeypatch):
    monkeypatch.setattr(macos.notifications, "is_allowed", lambda: False)

    with pytest.raises(macos.PermissionDeniedError, match="Script Editor"):
        macos.notify("x")
    assert fake_run.calls == []


def test_notify_checks_again_after_the_first_notification(fake_run, monkeypatch):
    answers = iter([None, False])  # unknown before posting, blocked right after
    monkeypatch.setattr(macos.notifications, "is_allowed", lambda: next(answers))

    with pytest.raises(macos.PermissionDeniedError):
        macos.notify("x")
    assert fake_run.args[0] == "osascript"


def test_notify_can_skip_the_check(fake_run, monkeypatch):
    monkeypatch.setattr(macos.notifications, "is_allowed", lambda: False)

    macos.notify("x", check_permission=False)
    assert fake_run.args[0] == "osascript"


@pytest.mark.parametrize(
    "apps, expected",
    [
        ([{"bundle-id": "com.apple.ScriptEditor2", "flags": 41951246}], True),
        ([{"bundle-id": "com.apple.ScriptEditor2", "flags": 8206}], False),
        ([{"bundle-id": "com.other.app", "flags": 41951246}], None),
        ([], None),
    ],
)
def test_is_allowed_reads_the_notification_settings(monkeypatch, apps, expected):
    import plistlib

    monkeypatch.setattr(_system.sys, "platform", "darwin")

    def fake(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, plistlib.dumps({"apps": apps}), b"")

    monkeypatch.setattr(macos.notifications.subprocess, "run", fake)

    assert macos.notifications.is_allowed() is expected


def test_is_allowed_is_unknown_when_the_settings_are_unreadable(monkeypatch):
    monkeypatch.setattr(_system.sys, "platform", "darwin")

    def fake(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, b"not a plist", b"")

    monkeypatch.setattr(macos.notifications.subprocess, "run", fake)

    assert macos.notifications.is_allowed() is None


@pytest.mark.parametrize("output, expected", [("88\n", 88), ("0\n", 0), ("missing value\n", None)])
def test_volume_get(fake_run, output, expected):
    fake_run.stdout = output

    assert macos.volume.get() == expected
    assert fake_run.args == ["osascript", "-e", "output volume of (get volume settings)"]


@pytest.mark.parametrize("output, expected", [("true\n", True), ("false\n", False), ("missing value\n", None)])
def test_volume_is_muted(fake_run, output, expected):
    fake_run.stdout = output

    assert macos.volume.is_muted() is expected


def test_volume_set_mute_unmute(fake_run):
    macos.volume.set(30)
    assert fake_run.args == ["osascript", "-e", "set volume output volume 30"]
    macos.volume.mute()
    assert fake_run.args == ["osascript", "-e", "set volume output muted true"]
    macos.volume.unmute()
    assert fake_run.args == ["osascript", "-e", "set volume output muted false"]


@pytest.mark.parametrize(
    "level, error",
    [(101, ValueError), (-1, ValueError), (True, TypeError), (50.5, TypeError), ("50", TypeError)],
)
def test_volume_set_rejects_bad_levels(level, error):
    with pytest.raises(error):
        macos.volume.set(level)


class _FakeMdfind:
    """Stands in for ``subprocess.Popen`` running mdfind."""

    instances = []

    def __init__(self, lines, returncode=0, stderr=""):
        self.lines, self.returncode_value, self.stderr_text = lines, returncode, stderr

    def __call__(self, args, **kwargs):
        import io

        self.args = list(args)
        self.stdout = iter(line + "\n" for line in self.lines)
        self.stdout = _Stream(self.stdout)
        self.stderr = io.StringIO(self.stderr_text)
        self.returncode = None
        self.killed = False
        return self

    def poll(self):
        return self.returncode

    def wait(self):
        if self.returncode is None:
            self.returncode = -9 if self.killed else self.returncode_value
        return self.returncode

    def kill(self):
        self.killed = True


class _Stream:
    def __init__(self, lines):
        self.lines, self.read_count = lines, 0

    def __iter__(self):
        for line in self.lines:
            self.read_count += 1
            yield line

    def close(self):
        pass


@pytest.fixture
def mdfind(monkeypatch):
    monkeypatch.setattr(_system.sys, "platform", "darwin")

    def install(lines, **kwargs):
        fake = _FakeMdfind(lines, **kwargs)
        monkeypatch.setattr(macos.spotlight.subprocess, "Popen", fake)
        return fake

    return install


def test_spotlight_search(mdfind, tmp_path):
    fake = mdfind(["/a/one.pdf", "", "/b/two.pdf"])

    assert macos.spotlight.search("kind:pdf", folder=tmp_path) == [Path("/a/one.pdf"), Path("/b/two.pdf")]
    assert fake.args == ["mdfind", "-onlyin", str(tmp_path.resolve()), "kind:pdf"]


def test_spotlight_limit_stops_reading(mdfind):
    fake = mdfind(["/{}".format(n) for n in range(100)])

    assert macos.spotlight.search("x", limit=2) == [Path("/0"), Path("/1")]
    assert fake.stdout.read_count == 2
    assert fake.killed


def test_spotlight_invalid_query(mdfind):
    mdfind(["Failed to create query for 'kMDItemFoo =='."], returncode=1)

    with pytest.raises(ValueError, match="not a valid Spotlight query"):
        macos.spotlight.search("kMDItemFoo ==")


def test_spotlight_limit_zero(mdfind):
    mdfind(["/a", "/b"])
    assert macos.spotlight.search("x", limit=0) == []

    mdfind(["Failed to create query for 'kMDItemFoo =='."], returncode=1)
    with pytest.raises(ValueError):
        macos.spotlight.search("kMDItemFoo ==", limit=0)


def test_spotlight_failure_is_a_command_error(mdfind):
    mdfind([], returncode=2, stderr="boom")

    with pytest.raises(macos.CommandError, match="boom"):
        macos.spotlight.search("x")


def test_spotlight_search_name_is_literal(mdfind):
    fake = mdfind([])

    macos.spotlight.search_name('a"b*c\\d')
    assert fake.args == ["mdfind", 'kMDItemFSName == "*a\\"b\\*c\\\\d*"cd']


def test_spotlight_missing_folder(mdfind, tmp_path):
    with pytest.raises(FileNotFoundError):
        macos.spotlight.search("x", folder=tmp_path / "missing")
    with pytest.raises(NotADirectoryError):
        macos.spotlight.search("x", folder=__file__)


def test_spotlight_metadata(monkeypatch, tmp_path):
    import plistlib
    from datetime import datetime

    monkeypatch.setattr(_system.sys, "platform", "darwin")
    target = tmp_path / "report.pdf"
    target.touch()
    created = datetime(2026, 1, 2, 3, 4, 5)

    def fake(args, **kwargs):
        assert args == ["mdls", "-plist", "-", str(target)]
        payload = plistlib.dumps({"kMDItemNumberOfPages": 3, "kMDItemFSCreationDate": created})
        return subprocess.CompletedProcess(args, 0, payload, b"")

    monkeypatch.setattr(macos.spotlight.subprocess, "run", fake)

    assert macos.spotlight.metadata(target) == {"kMDItemNumberOfPages": 3, "kMDItemFSCreationDate": created}
    with pytest.raises(FileNotFoundError):
        macos.spotlight.metadata(tmp_path / "missing")


def _script(args):
    """The AppleScript source of an osascript call (everything before "--")."""
    return "\n".join(args[i + 1] for i in range(args.index("--")) if args[i] == "-e")


def test_dialog_passes_text_as_arguments(fake_run):
    fake_run.stdout = "ok\nAlice\n"

    assert macos.dialog.prompt('Name? "quoted" -e', default="x", title="T", hidden=True) == "Alice"

    args = fake_run.args
    assert args[args.index("--") + 1:] == ['Name? "quoted" -e', "x", "T"]
    script = _script(args)
    assert "with hidden answer" in script and "Name?" not in script
    assert "activate" in script


@pytest.mark.parametrize("output, expected", [("ok\n", True), ("cancel\n", False), ("timeout\n", False)])
def test_dialog_confirm(fake_run, output, expected):
    fake_run.stdout = output

    assert macos.dialog.confirm("Delete?", ok="Delete", cancel="Keep", timeout=5) is expected
    assert "giving up after 5" in _script(fake_run.args)
    assert fake_run.args[-3:] == ["Delete?", "Delete", "Keep"]


def test_dialog_prompt_cancel_and_multiline(fake_run):
    fake_run.stdout = "cancel\n"
    assert macos.dialog.prompt("x") is None

    fake_run.stdout = "ok\nline 1\nline 2\n"
    assert macos.dialog.prompt("x") == "line 1\nline 2"


def test_dialog_choose(fake_run):
    fake_run.stdout = "ok\nPear\n"

    assert macos.dialog.choose(["Apple", "Pear"], prompt="Fruit?", default="Pear") == "Pear"
    assert fake_run.args[-4:] == ["Fruit?", "Pear", "Apple", "Pear"]

    fake_run.stdout = "cancel\n"
    assert macos.dialog.choose(["Apple"]) is None


@pytest.mark.parametrize(
    "options, default", [([], None), (["a\nb"], None), (["a"], "b")]
)
def test_dialog_choose_rejects_bad_options(options, default):
    with pytest.raises(ValueError):
        macos.dialog.choose(options, default=default)


def test_dialog_choose_files(fake_run, tmp_path):
    fake_run.stdout = "ok\n/a/one.pdf\n/b/two words.pdf\n"

    assert macos.dialog.choose_files(types=[".pdf", "public.image"], folder=tmp_path) == [
        Path("/a/one.pdf"),
        Path("/b/two words.pdf"),
    ]
    script = _script(fake_run.args)
    assert "with multiple selections allowed" in script and "of type fileTypes" in script
    assert fake_run.args[-2:] == ["pdf\npublic.image", str(tmp_path.resolve())]

    fake_run.stdout = "cancel\n"
    assert macos.dialog.choose_files() == []
    assert macos.dialog.choose_file() is None
    assert macos.dialog.choose_folder() is None


def test_dialog_rejects_bad_timeout():
    with pytest.raises(ValueError):
        macos.dialog.confirm("x", timeout=0)


def test_system_commands(fake_run):
    fake_run.stdout = "24G90\n"
    assert macos.system.build() == "24G90"
    assert fake_run.args == ["sw_vers", "-buildVersion"]

    fake_run.stdout = "My Mac\n"
    assert macos.system.computer_name() == "My Mac"
    assert fake_run.args == ["scutil", "--get", "ComputerName"]


def test_power_sleep_commands(fake_run):
    macos.power.sleep()
    assert fake_run.args == ["pmset", "sleepnow"]
    macos.power.sleep_display()
    assert fake_run.args == ["pmset", "displaysleepnow"]


def test_say_to_a_file(fake_run, tmp_path):
    target = macos.say("hi", output=tmp_path / "speech.WAV", wait=False)

    assert target == (tmp_path / "speech.WAV").resolve()
    assert fake_run.args == ["say", "-o", str(target), "--data-format=LEI16", "-f", "-"]


def test_say_rejects_unknown_audio_formats(fake_run, tmp_path):
    with pytest.raises(ValueError, match="unsupported audio format"):
        macos.say("hi", output=tmp_path / "speech.mp3")


def test_clipboard_wait_for_change(monkeypatch):
    counts = iter([1, 1, 1, 2])
    monkeypatch.setattr(macos.clipboard, "change_count", lambda: next(counts))
    monkeypatch.setattr(macos.clipboard, "paste", lambda: "new text")

    assert macos.clipboard.wait_for_change(interval=0.001) == "new text"


def test_clipboard_wait_for_change_times_out(monkeypatch):
    monkeypatch.setattr(macos.clipboard, "change_count", lambda: 1)

    with pytest.raises(TimeoutError):
        macos.clipboard.wait_for_change(timeout=0.01, interval=0.001)
