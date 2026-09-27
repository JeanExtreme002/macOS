# -*- coding: utf-8 -*-

"""
Finder operations: reveal files, move them to the Trash and manage tags.

::

    macos.finder.reveal("report.pdf")
    macos.finder.trash("old.log")                 # Path in ~/.Trash
    macos.finder.add_tags("report.pdf", "Work")
    macos.finder.tags("report.pdf")               # ['Work']

Trash and tags go through Foundation (``NSFileManager``/``NSURL``), the same
APIs Finder itself uses: a trashed file can be restored with *Put Back*, and
tags show up in Finder's sidebar and in Spotlight.
"""

import ctypes
import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Union

from . import _objc
from ._objc import BOOL, NSUInteger
from ._system import framework, run
from .errors import MacOSError

__all__ = ["reveal", "trash", "tags", "set_tags", "add_tags", "remove_tags"]

PathLike = Union[str, "os.PathLike[str]"]


def _existing(path: PathLike) -> Path:
    resolved = Path(path).expanduser().absolute()
    if not os.path.lexists(resolved):
        raise FileNotFoundError(str(resolved))
    return resolved


def _url(path: Path) -> int:
    return _objc.send(_objc.cls("NSURL"), "fileURLWithPath:", _objc.nsstring(str(path)), argtypes=(_objc.id,))


def _raise(error: ctypes.c_void_p, what: str) -> None:
    message = _objc.pystring(_objc.send(error.value, "localizedDescription")) if error.value else None
    raise MacOSError("{}: {}".format(what, message or "unknown error"))


@lru_cache(maxsize=None)
def _tag_names_key() -> int:
    return ctypes.c_void_p.in_dll(framework("Foundation"), "NSURLTagNamesKey").value or 0


def reveal(path: PathLike) -> None:
    """Open a Finder window with ``path`` selected."""
    # Through LaunchServices (`open -R`), which, unlike asking NSWorkspace,
    # also brings Finder to the front when called from a script.
    run(["open", "-R", str(_existing(path))])


def trash(path: PathLike) -> Path:
    """
    Move ``path`` to the Trash and return where it ended up.

    Unlike deleting it, the file can be restored from the Trash with
    *Put Back*.
    """
    source = _existing(path)
    with _objc.autorelease_pool():
        manager = _objc.send(_objc.cls("NSFileManager"), "defaultManager")
        resulting = ctypes.c_void_p()
        error = ctypes.c_void_p()
        ok = _objc.send(
            manager,
            "trashItemAtURL:resultingItemURL:error:",
            _url(source),
            ctypes.byref(resulting),
            ctypes.byref(error),
            argtypes=(_objc.id, ctypes.c_void_p, ctypes.c_void_p),
            restype=BOOL,
        )
        if not ok:
            _raise(error, "could not move {} to the Trash".format(source))
        return Path(_objc.pystring(_objc.send(resulting.value, "path")) or "")


def tags(path: PathLike) -> List[str]:
    """Return the Finder tags on ``path`` (e.g. ``['Red', 'Work']``)."""
    target = _existing(path)
    with _objc.autorelease_pool():
        value = ctypes.c_void_p()
        error = ctypes.c_void_p()
        ok = _objc.send(
            _url(target),
            "getResourceValue:forKey:error:",
            ctypes.byref(value),
            _tag_names_key(),
            ctypes.byref(error),
            argtypes=(ctypes.c_void_p, _objc.id, ctypes.c_void_p),
            restype=BOOL,
        )
        if not ok:
            _raise(error, "could not read the tags of {}".format(target))
        return [name for name in (_objc.pystring(item) for item in _objc.nsarray(value.value)) if name]


def set_tags(path: PathLike, names: Iterable[str]) -> None:
    """Replace the Finder tags on ``path`` with ``names`` (an empty list removes them all)."""
    target = _existing(path)
    names = list(dict.fromkeys(names))  # drop duplicates, keep the order
    with _objc.autorelease_pool():
        objects = (ctypes.c_void_p * len(names))(*[_objc.nsstring(name) for name in names])
        array = _objc.send(
            _objc.cls("NSArray"),
            "arrayWithObjects:count:",
            objects,
            len(names),
            argtypes=(ctypes.c_void_p, NSUInteger),
        )
        error = ctypes.c_void_p()
        ok = _objc.send(
            _url(target),
            "setResourceValue:forKey:error:",
            array,
            _tag_names_key(),
            ctypes.byref(error),
            argtypes=(_objc.id, _objc.id, ctypes.c_void_p),
            restype=BOOL,
        )
        if not ok:
            _raise(error, "could not set the tags of {}".format(target))


def add_tags(path: PathLike, *names: str) -> List[str]:
    """Add tags to ``path``, keeping the ones it has. Return the new list of tags."""
    updated = list(dict.fromkeys([*tags(path), *names]))
    set_tags(path, updated)
    return updated


def remove_tags(path: PathLike, *names: str) -> List[str]:
    """Remove tags from ``path`` (missing ones are ignored). Return the new list of tags."""
    updated = [name for name in tags(path) if name not in names]
    set_tags(path, updated)
    return updated
