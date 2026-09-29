"""Unit tests for :mod:`macos.hotkeys`. They run on any platform."""

import pytest

import macos


def test_hotkeys_registry():
    cmd, option, control = 1 << 20, 1 << 19, 1 << 18

    assert macos.hotkeys._combination("ctrl+option+cmd+f19") == (80, control | option | cmd)
    assert macos.hotkeys._combination("f5") == (96, 0)

    first = macos.hotkeys.register("ctrl+f19", lambda: "first")
    second = macos.hotkeys.register("ctrl+f19", lambda: "second")  # replaces it
    try:
        assert macos.hotkeys._registered[(80, control)] is second
        first.unregister()  # the same keys: removes the current one
        assert (80, control) not in macos.hotkeys._registered
    finally:
        macos.hotkeys.unregister("ctrl+f19")


def test_hotkeys_argument_checks():
    with pytest.raises(ValueError, match="not a modifier"):
        macos.hotkeys.register("hyper+k", lambda: None)
