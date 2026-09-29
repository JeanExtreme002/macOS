# -*- coding: utf-8 -*-

"""
Finder operations: reveal files, move them to the Trash, manage tags and aliases, and watch folders.

::

    macos.finder.reveal("report.pdf")
    macos.finder.trash("old.log")                 # Path in ~/.Trash
    macos.finder.add_tags("report.pdf", "Work")
    macos.finder.tags("report.pdf")               # ['Work']
    macos.finder.resolve_alias("Projects alias")  # PosixPath('/Users/alice/Documents/Projects')

    for event in macos.finder.watch("~/Downloads"):
        print(event.kind, event.path)             # created /Users/alice/Downloads/report.pdf

Trash and tags go through Foundation (``NSFileManager``/``NSURL``), the same
APIs Finder itself uses: a trashed file can be restored with *Put Back*, and
tags show up in Finder's sidebar and in Spotlight.
"""

import collections
import ctypes
import fnmatch
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Union

from . import _cf, _objc
from ._objc import BOOL, NSUInteger
from ._system import applescript, framework, run as _run
from .errors import MacOSError

__all__ = [
    "reveal",
    "trash",
    "tags",
    "set_tags",
    "add_tags",
    "remove_tags",
    "thumbnail",
    "is_alias",
    "resolve_alias",
    "make_alias",
    "Event",
    "watch",
    "wait_for_change",
    "selection",
    "current_folder",
    "compress",
    "extract",
    "quick_look",
    "show_hidden_files",
    "set_show_hidden_files",
    "show_extensions",
    "set_show_extensions",
    "show_path_bar",
    "set_show_path_bar",
    "show_status_bar",
    "set_show_status_bar",
    "show_desktop_icons",
    "set_show_desktop_icons",
    "default_view",
    "set_default_view",
    "show_library_folder",
    "set_show_library_folder",
    "new_window_folder",
    "set_new_window_folder",
    "search_scope",
    "set_search_scope",
    "show_full_path_in_title",
    "set_show_full_path_in_title",
    "restart",
    "folders_first",
    "set_folders_first",
    "extension_change_warning",
    "set_extension_change_warning",
    "remove_old_trash_items",
    "set_remove_old_trash_items",
    "drives_on_desktop",
    "set_show_drives_on_desktop",
]

PathLike = Union[str, "os.PathLike[str]"]


def _existing(path: PathLike) -> Path:
    resolved = Path(path).expanduser().absolute()
    if not os.path.lexists(resolved):
        raise FileNotFoundError(str(resolved))
    return resolved


def _raise(error: ctypes.c_void_p, what: str) -> None:
    raise MacOSError("{}: {}".format(what, _objc.error_message(error) or "unknown error"))


@lru_cache(maxsize=None)
def _tag_names_key() -> int:
    return ctypes.c_void_p.in_dll(framework("Foundation"), "NSURLTagNamesKey").value or 0


def reveal(path: PathLike) -> None:
    """Open a Finder window with ``path`` selected."""
    # Through LaunchServices (`open -R`), which, unlike asking NSWorkspace,
    # also brings Finder to the front when called from a script.
    _run(["open", "-R", str(_existing(path))])


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
            _objc.file_url(source),
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
            _objc.file_url(target),
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
            _objc.file_url(target),
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


_MAX_THUMBNAIL = 4096


