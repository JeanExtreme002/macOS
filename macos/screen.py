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
from .errors import MacOSError, PermissionDeniedError

__all__ = ["screenshot", "has_permission", "request_permission", "displays", "Display", "wallpaper", "set_wallpaper"]

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


@lru_cache(maxsize=None)
def _display_api() -> ctypes.CDLL:
    cg = framework("CoreGraphics")
    cg.CGGetActiveDisplayList.argtypes = (ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32))
    cg.CGGetActiveDisplayList.restype = ctypes.c_int32
    cg.CGMainDisplayID.argtypes = ()
    cg.CGMainDisplayID.restype = ctypes.c_uint32
    cg.CGDisplayBounds.argtypes = (ctypes.c_uint32,)
    cg.CGDisplayBounds.restype = _objc.CGRect
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


def _screens() -> List[Tuple[int, int]]:
    """``(display id, NSScreen)`` pairs, the main screen first. Call inside an autorelease pool."""
    framework("AppKit")
    pairs = []
    for screen in _objc.nsarray(_objc.send(_objc.cls("NSScreen"), "screens")):
        description = _objc.send(screen, "deviceDescription")
        number = _objc.send(description, "objectForKey:", _objc.nsstring("NSScreenNumber"), argtypes=(_objc.id,))
        if number:
            pairs.append((_objc.send(number, "unsignedIntValue", restype=ctypes.c_uint32), screen))
    return pairs


def _screen_names() -> Dict[int, str]:
    """Display names by CoreGraphics ID, from NSScreen (macOS 10.15+)."""
    names = {}
    with _objc.autorelease_pool():
        for display_id, screen in _screens():
            has_name = _objc.send(
                screen, "respondsToSelector:", _objc.sel("localizedName"), argtypes=(_objc.SEL,), restype=_objc.BOOL
            )
            name = _objc.pystring(_objc.send(screen, "localizedName")) if has_name else None
            if name:
                names[display_id] = name
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


@lru_cache(maxsize=None)
def _workspace() -> int:
    framework("AppKit")
    return _objc.send(_objc.cls("NSWorkspace"), "sharedWorkspace")


def _pick(pairs: List[Tuple[int, int]], display_id: Union[int, Display, None]) -> List[Tuple[int, int]]:
    if display_id is None:
        return pairs
    wanted = display_id.id if isinstance(display_id, Display) else display_id
    chosen = [pair for pair in pairs if pair[0] == wanted]
    if not chosen:
        raise ValueError("no connected display has the id {} (see macos.screen.displays())".format(wanted))
    return chosen


def wallpaper(display_id: Union[int, Display, None] = None) -> Optional[Path]:
    """
    Return the desktop picture of a display (the main one by default).

    ``display_id`` is a :class:`Display` from :func:`displays`, or its
    :attr:`~Display.id`. (It's not the position that :func:`screenshot`'s
    ``display`` takes.) Returns ``None``
    when the desktop shows something other than a picture file, such as a
    solid color or a dynamic wallpaper that isn't a file.
    """
    with _objc.autorelease_pool():
        pairs = _pick(_screens(), display_id)
        if not pairs:
            return None
        url = _objc.send(_workspace(), "desktopImageURLForScreen:", pairs[0][1], argtypes=(_objc.id,))
        path = _objc.pystring(_objc.send(url, "path")) if url else None
        return Path(path) if path else None


def set_wallpaper(path: Union[str, "os.PathLike[str]"], *, display_id: Union[int, Display, None] = None) -> None:
    """
    Set the desktop picture, on every display or only on ``display_id``.

    ``path`` is an image file (JPEG, PNG, HEIC...). macOS keeps referring to
    that file, so don't delete it afterwards. ``display_id`` works as in
    :func:`wallpaper`. If macOS refuses the picture for one display, the ones
    before it keep the new picture and :class:`~macos.errors.MacOSError` is
    raised.
    """
    image = Path(path).expanduser().resolve()
    if not image.is_file():
        raise FileNotFoundError(str(image))
    with _objc.autorelease_pool():
        url = _objc.file_url(image)
        options = _objc.send(_objc.cls("NSDictionary"), "dictionary")
        for _, screen in _pick(_screens(), display_id):
            error = ctypes.c_void_p()
            ok = _objc.send(
                _workspace(),
                "setDesktopImageURL:forScreen:options:error:",
                url,
                screen,
                options,
                ctypes.byref(error),
                argtypes=(_objc.id, _objc.id, _objc.id, ctypes.c_void_p),
                restype=_objc.BOOL,
            )
            if not ok:
                message = _objc.error_message(error) or "not an image macOS can show"
                raise MacOSError("could not set the wallpaper: {}".format(message))
