"""Unit tests for :mod:`macos.system`. They run on any platform."""

import sys
from pathlib import Path

import pytest

import macos


def test_system_commands(fake_run):
    fake_run.stdout = "24G90\n"
    assert macos.system.build() == "24G90"
    assert fake_run.args == ["sw_vers", "-buildVersion"]

    fake_run.stdout = "My Mac\n"
    assert macos.system.computer_name() == "My Mac"
    assert fake_run.args == ["scutil", "--get", "ComputerName"]


def test_eject(fake_run, monkeypatch):
    backup = macos.system.Volume("Backup", Path("/Volumes/Backup"), 10, 5, False, True, True)
    root = macos.system.Volume("Macintosh HD", Path("/"), 10, 5, True, False, False)
    monkeypatch.setattr(macos.system, "volumes", lambda: [root, backup])

    macos.system.eject("Backup")
    assert fake_run.args == ["diskutil", "eject", "/Volumes/Backup"]
    macos.system.eject("/Volumes/Backup/")
    assert fake_run.args[-1] == "/Volumes/Backup"
    macos.system.eject(backup)
    assert fake_run.args[-1] == "/Volumes/Backup"

    with pytest.raises(ValueError, match="startup disk"):
        macos.system.eject("Macintosh HD")
    with pytest.raises(ValueError, match="no mounted volume"):
        macos.system.eject("Nope")


def test_eject_refuses_folders_and_hidden_system_volumes(fake_run, monkeypatch, tmp_path):
    monkeypatch.setattr(macos.system, "volumes", lambda: [])

    for target in (tmp_path, "/System/Volumes/Data"):
        with pytest.raises(ValueError, match="no mounted volume"):
            macos.system.eject(target)
    assert fake_run.calls == []


def test_eject_refuses_ambiguous_names_and_fixed_volumes(fake_run, monkeypatch):
    first = macos.system.Volume("Untitled", Path("/Volumes/Untitled"), 10, 5, False, True, True)
    second = macos.system.Volume("Untitled", Path("/Volumes/Untitled 1"), 10, 5, False, True, True)
    fixed = macos.system.Volume("Data", Path("/Volumes/Data"), 10, 5, True, False, False)
    monkeypatch.setattr(macos.system, "volumes", lambda: [first, second, fixed])

    with pytest.raises(ValueError, match="more than one volume"):
        macos.system.eject("Untitled")
    macos.system.eject("/Volumes/Untitled 1")
    assert fake_run.args == ["diskutil", "eject", "/Volumes/Untitled 1"]

    with pytest.raises(ValueError, match="can't be ejected"):
        macos.system.eject("Data")


def test_microphone_in_use(monkeypatch):
    from macos import audio

    properties = {(1, "prs#"): [101, 102], (101, "piri"): 0, (102, "piri"): 0}

    def fake_property(target, selector, scope=None, element=0):
        value = properties.get((target, selector))
        if value is None:
            return None
        values = value if isinstance(value, list) else [value]
        return b"".join(number.to_bytes(4, "little") for number in values)

    monkeypatch.setattr(audio, "_property", fake_property)
    monkeypatch.setattr(audio, "_uint", lambda target, selector: properties.get((target, selector)))
    assert macos.system.microphone_in_use() is False
    properties[(102, "piri")] = 1  # one app records
    assert macos.system.microphone_in_use() is True

    # Before macOS 14 there's no process list: an input device running counts.
    del properties[(1, "prs#")]
    monkeypatch.setattr(audio, "inputs", lambda: [audio.Device(9, "Mic", "mic", "builtin", False, True)])
    assert macos.system.microphone_in_use() is False
    properties[(9, "gone")] = 1
    assert macos.system.microphone_in_use() is True


def test_camera_in_use(monkeypatch):
    running = {1: [34, 35], 34: [0], 35: [0]}
    monkeypatch.setattr(
        macos.system,
        "_camera_property",
        lambda target, selector: b"".join(number.to_bytes(4, "little") for number in running[target]),
    )

    assert macos.system.camera_in_use() is False
    running[35] = [1]
    assert macos.system.camera_in_use() is True