@lru_cache(maxsize=None)
def _graphics() -> ctypes.CDLL:
    cg = framework("CoreGraphics")
    cg.CGImageGetWidth.argtypes = (ctypes.c_void_p,)
    cg.CGImageGetWidth.restype = ctypes.c_size_t
    cg.CGImageGetHeight.argtypes = (ctypes.c_void_p,)
    cg.CGImageGetHeight.restype = ctypes.c_size_t
    cg.CGColorSpaceCreateDeviceRGB.argtypes = ()
    cg.CGColorSpaceCreateDeviceRGB.restype = ctypes.c_void_p
    cg.CGColorSpaceRelease.argtypes = (ctypes.c_void_p,)
    cg.CGColorSpaceRelease.restype = None
    cg.CGBitmapContextCreate.argtypes = (
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    cg.CGBitmapContextCreate.restype = ctypes.c_void_p
    cg.CGContextSetInterpolationQuality.argtypes = (ctypes.c_void_p, ctypes.c_int32)
    cg.CGContextSetInterpolationQuality.restype = None
    cg.CGContextDrawImage.argtypes = (ctypes.c_void_p, _objc.CGRect, ctypes.c_void_p)
    cg.CGContextDrawImage.restype = None
    cg.CGBitmapContextCreateImage.argtypes = (ctypes.c_void_p,)
    cg.CGBitmapContextCreateImage.restype = ctypes.c_void_p
    cg.CGContextRelease.argtypes = (ctypes.c_void_p,)
    cg.CGContextRelease.restype = None
    return cg


def _fit(image: int, size: int) -> Optional[int]:
    """A new ``CGImage`` scaled so its largest side is ``size`` pixels (caller releases it), or ``None``."""
    cg = _graphics()
    width, height = cg.CGImageGetWidth(image), cg.CGImageGetHeight(image)
    scale = size / max(width, height, 1)
    new_width, new_height = max(1, round(width * scale)), max(1, round(height * scale))
    space = cg.CGColorSpaceCreateDeviceRGB()
    # 8 bits per component, premultiplied alpha last (kCGImageAlphaPremultipliedLast).
    context = cg.CGBitmapContextCreate(None, new_width, new_height, 8, 0, space, 1)
    cg.CGColorSpaceRelease(space)
    if not context:
        return None
    try:
        cg.CGContextSetInterpolationQuality(context, 3)  # kCGInterpolationHigh
        rect = _objc.CGRect(_objc.CGPoint(0, 0), _objc.CGSize(new_width, new_height))
        cg.CGContextDrawImage(context, rect, image)
        return cg.CGBitmapContextCreateImage(context) or None
    finally:
        cg.CGContextRelease(context)


@lru_cache(maxsize=None)
def _quicklook() -> ctypes.CDLL:
    quicklook = framework("QuickLook")
    quicklook.QLThumbnailImageCreate.argtypes = (ctypes.c_void_p, ctypes.c_void_p, _objc.CGSize, ctypes.c_void_p)
    quicklook.QLThumbnailImageCreate.restype = ctypes.c_void_p
    return quicklook


def _encode(image: Optional[int]) -> bytes:
    """Encode an owned ``CGImage`` as PNG bytes and release it."""
    if not image:
        raise MacOSError("the preview could not be drawn")
    return _objc.cgimage_png(image)


def thumbnail(path: PathLike, *, size: int = 256) -> bytes:
    """
    Return a preview of ``path`` as PNG bytes, like the ones Finder shows.

    Documents, images, videos and PDFs get a Quick Look preview of their
    content; anything else (apps, folders, unknown files) gets its icon.
    ``size`` is the largest side, in pixels (up to 4096)::

        Path("preview.png").write_bytes(macos.finder.thumbnail("report.pdf"))
    """
    if not 0 < size <= _MAX_THUMBNAIL:
        raise ValueError("size must be from 1 to {}, not {}".format(_MAX_THUMBNAIL, size))
    target = _existing(path)
    framework("AppKit")
    with _objc.autorelease_pool():
        image = _quicklook().QLThumbnailImageCreate(None, _objc.file_url(target), _objc.CGSize(size, size), None)
        if image:
            return _encode(image)

        # No Quick Look preview: fall back to the file's icon, drawn at `size`.
        workspace = _objc.send(_objc.cls("NSWorkspace"), "sharedWorkspace")
        icon = _objc.send(workspace, "iconForFile:", _objc.nsstring(str(target)), argtypes=(_objc.id,))
        rect = _objc.CGRect(_objc.CGPoint(0, 0), _objc.CGSize(size, size))
        cgimage = _objc.send(
            icon,
            "CGImageForProposedRect:context:hints:",
            ctypes.byref(rect),
            None,
            None,
            argtypes=(ctypes.c_void_p, _objc.id, _objc.id),
            restype=ctypes.c_void_p,
        )
        if not cgimage:
            raise MacOSError("the icon of {} could not be drawn".format(target))
        # On a Retina display the icon comes out at twice the size: scale it.
        return _encode(_fit(cgimage, size))


# Finder aliases: files that point to another file or folder, and keep finding
# it when it's moved or renamed. Unlike symbolic links, Python can't follow them.

_SUITABLE_FOR_BOOKMARK_FILE = 1 << 10  # NSURLBookmarkCreationSuitableForBookmarkFile
_WITHOUT_UI = 1 << 8  # NSURLBookmarkResolutionWithoutUI: never ask the user anything
_MAX_HOPS = 32  # an alias of an alias of...: stop at loops


def _is_finder_alias(path: Path) -> bool:
    with _objc.autorelease_pool():
        value = ctypes.c_void_p()
        error = ctypes.c_void_p()
        key = ctypes.c_void_p.in_dll(framework("Foundation"), "NSURLIsAliasFileKey").value
        ok = _objc.send(
            _objc.file_url(path),
            "getResourceValue:forKey:error:",
            ctypes.byref(value),
            key,
            ctypes.byref(error),
            argtypes=(ctypes.c_void_p, _objc.id, ctypes.c_void_p),
            restype=BOOL,
        )
        if not ok:
            _raise(error, "could not read {}".format(path))
        # Foundation counts symbolic links as aliases too; a Finder alias isn't one.
        return bool(value.value and _objc.send(value.value, "boolValue", restype=BOOL)) and not path.is_symlink()


def is_alias(path: PathLike) -> bool:
    """
    Whether ``path`` is a Finder alias (made with *File › Make Alias*).

    Symbolic links aren't aliases: check them with :meth:`pathlib.Path.is_symlink`.
    """
    return _is_finder_alias(_existing(path))


def resolve_alias(path: PathLike) -> Path:
    """
    Return the file or folder a Finder alias points to, even after it was moved or renamed.

    ``os.path.realpath()`` and :meth:`pathlib.Path.resolve` only follow
    symbolic links: to Python, an alias is a small file of its own. This
    follows aliases and symbolic links, one after another, and returns any
    other path as it is, so it's safe to call on every path::

        for item in Path("~/Desktop").expanduser().iterdir():
            print(item.name, "->", macos.finder.resolve_alias(item))

    Raises :class:`FileNotFoundError` when the original is gone. It never
    shows a dialog, but an alias to a network share may mount it.
    """
    current = _existing(path)
    for _ in range(_MAX_HOPS):
        if not (current.is_symlink() or _is_finder_alias(current)):
            return current
        with _objc.autorelease_pool():
            error = ctypes.c_void_p()
            resolved = _objc.send(
                _objc.cls("NSURL"),
                "URLByResolvingAliasFileAtURL:options:error:",
                _objc.file_url(current),
                _WITHOUT_UI,
                ctypes.byref(error),
                argtypes=(_objc.id, NSUInteger, ctypes.c_void_p),
            )
            target = _objc.pystring(_objc.send(resolved, "path")) if resolved else None
            if not target:
                raise FileNotFoundError(
                    "the original of the alias {} was not found: {}".format(
                        current, _objc.error_message(error) or "it may have been deleted"
                    )
                )
        current = Path(target)
    raise MacOSError("{} is part of a loop of aliases".format(path))


def _display_name(path: Path) -> str:
    """The name Finder shows, e.g. ``'Macintosh HD'`` for ``/``, which has no name of its own."""
    with _objc.autorelease_pool():
        manager = _objc.send(_objc.cls("NSFileManager"), "defaultManager")
        name = _objc.pystring(
            _objc.send(manager, "displayNameAtPath:", _objc.nsstring(str(path)), argtypes=(_objc.id,))
        )
    return name or "Disk"


def make_alias(target: PathLike, alias: Optional[PathLike] = None) -> Path:
    """
    Create a Finder alias of ``target``, like *File › Make Alias*, and return its path.

    By default it goes next to ``target``, named ``"<name> alias"`` as Finder
    does. ``alias`` is the path to create, or a folder to create it in::

        macos.finder.make_alias("report.pdf")                      # report.pdf alias
        macos.finder.make_alias("report.pdf", "~/Desktop")         # ~/Desktop/report.pdf alias
        macos.finder.make_alias("report.pdf", "~/Desktop/Report")  # named Report

    Raises :class:`FileExistsError` if something already has the alias's path.
    The alias of a disk (``"/"``) is named after it (``"Macintosh HD alias"``)
    and needs ``alias``, since nothing is next to it.
    """
    original = _existing(target)
    if alias is None and original.parent == original:
        raise ValueError("pass where to create the alias of {}: there's no folder around it".format(original))
    name = "{} alias".format(original.name or _display_name(original))
    if alias is None:
        destination = original.with_name(name)
    else:
        destination = Path(alias).expanduser().absolute()
        if destination.is_dir() and not destination.is_symlink():
            destination = destination / name
    if os.path.lexists(destination):
        raise FileExistsError(str(destination))
    if not destination.parent.is_dir():
        raise FileNotFoundError(str(destination.parent))
    with _objc.autorelease_pool():
        error = ctypes.c_void_p()
        bookmark = _objc.send(
            _objc.file_url(original),
            "bookmarkDataWithOptions:includingResourceValuesForKeys:relativeToURL:error:",
            _SUITABLE_FOR_BOOKMARK_FILE,
            None,
            None,
            ctypes.byref(error),
            argtypes=(NSUInteger, _objc.id, _objc.id, ctypes.c_void_p),
        )
        if not bookmark:
            _raise(error, "could not make an alias of {}".format(original))
        ok = _objc.send(
            _objc.cls("NSURL"),
            "writeBookmarkData:toURL:options:error:",
            bookmark,
            _objc.file_url(destination),
            _SUITABLE_FOR_BOOKMARK_FILE,
            ctypes.byref(error),
            argtypes=(_objc.id, _objc.id, NSUInteger, ctypes.c_void_p),
            restype=BOOL,
        )
        if not ok:
            _raise(error, "could not write the alias {}".format(destination))
    return destination


@dataclass(frozen=True)
class Event:
    """A change in a watched folder."""

    path: Path
    """The file or folder that changed, with symbolic links resolved (``/private/tmp/...`` for ``/tmp/...``)."""
    kind: str
    """``'created'``, ``'modified'``, ``'deleted'`` or ``'renamed'`` (the new name of a moved or renamed item)."""
    is_dir: bool


# FSEventStreamEventFlags
_CREATED, _REMOVED, _RENAMED, _IS_DIR = 0x100, 0x200, 0x800, 0x20000
_FILE_EVENTS, _NO_DEFER = 0x10, 0x2  # FSEventStreamCreateFlags: one event per file, the first one right away
_SINCE_NOW = 0xFFFFFFFFFFFFFFFF  # kFSEventStreamEventIdSinceNow
_LATENCY = 0.1  # seconds FSEvents gathers events for before calling back

_Callback = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint64),
)


