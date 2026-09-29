"""Tests of :mod:`macos.defaults` against the real system. Skipped outside macOS."""

import datetime
import os
import subprocess

import macos


def test_defaults_round_trip():
    domain = "com.github.pymacos.test-{}".format(os.getpid())
    values = {
        "flag": True, "count": 3, "ratio": 0.5, "name": "olá", "blob": b"\x00\x01",
        "when": datetime.datetime(2026, 9, 29, 12, 0), "items": [1, "a"], "nested": {"k": [True]},
    }  # fmt: skip
    try:
        for key, value in values.items():
            macos.defaults.write(domain, key, value)
        assert macos.defaults.read(domain) == values
        assert macos.defaults.keys(domain) == sorted(values)
        # The types are real ones, as `defaults` sees them.
        assert "boolean" in subprocess.run(["defaults", "read-type", domain, "flag"], capture_output=True, text=True).stdout
        assert macos.defaults.read(domain, "missing", default="none") == "none"
        assert macos.defaults.delete(domain, "flag") is True and macos.defaults.delete(domain, "flag") is False
    finally:
        for key in values:
            macos.defaults.delete(domain, key)
        subprocess.run(["defaults", "delete", domain], capture_output=True)
    assert macos.defaults.read(macos.defaults.GLOBAL, "AppleLocale") == macos.defaults.read("-g", "AppleLocale")
