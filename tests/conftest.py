import subprocess
import sys
from typing import List

import pytest

from macos import _system


def pytest_collection_modifyitems(config, items):
    if sys.platform == "darwin":
        return
    skip = pytest.mark.skip(reason="live tests need macOS")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


class FakeRun:
    """Records the commands passed to ``subprocess.run`` instead of running them."""

    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.calls: List[dict] = []
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, args, **kwargs):
        self.calls.append({"args": list(args), **kwargs})
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, self.stderr)

    @property
    def args(self) -> List[str]:
        return self.calls[-1]["args"]


@pytest.fixture
def fake_run(monkeypatch):
    """Pretend to be on macOS and capture system commands."""
    fake = FakeRun()
    monkeypatch.setattr(_system.sys, "platform", "darwin")
    monkeypatch.setattr(_system.subprocess, "run", fake)
    return fake
