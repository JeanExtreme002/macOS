"""Unit tests for :mod:`macos.spotlight`. They run on any platform."""

import subprocess
from pathlib import Path

import pytest

import macos
from macos import _system


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