def test_wait_for_idle_and_activity(monkeypatch):
    from datetime import timedelta

    system = macos.system
    clock = {"now": 0.0}
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(system.time, "sleep", sleep)
    monkeypatch.setattr(system.time, "monotonic", lambda: clock["now"])
    idle = iter([10.0, 250.0, 300.0])
    monkeypatch.setattr(system, "idle_time", lambda: timedelta(seconds=next(idle)))

    assert system.wait_for_idle(timedelta(minutes=5)) is True
    assert sleeps[:2] == [290.0, 50.0]  # it sleeps until the goal could be reached, not in small steps

    # Idle for 0.01 s when it starts; input 0.1 s later, so 0.1 s idle after one 0.2 s interval:
    # still more than the first reading, but less than the 0.21 s it would be without input.
    readings = iter([0.01, 0.1])
    monkeypatch.setattr(system, "idle_time", lambda: timedelta(seconds=next(readings)))
    assert system.wait_for_activity() is True

    monkeypatch.setattr(system, "idle_time", lambda: timedelta(seconds=clock["now"]))  # nobody around
    assert system.wait_for_activity(timeout=1) is False
    monkeypatch.setattr(system, "idle_time", lambda: timedelta(seconds=1))
    assert system.wait_for_idle(60, timeout=0) is False
    with pytest.raises(ValueError):
        system.wait_for_idle(-1)


_UPDATES = """Software Update Tool

Finding available software
Software Update found the following new or updated software:
* Label: Safari27.0SequoiaAuto-27.0
\tTitle: Safari, Version: 27.0, Size: 238423KiB, Recommended: YES,\x20
* Label: macOS Sequoia\xa015.8.1-24H32
\tTitle: macOS Sequoia\xa015.8.1, Version: 15.8.1, Size: 2310804KiB, Recommended: YES, Action: restart,\x20
"""


def test_available_updates(fake_run):
    fake_run.stdout = _UPDATES
    safari, sequoia = macos.system.available_updates()

    assert (safari.label, safari.title, safari.version, safari.size, safari.restart) == (
        "Safari27.0SequoiaAuto-27.0", "Safari", "27.0", 238423 * 1024, False,
    )  # fmt: skip
    assert sequoia.label == "macOS Sequoia\xa015.8.1-24H32"  # exact, as softwareupdate --install takes it
    assert sequoia.title == "macOS Sequoia 15.8.1" and sequoia.recommended and sequoia.restart
    fake_run.stdout = "Software Update Tool\n\nFinding available software\n"
    assert macos.system.available_updates() == []


def test_mount_image(fake_run, tmp_path):
    image = tmp_path / "Tool.dmg"
    image.write_bytes(b"dmg")
    fake_run.stdout = (
        '<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict><key>system-entities</key><array>'
        "<dict><key>content-hint</key><string>GUID_partition_scheme</string></dict>"
        "<dict><key>mount-point</key><string>/Volumes/Tool</string></dict></array></dict></plist>"
    )

    assert macos.system.mount_image(image) == Path("/Volumes/Tool")
    assert fake_run.args[:2] == ["hdiutil", "attach"] and fake_run.calls[-1]["input"] == "Y\n"  # accepts a license
    macos.system.unmount_image("/Volumes/Tool", force=True)
    assert fake_run.args == ["hdiutil", "detach", "/Volumes/Tool", "-force"]
    with pytest.raises(FileNotFoundError):
        macos.system.mount_image(tmp_path / "missing.dmg")


def test_cpu_and_memory_argument_checks():
    with pytest.raises(ValueError, match="interval"):
        macos.system.cpu_usage(0)
    usage = macos.system.MemoryUsage(total=100, used=25, wired=5, compressed=5, cached=10)
    assert (usage.free, usage.percent) == (75, 0.25)


def test_mount_image_detaches_an_image_without_a_volume(fake_run, tmp_path):
    image = tmp_path / "Disk.dmg"
    image.write_bytes(b"dmg")
    fake_run.stdout = (
        '<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict><key>system-entities</key><array>'
        "<dict><key>dev-entry</key><string>/dev/disk9s1</string></dict>"
        "<dict><key>dev-entry</key><string>/dev/disk9</string></dict></array></dict></plist>"
    )

    with pytest.raises(macos.MacOSError, match="no volume to mount"):
        macos.system.mount_image(image)
    assert fake_run.args == ["hdiutil", "detach", "/dev/disk9", "-force"]  # the whole disk, not left attached


