# -*- coding: utf-8 -*-

"""
Open files, folders and URLs, with their default app or a chosen one.

::

    macos.open("report.pdf")                   # in the default app
    macos.open("https://python.org")           # in the default browser
    macos.open_with("photo.png", "Preview")

Goes through LaunchServices (the ``open`` command), exactly like
double-clicking in Finder or choosing *Open With*.
"""

import os
import re
from pathlib import Path
from typing import List, Union

from ._system import run
from .apps import open_with

__all__ = ["open", "open_with"]

Target = Union[str, "os.PathLike[str]"]

# "https://...", "mailto:...", "x-apple.systempreferences:..." and the like.
_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _target(target: Target) -> str:
    if isinstance(target, str) and _URL.match(target) and not os.path.exists(target):
        return target
    path = Path(target).expanduser().absolute()
    if not os.path.lexists(path):
        raise FileNotFoundError(str(path))
    return str(path)


def _flags(background: bool) -> List[str]:
    return ["-g"] if background else []


def open(target: Target, *, background: bool = False) -> None:
    """
    Open a file, folder or URL with its default app, like double-clicking it.

    Folders open in Finder and URLs in their default app (the browser for
    ``https://``, Mail for ``mailto:``...). ``background=True`` opens it
    without bringing the app to the front.
    """
    run(["open", *_flags(background), "--", _target(target)])
