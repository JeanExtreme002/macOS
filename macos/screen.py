# -*- coding: utf-8 -*-

"""
Take screenshots.

::

    path = macos.screenshot()                       # temporary PNG
    macos.screenshot("desk.jpg", region=(0, 0, 800, 600))

Capturing other apps' windows needs the *Screen Recording* permission for the
app running Python (your terminal or IDE). Without it macOS doesn't fail: it
silently returns an image with only the wallpaper and the menu bar. This
module checks the permission first and raises
:class:`~macos.errors.PermissionDeniedError` instead.
"""

import ctypes
import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from . import _objc
from ._system import framework, run
from .errors import PermissionDeniedError

__all__ = ["screenshot", "has_permission", "request_permission", "displays", "Display"]

_FORMATS = {".png": "png", ".jpg": "jpg", ".jpeg": "jpg", ".heic": "heic", ".tiff": "tiff", ".gif": "gif", ".pdf": "pdf"}


@lru_cache(maxsize=None)
def _graphics() -> Optional[ctypes.CDLL]:
    """CoreGraphics, or ``None`` before macOS 10.15, which had no Screen Recording permission."""
    cg = framework("CoreGraphics")
    if not hasattr(cg, "CGPreflightScreenCaptureAccess"):
        return None
    cg.CGPreflightScreenCaptureAccess.argtypes = ()
    cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
    cg.CGRequestScreenCaptureAccess.argtypes = ()
    cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
    return cg


def has_permission() -> bool:
    """Whether this process may capture the screen, without prompting the user."""
    cg = _graphics()
    return cg is None or bool(cg.CGPreflightScreenCaptureAccess())


def request_permission() -> bool:
    """
    Ask for the Screen Recording permission, showing the system prompt if needed.

    Returns whether it is granted now. After the user grants it in System
    Settings, the app running Python must be restarted for it to take effect.
    """
    cg = _graphics()
    return cg is None or bool(cg.CGRequestScreenCaptureAccess())


def screenshot(
    path: Union[str, "os.PathLike[str]", None] = None,
    *,
    region: Optional[Tuple[int, int, int, int]] = None,
    display: Optional[int] = None,
    cursor: bool = False,
    check_permission: bool = True,
) -> Path:
    """
    Capture the screen to an image file and return its path.

    - ``path``: where to save it. The format follows the extension (``.png``,
      ``.jpg``, ``.heic``, ``.tiff``, ``.gif``, ``.pdf``). When omitted, a
      temporary ``.png`` is created; deleting it is up to you.
    - ``region``: ``(x, y, width, height)`` in points, from the top-left corner
      of the main display.
    - ``display``: capture this display (``1`` is the main one) instead of the
      main display.
    - ``cursor``: include the mouse pointer.
    - ``check_permission``: raise if the Screen Recording permission is
      missing. Pass ``False`` to accept a capture without other apps' windows.
    """
    if check_permission and not has_permission():
        raise PermissionDeniedError(
            "Screen Recording permission is missing: allow the app running Python (your terminal or IDE) in "
            "System Settings › Privacy & Security › Screen & System Audio Recording, then restart it"
        )

    if path is None:
        descriptor, name = tempfile.mkstemp(prefix="screenshot-", suffix=".png")
        os.close(descriptor)
        target = Path(name)
    else:
        target = Path(path).expanduser().resolve()
        if target.suffix.lower() not in _FORMATS:
            raise ValueError(
                "unsupported image format {!r}; use one of {}".format(target.suffix, ", ".join(sorted(_FORMATS)))
            )
    extension = target.suffix.lower()

    args = ["screencapture", "-x", "-t", _FORMATS[extension]]  # -x: no shutter sound
    if cursor:
        args.append("-C")
    if region is not None:
        x, y, width, height = region
        args.append("-R{},{},{},{}".format(x, y, width, height))
    if display is not None:
        args.append("-D{}".format(display))
    args.append(str(target))

    try:
        run(args)
    except BaseException:
        if path is None:
            target.unlink(missing_ok=True)
        raise
    return target


class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class _CGRect(ctypes.Structure):
    _fields_ = [("origin", _CGPoint), ("size", _CGSize)]