def test_cpu_usage_survives_a_counter_wrapping_around(monkeypatch):
    system = macos.system
    samples = iter([(2**32 - 100, 50, 1000, 0), (100, 150, 1200, 0)])  # user wrapped: +200
    monkeypatch.setattr(system, "_cpu_ticks", lambda: next(samples))
    monkeypatch.setattr(system.time, "sleep", lambda seconds: None)

    assert system.cpu_usage() == 0.6  # (200 user + 100 system) busy of 500 ticks


@pytest.mark.skipif(sys.platform != "darwin", reason="reads the real processes")
def test_processes():
    import os
    import subprocess

    found = macos.system.processes()
    own = next(process for process in found if process.pid == os.getpid())
    assert own.memory and own.cpu_time is not None and own.started and own.path and own.path.exists()
    assert any(process.pid == 1 and process.name == "launchd" and process.user == "root" for process in found)
    assert macos.system.process(os.getpid()).parent_pid == os.getppid()

    child = subprocess.Popen(["sleep", "30"])
    try:
        assert macos.system.process(child.pid).name == "sleep"
        assert macos.system.process(child.pid, cpu=True).cpu_percent is not None
        macos.system.process(child.pid).kill()
        assert child.wait(timeout=5) == -15
    finally:
        child.kill()
    assert macos.system.process(child.pid) is None
    with pytest.raises(ProcessLookupError):
        macos.system.kill(child.pid)


def test_process_checks():
    with pytest.raises(ValueError, match="pid must be positive"):
        macos.system.process(0)


def test_process_names_cut_by_the_kernel():
    from pathlib import Path

    long_path = Path("/Applications/Google Chrome.app/Contents/Frameworks/Google Chrome Helper (Renderer)")
    name = macos.system._process_name
    assert name(b"Code Helper (Plugin)", b"Code Helper (Pl", Path("/x/Code Helper (Plugin)")) == "Code Helper (Plugin)"
    assert name(b"Google Chrome Helper (Rendere", b"Google Chrome H", long_path) == "Google Chrome Helper (Rendere"
    beta = long_path.with_name("Google Chrome Helper (Renderer) Beta")  # 36 characters: cut to 31
    assert name(b"Google Chrome Helper (Renderer)", b"Google Chrome H", beta) == "Google Chrome Helper (Renderer) Beta"
    assert name(b"", b"Google Chrome H", long_path) == "Google Chrome Helper (Renderer)"  # only the short name
    assert name(b"", b"launchd", Path("/sbin/launchd")) == "launchd"
    assert name(b"", b"kernel_task", None) == "kernel_task"


def test_cpu_percent_from_two_readings(monkeypatch):
    from datetime import timedelta

    clock = {"now": 100.0}
    monkeypatch.setattr(macos.system.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(macos.system.time, "sleep", lambda seconds: clock.update(now=clock["now"] + seconds))

    def process(pid, cpu_seconds, started="then"):
        return macos.system.Process(pid, "p", None, "me", 1, started, 1, timedelta(seconds=cpu_seconds))

    before = [process(1, 10), process(2, 5), process(3, 1), process(4, 2)]
    later = {1: process(1, 10.25), 2: process(2, 5.8), 4: process(4, 0, started="another")}  # 3 quit; 4 is a new one
    measured = macos.system._with_cpu(before, lambda: later, started=100.0)
    assert [found.cpu_percent for found in measured] == [50.0, 160.0, None, None]


@pytest.mark.skipif(sys.platform != "darwin", reason="reads the real sockets")
def test_ports_and_their_owners():
    import os
    import socket

    with socket.socket() as server, socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as udp:
        server.bind(("127.0.0.1", 0))
        server.listen()
        udp.bind(("::1", 0))
        tcp_port, udp_port = server.getsockname()[1], udp.getsockname()[1]
        found = macos.system.ports()
        assert macos.system.Port(tcp_port, "tcp", "127.0.0.1", os.getpid(), macos.system.process(os.getpid()).name) in found
        assert any(port.port == udp_port and port.protocol == "udp" and port.address == "::1" for port in found)
        assert macos.system.port_owner(tcp_port).pid == os.getpid()
        assert macos.system.port_owner(udp_port, "udp").pid == os.getpid()
        assert macos.system.port_owner(tcp_port, "udp") is None
    assert macos.system.port_owner(tcp_port) is None  # closed


def test_port_checks():
    with pytest.raises(ValueError, match="port must be from 1 to 65535"):
        macos.system.port_owner(0)
    with pytest.raises(ValueError, match="protocol must be"):
        macos.system.port_owner(80, "sctp")
