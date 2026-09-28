"""A tiny app with one window, for the window tests: python _window_app.py TITLE SECONDS."""

import ctypes
import sys
import time

from macos import _objc
from macos._system import framework


def main(title: str, seconds: float) -> None:
    framework("AppKit")
    with _objc.autorelease_pool():
        app = _objc.send(_objc.cls("NSApplication"), "sharedApplication")
        _objc.send(app, "setActivationPolicy:", 1, argtypes=(_objc.NSInteger,), restype=_objc.BOOL)  # accessory: no Dock icon
        _objc.send(app, "finishLaunching", restype=None)
        frame = _objc.CGRect(_objc.CGPoint(40, 40), _objc.CGSize(320, 200))
        style = 1 | 2 | 4 | 8  # titled, closable, miniaturizable, resizable
        window = _objc.send(_objc.cls("NSWindow"), "alloc")
        window = _objc.send(
            window,
            "initWithContentRect:styleMask:backing:defer:",
            frame,
            style,
            2,
            False,
            argtypes=(_objc.CGRect, _objc.NSUInteger, _objc.NSUInteger, _objc.BOOL),
        )
        _objc.send(window, "setReleasedWhenClosed:", False, argtypes=(_objc.BOOL,), restype=None)
        _objc.send(window, "setTitle:", _objc.nsstring(title), argtypes=(_objc.id,), restype=None)
        _objc.send(window, "makeKeyAndOrderFront:", None, argtypes=(_objc.id,), restype=None)
        print("ready", flush=True)
        mode = _objc.nsstring("kCFRunLoopDefaultMode")
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            with _objc.autorelease_pool():
                until = _objc.send(_objc.cls("NSDate"), "dateWithTimeIntervalSinceNow:", 0.05, argtypes=(ctypes.c_double,))
                event = _objc.send(
                    app,
                    "nextEventMatchingMask:untilDate:inMode:dequeue:",
                    ctypes.c_uint64(0xFFFFFFFFFFFFFFFF),
                    until,
                    mode,
                    True,
                    argtypes=(ctypes.c_uint64, _objc.id, _objc.id, _objc.BOOL),
                )
                if event:
                    _objc.send(app, "sendEvent:", event, argtypes=(_objc.id,), restype=None)
            if not _objc.send(window, "isVisible", restype=_objc.BOOL) and not _objc.send(
                window, "isMiniaturized", restype=_objc.BOOL
            ):
                break  # closed


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))