@lru_cache(maxsize=None)
def _core_services() -> ctypes.CDLL:
    services = framework("CoreServices")
    pointer = ctypes.c_void_p
    signatures = {
        "FSEventStreamCreate": (
            (pointer, _Callback, pointer, pointer, ctypes.c_uint64, ctypes.c_double, ctypes.c_uint32),
            pointer,
        ),
        "FSEventStreamScheduleWithRunLoop": ((pointer, pointer, pointer), None),
        "FSEventStreamStart": ((pointer,), ctypes.c_bool),
        "FSEventStreamStop": ((pointer,), None),
        "FSEventStreamInvalidate": ((pointer,), None),
        "FSEventStreamRelease": ((pointer,), None),
    }
    for name, (argtypes, restype) in signatures.items():
        function = getattr(services, name)
        function.argtypes = argtypes
        function.restype = restype
    run_loop = framework("CoreFoundation")
    run_loop.CFRunLoopGetCurrent.argtypes = ()
    run_loop.CFRunLoopGetCurrent.restype = pointer
    run_loop.CFRunLoopRunInMode.argtypes = (pointer, ctypes.c_double, ctypes.c_bool)
    run_loop.CFRunLoopRunInMode.restype = ctypes.c_int32
    return services


def _kind(path: Path, flags: int, seen: Set[Path]) -> str:
    """
    What happened to ``path``.

    FSEvents' flags pile up: a file's later changes still carry the
    "created" flag, and a rename flags both names. So a path that no longer
    exists was deleted (or moved away), and only the first sighting of a
    created path counts as its creation.
    """
    if not os.path.lexists(str(path)):
        seen.discard(path)
        return "deleted"
    first = path not in seen
    seen.add(path)
    if flags & _RENAMED and not flags & _CREATED:
        return "renamed"
    if flags & _CREATED and first:
        return "created"
    if flags & _RENAMED and first:
        return "renamed"
    return "modified"