@lru_cache(maxsize=None)
def _display_api() -> ctypes.CDLL:
    cg = framework("CoreGraphics")
    cg.CGGetActiveDisplayList.argtypes = (ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32))
    cg.CGGetActiveDisplayList.restype = ctypes.c_int32
    cg.CGMainDisplayID.argtypes = ()
    cg.CGMainDisplayID.restype = ctypes.c_uint32
    cg.CGDisplayBounds.argtypes = (ctypes.c_uint32,)
    cg.CGDisplayBounds.restype = _CGRect
    cg.CGDisplayIsBuiltin.argtypes = (ctypes.c_uint32,)
    cg.CGDisplayIsBuiltin.restype = ctypes.c_bool
    cg.CGDisplayCopyDisplayMode.argtypes = (ctypes.c_uint32,)
    cg.CGDisplayCopyDisplayMode.restype = ctypes.c_void_p
    cg.CGDisplayModeGetPixelWidth.argtypes = (ctypes.c_void_p,)
    cg.CGDisplayModeGetPixelWidth.restype = ctypes.c_size_t
    cg.CGDisplayModeGetPixelHeight.argtypes = (ctypes.c_void_p,)
    cg.CGDisplayModeGetPixelHeight.restype = ctypes.c_size_t
    cg.CGDisplayModeGetRefreshRate.argtypes = (ctypes.c_void_p,)
    cg.CGDisplayModeGetRefreshRate.restype = ctypes.c_double
    cg.CGDisplayModeRelease.argtypes = (ctypes.c_void_p,)
    cg.CGDisplayModeRelease.restype = None
    return cg


@dataclass(frozen=True)
class Display:
    """A connected display. Sizes and positions are in points, like :func:`macos.screenshot`'s ``region``."""

    id: int
    """The CoreGraphics display ID."""
    name: Optional[str]
    """E.g. ``'Built-in Retina Display'`` (``None`` if macOS doesn't report one)."""
    width: int
    height: int
    x: int
    """Position relative to the main display's top-left corner."""
    y: int
    pixel_width: int
    """Physical resolution, e.g. twice the width on a Retina display."""
    pixel_height: int
    scale: float
    """Pixels per point: 2.0 on Retina displays, 1.0 otherwise."""
    refresh_rate: Optional[float]
    """In Hz; ``None`` when macOS doesn't report it."""
    is_main: bool
    """The display with the menu bar."""
    is_builtin: bool
    """A laptop's own screen."""


def _screen_names() -> Dict[int, str]:
    """Display names by CoreGraphics ID, from NSScreen (macOS 10.15+)."""
    framework("AppKit")
    names = {}
    with _objc.autorelease_pool():
        for screen in _objc.nsarray(_objc.send(_objc.cls("NSScreen"), "screens")):
            description = _objc.send(screen, "deviceDescription")
            number = _objc.send(description, "objectForKey:", _objc.nsstring("NSScreenNumber"), argtypes=(_objc.id,))
            has_name = _objc.send(
                screen, "respondsToSelector:", _objc.sel("localizedName"), argtypes=(_objc.SEL,), restype=_objc.BOOL
            )
            name = _objc.pystring(_objc.send(screen, "localizedName")) if has_name else None
            if number and name:
                names[_objc.send(number, "unsignedIntValue", restype=ctypes.c_uint32)] = name
    return names


def displays() -> List[Display]:
    """Return the connected displays, the main one (with the menu bar) first."""
    cg = _display_api()
    ids = (ctypes.c_uint32 * 32)()
    count = ctypes.c_uint32()
    cg.CGGetActiveDisplayList(len(ids), ids, ctypes.byref(count))
    main = cg.CGMainDisplayID()
    names = _screen_names()

    found = []
    for display_id in ids[: count.value]:
        bounds = cg.CGDisplayBounds(display_id)
        mode = cg.CGDisplayCopyDisplayMode(display_id)
        try:
            pixel_width = cg.CGDisplayModeGetPixelWidth(mode) if mode else round(bounds.size.width)
            pixel_height = cg.CGDisplayModeGetPixelHeight(mode) if mode else round(bounds.size.height)
            refresh = cg.CGDisplayModeGetRefreshRate(mode) if mode else 0.0
        finally:
            if mode:
                cg.CGDisplayModeRelease(mode)
        width = round(bounds.size.width)
        found.append(
            Display(
                id=display_id,
                name=names.get(display_id),
                width=width,
                height=round(bounds.size.height),
                x=round(bounds.origin.x),
                y=round(bounds.origin.y),
                pixel_width=pixel_width,
                pixel_height=pixel_height,
                scale=pixel_width / width if width else 1.0,
                refresh_rate=refresh or None,  # 0 for displays that don't report it
                is_main=display_id == main,
                is_builtin=cg.CGDisplayIsBuiltin(display_id),
            )
        )
    return sorted(found, key=lambda display: not display.is_main)
