"""Tests of :mod:`macos.schedule` against the real system. Skipped outside macOS."""

import os
import time

import pytest

import macos


@pytest.mark.skipif(
    not (os.environ.get("CI") or os.environ.get("PYMACOS_SCHEDULE_TESTS")),
    reason="adds a launch agent, which macOS announces: set PYMACOS_SCHEDULE_TESTS=1 to run",
)
def test_schedule_runs_the_script(tmp_path):
    script = tmp_path / "job.py"
    output = tmp_path / "out.txt"
    script.write_text("import sys\nopen(sys.argv[1], 'w').write(' '.join(sys.argv[2:]))\nprint('done')\n")
    name = "pymacos-test-{}".format(os.getpid())
    try:
        job = macos.schedule.add(name, script, every=3600, args=[str(output), "two words"])
        assert job.every == 3600 and job.script == script and name in [found.name for found in macos.schedule.jobs()]
        macos.schedule.run_now(name)
        deadline = time.monotonic() + 30
        while not output.exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert output.read_text() == "two words"
        deadline = time.monotonic() + 10
        while macos.schedule.get(name).last_exit_status is None and time.monotonic() < deadline:
            time.sleep(0.2)
        job = macos.schedule.get(name)
        assert job.last_exit_status == 0 and "done" in job.log.read_text()
        assert job.args == (str(output), "two words")
    finally:
        assert macos.schedule.remove(name)
        (macos.schedule._log(name)).unlink(missing_ok=True)
    assert macos.schedule.get(name) is None
