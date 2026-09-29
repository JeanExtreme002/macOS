"""Tests of :mod:`macos.dialog` against the real system. Skipped outside macOS."""

import pytest

import macos


def test_dialogs_close_after_their_timeout():
    try:
        assert macos.dialog.confirm("pymacos test: this closes by itself", timeout=1) is False
        assert macos.dialog.prompt("pymacos test: this closes by itself", timeout=1) is None
        macos.dialog.alert("pymacos test: this closes by itself", timeout=1)
    except macos.CommandError as error:  # e.g. no window server on a CI runner
        pytest.skip("dialogs can't be shown here: {}".format(error))