def _matches(name: str, pattern: Union[str, Sequence[str], None]) -> bool:
    if pattern is None:
        return True
    patterns = [pattern] if isinstance(pattern, str) else pattern
    # Mac file systems ignore case, and so does the match.
    return any(fnmatch.fnmatchcase(name.casefold(), wanted.casefold()) for wanted in patterns)


def watch(
    path: PathLike,
    *,
    pattern: Union[str, Sequence[str], None] = None,
    recursive: bool = True,
    timeout: Optional[float] = None,
) -> Iterator[Event]:
    """
    Yield an :class:`Event` each time something changes in the folder ``path``, as it happens.

    ::

        for event in macos.finder.watch("~/Downloads"):
            if event.kind == "created" and event.path.suffix == ".pdf":
                print("new PDF:", event.path.name)

    It goes on until you ``break`` out of the loop, or ``timeout`` seconds
    pass. ``pattern`` keeps the files whose name matches it, such as
    ``"*.pdf"`` (or any of a list, ignoring case), and ``recursive=False``
    ignores what happens in subfolders. Writing a
    new file usually yields ``'created'`` and then ``'modified'``; saving
    over a file yields ``'modified'``. Uses FSEvents, like Spotlight and Time
    Machine: no polling, and no permission needed, except that the
    Desktop, Documents and Downloads folders ask for access the first time,
    like any access to them.
    """
    folder = Path(os.path.realpath(os.path.expanduser(str(path))))
    if not folder.is_dir():
        raise NotADirectoryError(str(folder))
    services, run_loop = _core_services(), framework("CoreFoundation")
    pending: "collections.deque[Event]" = collections.deque()
    seen: Set[Path] = set()

    def changed(stream: int, info: int, count: int, paths: int, flags: "ctypes._Pointer", ids: "ctypes._Pointer") -> None:
        names = ctypes.cast(paths, ctypes.POINTER(ctypes.c_char_p))
        for index in range(count):
            changed_path = Path(os.fsdecode(names[index]))
            if changed_path == folder or (not recursive and changed_path.parent != folder):
                continue
            if not _matches(changed_path.name, pattern):
                continue
            pending.append(Event(changed_path, _kind(changed_path, flags[index], seen), bool(flags[index] & _IS_DIR)))

    callback = _Callback(changed)  # kept alive for as long as the stream runs
    with _cf.owned(_cf.from_python([str(folder)])) as paths:
        stream = services.FSEventStreamCreate(None, callback, None, paths, _SINCE_NOW, _LATENCY, _FILE_EVENTS | _NO_DEFER)
    if not stream:
        raise MacOSError("could not watch {}".format(folder))
    mode = ctypes.c_void_p.in_dll(run_loop, "kCFRunLoopDefaultMode")
    services.FSEventStreamScheduleWithRunLoop(stream, run_loop.CFRunLoopGetCurrent(), mode)
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        if not services.FSEventStreamStart(stream):
            raise MacOSError("could not watch {}".format(folder))
        while True:
            while pending:
                yield pending.popleft()
            remaining = 0.1 if deadline is None else min(0.1, deadline - time.monotonic())
            if remaining <= 0:
                return
            run_loop.CFRunLoopRunInMode(mode, remaining, True)
    finally:
        services.FSEventStreamStop(stream)
        services.FSEventStreamInvalidate(stream)
        services.FSEventStreamRelease(stream)


