"""Unit tests for the command-backed features. They run on any platform."""

import os
import subprocess
import sys

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
