"""Unit tests for :mod:`macos.schedule`. They run on any platform."""

import os
import plistlib
import sys
from pathlib import Path

import pytest

import macos


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(os, "getuid", lambda: 501, raising=False)
    script = tmp_path / "backup.py"
    script.write_text("print('hi')")
    return tmp_path


def _plist(home, name):
    return plistlib.loads((home / "Library" / "LaunchAgents" / "pymacos.{}.plist".format(name)).read_bytes())


def test_schedule_every(fake_run, home):
    job = macos.schedule.add("backup", home / "backup.py", every=3600, args=["--quiet"])

    plist = _plist(home, "backup")
    assert plist["Label"] == "pymacos.backup"
    assert plist["ProgramArguments"] == [sys.executable, str(home / "backup.py"), "--quiet"]
    assert plist["StartInterval"] == 3600 and plist["RunAtLoad"] is False
    assert plist["WorkingDirectory"] == str(home)
    assert plist["StandardOutPath"] == plist["StandardErrorPath"] == str(home / "Library/Logs/pymacos/backup.log")
    commands = [call["args"] for call in fake_run.calls]
    assert ["launchctl", "bootout", "gui/501/pymacos.backup"] in commands  # replacing a job unloads the old one
    assert ["launchctl", "bootstrap", "gui/501", str(home / "Library/LaunchAgents/pymacos.backup.plist")] in commands
    assert (job.name, job.every, job.at, job.args) == ("backup", 3600, (), ("--quiet",))


def test_schedule_at_times_and_weekdays(fake_run, home):
    job = macos.schedule.add("report", home / "backup.py", at=["9:00", "18:30"], weekdays=["Mon", "friday"])

    assert _plist(home, "report")["StartCalendarInterval"] == [
        {"Hour": 9, "Minute": 0, "Weekday": 1},
        {"Hour": 9, "Minute": 0, "Weekday": 5},
        {"Hour": 18, "Minute": 30, "Weekday": 1},
        {"Hour": 18, "Minute": 30, "Weekday": 5},
    ]
    assert (job.at, job.weekdays, job.every) == (("09:00", "18:30"), ("mon", "fri"), None)


def test_schedule_at_login_jobs_and_remove(fake_run, home):
    macos.schedule.add("hello", home / "backup.py", at_login=True, python=home / "venv/bin/python")
    macos.schedule.add("daily", home / "backup.py", at="07:15")

    assert _plist(home, "hello")["RunAtLoad"] is True
    assert _plist(home, "hello")["ProgramArguments"][0] == str(home / "venv/bin/python")
    assert [job.name for job in macos.schedule.jobs()] == ["daily", "hello"]
    assert macos.schedule.remove("hello") is True
    assert macos.schedule.remove("hello") is False
    assert macos.schedule.get("hello") is None
    macos.schedule.run_now("daily")
    assert fake_run.args == ["launchctl", "kickstart", "gui/501/pymacos.daily"]


def test_schedule_reads_the_job_state(fake_run, home):
    macos.schedule.add("backup", home / "backup.py", every=60)
    fake_run.stdout = '{\n\t"LastExitStatus" = 256;\n\t"PID" = 4242;\n\t"Label" = "pymacos.backup";\n};\n'

    job = macos.schedule.get("backup")

    assert job.running is True and job.last_exit_status == 256


def test_schedule_argument_checks(fake_run, home):
    script = home / "backup.py"
    checks = [
        (lambda: macos.schedule.add("bad name", script, every=60), "name must be"),
        (lambda: macos.schedule.add("x", script), "every=, at= or at_login=True"),
        (lambda: macos.schedule.add("x", script, every=60, at="09:00"), "either every or at"),
        (lambda: macos.schedule.add("x", script, every=0), "at least 1 second"),
        (lambda: macos.schedule.add("x", script, at="25:00"), "a time such as"),
        (lambda: macos.schedule.add("x", script, at=[]), "at least one time"),
        (lambda: macos.schedule.add("x", script, at="09:00", weekdays=["someday"]), "weekdays are"),
        (lambda: macos.schedule.add("x", script, every=60, weekdays=["mon"]), "only apply with at"),
        (lambda: macos.schedule.run_now("missing"), "no job named"),
    ]
    for call, message in checks:
        with pytest.raises(ValueError, match=message):
            call()
    with pytest.raises(FileNotFoundError):
        macos.schedule.add("x", home / "missing.py", every=60)
    assert not Path(home / "Library/LaunchAgents").exists() or not list(Path(home / "Library/LaunchAgents").iterdir())


def test_schedule_takes_timedelta_and_time(fake_run, home):
    import datetime

    macos.schedule.add("hourly", home / "backup.py", every=datetime.timedelta(minutes=90))
    macos.schedule.add("morning", home / "backup.py", at=[datetime.time(7, 5, 30), "19:00"])

    assert _plist(home, "hourly")["StartInterval"] == 5400
    assert _plist(home, "morning")["StartCalendarInterval"] == [{"Hour": 7, "Minute": 5}, {"Hour": 19, "Minute": 0}]


def test_schedule_pause_and_resume(fake_run, home):
    macos.schedule.add("backup", home / "backup.py", every=60)
    fake_run.calls.clear()

    macos.schedule.pause("backup")
    assert [call["args"][1] for call in fake_run.calls] == ["bootout", "disable"]
    assert fake_run.args == ["launchctl", "disable", "gui/501/pymacos.backup"]

    fake_run.stdout = '\tdisabled services = {\n\t\t"pymacos.backup" => disabled\n\t\t"pymacos.other" => enabled\n\t}\n'
    assert macos.schedule.get("backup").paused is True
    fake_run.calls.clear()
    macos.schedule.remove("backup")  # a paused job is enabled again, so its name can be reused
    assert ["launchctl", "enable", "gui/501/pymacos.backup"] in [call["args"] for call in fake_run.calls]

    fake_run.stdout = ""
    macos.schedule.add("backup", home / "backup.py", every=60)
    fake_run.calls.clear()
    macos.schedule.resume("backup")
    assert [call["args"][1] for call in fake_run.calls] == ["bootout", "enable", "bootstrap"]
    with pytest.raises(ValueError, match="no job named"):
        macos.schedule.pause("missing")


def test_schedule_remove_only_ignores_a_job_that_isnt_loaded(fake_run, home, monkeypatch):
    import subprocess

    from macos import _system

    macos.schedule.add("backup", home / "backup.py", every=60)
    answers = {"bootout": (3, "Boot-out failed: 3: No such process")}

    def launchctl(args, **kwargs):
        code, error = answers.get(args[1], (0, ""))
        return subprocess.CompletedProcess(args, code, "", error)

    monkeypatch.setattr(_system.subprocess, "run", launchctl)
    assert macos.schedule.remove("backup") is True  # not loaded: fine

    macos.schedule.add("backup", home / "backup.py", every=60)
    answers["bootout"] = (5, "Boot-out failed: 5: Input/output error")
    with pytest.raises(macos.CommandError):
        macos.schedule.remove("backup")
    assert macos.schedule.get("backup") is not None  # still managed, since it may still be loaded