def wait_for_change(
    path: PathLike,
    *,
    pattern: Union[str, Sequence[str], None] = None,
    recursive: bool = True,
    timeout: Optional[float] = None,
) -> Optional[Event]:
    """
    Wait until something changes in the folder ``path``, and return that :class:`Event`.

    Returns ``None`` if ``timeout`` seconds pass first. Handy to wait for a
    download or an export to show up::

        event = macos.finder.wait_for_change("~/Downloads", pattern="*.pdf", timeout=60)

    ``pattern`` and ``recursive`` work as in :func:`watch`.
    """
    for event in watch(path, pattern=pattern, recursive=recursive, timeout=timeout):
        return event
    return None


_SELECTION = """
on run argv
    tell application "Finder" to set picked to selection as alias list
    set out to ""
    repeat with item_ in picked
        set out to out & (POSIX path of item_) & (ASCII character 30)
    end repeat
    return out
end run
"""

_CURRENT_FOLDER = """
on run argv
    tell application "Finder"
        if (count of Finder windows) is 0 then return ""
        try
            return POSIX path of (target of front Finder window as alias)
        on error
            return ""
        end try
    end tell
end run
"""


def selection() -> List[Path]:
    """
    The files and folders selected in Finder, in the window in front (or on the Desktop).

    Handy for scripts that act on what you picked, from a hotkey or a Shortcut::

        for path in macos.finder.selection():
            macos.image.convert(path, path.with_suffix(".jpg"))

    Goes through AppleScript: the first time, macOS asks to allow the app
    running Python to control Finder.
    """
    output = applescript("Finder", _SELECTION).rstrip("\n")
    return [Path(item.rstrip("/") or "/") for item in output.split("\x1e") if item]


