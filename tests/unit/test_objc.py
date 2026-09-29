"""Unit tests for the Objective-C bridge: blocks and runtime classes."""

import sys

import pytest


@pytest.mark.skipif(sys.platform != "darwin", reason="calls the Objective-C runtime")
def test_objc_blocks_and_classes():
    import ctypes

    from macos import _objc

    seen = []
    with _objc.autorelease_pool():
        items = _objc.nsarray_of([_objc.nsstring(text) for text in ("a", "b")])
        each = _objc.block(
            lambda item, index, stop: seen.append((_objc.pystring(item), index)),
            b"v@?@Q^c",
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
        )
        _objc.send(items, "enumerateObjectsUsingBlock:", each, argtypes=(ctypes.c_void_p,), restype=None)
    assert seen == [("a", 0), ("b", 1)]

    echo = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    made = _objc.define_class("PymacosTestEcho", {"echo:": ("@@:@", echo, lambda self, cmd, value: value)})
    assert _objc.define_class("PymacosTestEcho", {}) == made  # made once
    with _objc.autorelease_pool():
        answer = _objc.send(_objc.new("PymacosTestEcho"), "echo:", _objc.nsstring("hi"), argtypes=(_objc.id,))
        assert _objc.pystring(answer) == "hi"

    assert _objc.run_until(lambda: True, 1) is True
    assert _objc.run_until(lambda: False, 0.1) is False
