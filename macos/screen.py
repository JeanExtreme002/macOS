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
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple, Union

from ._system import framework, run
from .errors import PermissionDeniedError

__all__ = ["screenshot", "has_permission", "request_permission"]

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