def current_folder() -> Optional[Path]:
    """
    The folder shown in Finder's window in front, or ``None`` with no window open.

    Places that aren't folders (Recents, AirDrop, a search) give ``None`` too.
    """
    output = applescript("Finder", _CURRENT_FOLDER).rstrip("\n")
    return Path(output.rstrip("/") or "/") if output else None


_FINDER = "com.apple.finder"


def restart() -> None:
    """Relaunch Finder, so it reads its settings again (the ``set_show_*`` functions do it for you)."""
    _run(["killall", "Finder"])  # macOS opens it again right away, with its windows


def _setting(domain: str, key: str) -> bool:
    from . import defaults

    return bool(defaults.read(domain, key, default=False))


def _set(domain: str, key: str, on: bool) -> None:
    from . import defaults

    defaults.write(domain, key, bool(on))
    restart()


def show_hidden_files() -> bool:
    """Whether Finder shows hidden files (``.git``, ``.env``...), as ⌘⇧. toggles."""
    return _setting(_FINDER, "AppleShowAllFiles")


def set_show_hidden_files(on: bool = True) -> None:
    """Show hidden files in Finder, or hide them again. Relaunches Finder."""
    _set(_FINDER, "AppleShowAllFiles", on)


def show_extensions() -> bool:
    """Whether Finder shows every file name's extension (``.pdf``, ``.txt``...)."""
    return _setting("NSGlobalDomain", "AppleShowAllExtensions")


def set_show_extensions(on: bool = True) -> None:
    """Show every file name's extension in Finder, like Finder › Settings › Advanced. Relaunches Finder."""
    _set("NSGlobalDomain", "AppleShowAllExtensions", on)


def show_path_bar() -> bool:
    """Whether Finder windows show the path bar, the folders leading to the one shown."""
    return _setting(_FINDER, "ShowPathbar")


def set_show_path_bar(on: bool = True) -> None:
    """Show the path bar at the bottom of Finder windows, or hide it. Relaunches Finder."""
    _set(_FINDER, "ShowPathbar", on)


def show_status_bar() -> bool:
    """Whether Finder windows show the status bar, with the item count and the free space."""
    return _setting(_FINDER, "ShowStatusBar")


def set_show_status_bar(on: bool = True) -> None:
    """Show the status bar at the bottom of Finder windows, or hide it. Relaunches Finder."""
    _set(_FINDER, "ShowStatusBar", on)


def compress(path: PathLike, output: Optional[PathLike] = None) -> Path:
    """
    Zip a file or folder, like Finder's *Compress*, and return the ``.zip``.

    By default the archive goes next to it, as ``<name>.zip``. It keeps what
    plain zip tools lose: extended attributes, tags, resource forks and
    permissions. Uses the ``ditto`` command, as Finder does.
    """
    source = _existing(path)
    target = Path(output).expanduser().absolute() if output is not None else source.with_name(source.name + ".zip")
    if target.suffix.lower() != ".zip":
        raise ValueError("the archive must end in .zip, not {!r}".format(target.name))
    _run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(source), str(target)])
    return target


def extract(archive: PathLike, destination: Optional[PathLike] = None) -> Path:
    """
    Unzip an archive, like double-clicking it, into ``destination`` (by default, its folder); return ``destination``.

    Keeps the attributes and permissions :func:`compress` stores.
    """
    source = _existing(archive)
    target = Path(destination).expanduser().absolute() if destination is not None else source.parent
    target.mkdir(parents=True, exist_ok=True)
    _run(["ditto", "-x", "-k", str(source), str(target)])
    return target


def quick_look(path: PathLike) -> None:
    """
    Show a file in Quick Look, the preview Space opens in Finder, and return at once.

    The preview stays until the user closes it.
    """
    import subprocess

    from ._system import require_macos

    source = _existing(path)
    require_macos()
    subprocess.Popen(
        ["qlmanage", "-p", str(source)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # outlives the script, as a preview opened from Finder does
    )


def show_desktop_icons() -> bool:
    """Whether the desktop shows its files and folders (and mounted disks)."""
    return _setting_default(_FINDER, "CreateDesktop", True)


def set_show_desktop_icons(on: bool = True) -> None:
    """
    Show the desktop's icons, or hide them all (``False``), for a clean screen in presentations and recordings.

    The files stay on the Desktop, in its folder. Relaunches Finder.
    """
    _set(_FINDER, "CreateDesktop", on)


def _setting_default(domain: str, key: str, default: bool) -> bool:
    from . import defaults

    return bool(defaults.read(domain, key, default=default))


_VIEWS = {"icons": "icnv", "list": "Nlsv", "columns": "clmv", "gallery": "glyv"}


def default_view() -> str:
    """How Finder shows folders that have no view of their own: ``'icons'``, ``'list'``, ``'columns'`` or ``'gallery'``."""
    from . import defaults

    code = defaults.read(_FINDER, "FXPreferredViewStyle", default="icnv")
    return next((view for view, found in _VIEWS.items() if found == code), "icons")


def set_default_view(view: str) -> None:
    """
    Show folders as ``'icons'``, a ``'list'``, ``'columns'`` or a ``'gallery'`` by default. Relaunches Finder.

    Folders already shown another way keep their own view.
    """
    from . import defaults

    if view not in _VIEWS:
        raise ValueError("view must be one of {}, not {!r}".format(", ".join(_VIEWS), view))
    defaults.write(_FINDER, "FXPreferredViewStyle", _VIEWS[view])
    restart()


_UF_HIDDEN = 0x8000  # stat.UF_HIDDEN: the flag chflags hidden sets


def show_library_folder() -> bool:
    """Whether your Library folder (``~/Library``) shows in Finder; macOS hides it."""
    from ._system import require_macos

    require_macos()
    flags = getattr(os.stat(str(Path.home() / "Library")), "st_flags", 0)  # only BSD systems have file flags
    return not flags & _UF_HIDDEN


def set_show_library_folder(on: bool = True) -> None:
    """Show your Library folder in Finder, or hide it again, as ``chflags nohidden ~/Library`` does."""
    _run(["chflags", "nohidden" if on else "hidden", str(Path.home() / "Library")])


_NEW_WINDOW_TARGETS = {"PfHm": "~", "PfDe": "~/Desktop", "PfDo": "~/Documents"}


def new_window_folder() -> Path:
    """The folder a new Finder window (⌘N) opens."""
    from . import defaults

    target = defaults.read(_FINDER, "NewWindowTarget", default="PfHm")
    if target in _NEW_WINDOW_TARGETS:
        return Path(os.path.expanduser(_NEW_WINDOW_TARGETS[target]))
    url = defaults.read(_FINDER, "NewWindowTargetPath", default="")
    from urllib.parse import unquote, urlparse

    return Path(unquote(urlparse(url).path)).absolute() if url else Path.home()


def set_new_window_folder(folder: PathLike) -> None:
    """Open new Finder windows (⌘N) in ``folder``, such as ``"~/Downloads"``. Relaunches Finder."""
    from urllib.parse import quote

    from . import defaults

    target = _existing(folder)
    if not target.is_dir():
        raise NotADirectoryError(str(target))
    defaults.write(_FINDER, "NewWindowTarget", "PfLo")
    defaults.write(_FINDER, "NewWindowTargetPath", "file://{}/".format(quote(str(target))))
    restart()


_SCOPES = {"this_mac": "SCev", "current_folder": "SCcf", "previous": "SCsp"}


def search_scope() -> str:
    """Where a Finder search looks first: ``'this_mac'``, ``'current_folder'`` or ``'previous'`` (the last scope used)."""
    from . import defaults

    code = defaults.read(_FINDER, "FXDefaultSearchScope", default="SCev")
    return next((scope for scope, found in _SCOPES.items() if found == code), "this_mac")


def set_search_scope(scope: str) -> None:
    """
    Search the ``'current_folder'``, the whole Mac (``'this_mac'``), or the ``'previous'`` scope by default.

    Relaunches Finder.
    """
    from . import defaults

    if scope not in _SCOPES:
        raise ValueError("scope must be one of {}, not {!r}".format(", ".join(_SCOPES), scope))
    defaults.write(_FINDER, "FXDefaultSearchScope", _SCOPES[scope])
    restart()


def show_full_path_in_title() -> bool:
    """Whether Finder windows show the folder's full path in their title."""
    return _setting_default(_FINDER, "_FXShowPosixPathInTitle", False)


def set_show_full_path_in_title(on: bool = True) -> None:
    """Show the folder's full path (``/Users/alice/Projects``) in Finder windows' title. Relaunches Finder."""
    _set(_FINDER, "_FXShowPosixPathInTitle", on)


def folders_first() -> bool:
    """Whether folders come before files when windows are sorted by name."""
    return _setting_default(_FINDER, "_FXSortFoldersFirst", False)


def set_folders_first(on: bool = True) -> None:
    """Keep folders before files when sorting by name, in windows and on the desktop, or mix them."""
    from . import defaults

    defaults.write(_FINDER, "_FXSortFoldersFirstOnDesktop", bool(on))
    _set(_FINDER, "_FXSortFoldersFirst", on)


def extension_change_warning() -> bool:
    """Whether Finder asks before a file's extension is changed."""
    return _setting_default(_FINDER, "FXEnableExtensionChangeWarning", True)


def set_extension_change_warning(on: bool = True) -> None:
    """Ask before changing a file's extension, or rename it straight away (``False``)."""
    _set(_FINDER, "FXEnableExtensionChangeWarning", on)


def remove_old_trash_items() -> bool:
    """Whether items are deleted from the Trash after 30 days."""
    return _setting_default(_FINDER, "FXRemoveOldTrashItems", False)


def set_remove_old_trash_items(on: bool = True) -> None:
    """Delete items from the Trash after 30 days, or keep them until it's emptied."""
    _set(_FINDER, "FXRemoveOldTrashItems", on)


_DESKTOP_DRIVES = {
    "internal": ("ShowHardDrivesOnDesktop", False),
    "external": ("ShowExternalHardDrivesOnDesktop", True),
    "removable": ("ShowRemovableMediaOnDesktop", True),
    "servers": ("ShowMountedServersOnDesktop", False),
}


def drives_on_desktop() -> Dict[str, bool]:
    """
    Which disks show on the desktop: ``{"internal": False, "external": True, "removable": True, "servers": False}``.
    """
    return {kind: _setting_default(_FINDER, key, default) for kind, (key, default) in _DESKTOP_DRIVES.items()}


def set_show_drives_on_desktop(
    *,
    internal: Optional[bool] = None,
    external: Optional[bool] = None,
    removable: Optional[bool] = None,
    servers: Optional[bool] = None,
) -> None:
    """
    Show or hide each kind of disk on the desktop; the ones left out stay as they are.

    ::

        macos.finder.set_show_drives_on_desktop(external=False, servers=True)

    ``internal`` is the Mac's own disk, ``external`` the USB and Thunderbolt
    ones, ``removable`` CDs and the like, ``servers`` the network shares.
    """
    from . import defaults

    wanted = {"internal": internal, "external": external, "removable": removable, "servers": servers}
    if all(on is None for on in wanted.values()):
        raise ValueError("say which disks to show or hide: internal=, external=, removable= or servers=")
    for kind, on in wanted.items():
        if on is not None:
            defaults.write(_FINDER, _DESKTOP_DRIVES[kind][0], bool(on))
    restart()
