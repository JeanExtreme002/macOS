# -*- coding: utf-8 -*-

"""
Configure the Dock: hide it, size and place it, and choose the apps kept in it.

::

    macos.dock.set_autohide(True)
    macos.dock.set_size(48)                      # icons of 48 points
    macos.dock.set_position("left")
    [app.name for app in macos.dock.apps()]      # ['Finder', 'Safari', 'Mail', ...]
    macos.dock.add_app("Visual Studio Code")
    macos.dock.remove_app("Podcasts")

Each change restarts the Dock to apply it: it disappears for a second. No
permission is needed.
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote, urlparse

from . import apps as _apps, defaults
from ._system import require_macos, run as _run
from .errors import AppNotFoundError

__all__ = [
    "DockApp",
    "autohide",
    "set_autohide",
    "size",
    "set_size",
    "position",
    "set_position",
    "apps",
    "add_app",
    "remove_app",
    "restart",
]

_DOMAIN = "com.apple.dock"
_POSITIONS = ("left", "bottom", "right")
_FILE_URL = 15  # _CFURLStringType of a file:// URL


@dataclass(frozen=True)
class DockApp:
    """An app kept in the Dock."""

    name: str
    path: Optional[Path]
    bundle_id: Optional[str]


_SETTLE = 1.5  # seconds a new Dock takes to read its settings, and write them back


def _pid() -> Optional[int]:
    for app in _apps.running(include_background=True):
        if app.bundle_id == "com.apple.dock":
            return app.pid
    return None


def restart() -> None:
    """
    Restart the Dock, so it reads its settings again (the other functions do it for you).

    Returns once the new Dock has started, so the next change reaches it.
    """
    require_macos()
    old = _pid()
    # Killed, not asked to quit: a quitting Dock saves the settings it had over the change.
    # launchd starts a new one right away.
    _run(["killall", "-KILL", "Dock"])
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        pid = _pid()
        if pid is not None and pid != old:
            break
        time.sleep(0.1)
    time.sleep(_SETTLE)


def autohide() -> bool:
    """Whether the Dock hides until the pointer reaches the edge of the screen."""
    return bool(defaults.read(_DOMAIN, "autohide", default=False))


def set_autohide(on: bool = True) -> None:
    """Hide the Dock until the pointer reaches the edge of the screen, or keep it shown."""
    defaults.write(_DOMAIN, "autohide", bool(on))
    restart()


def size() -> int:
    """The size of the Dock's icons, in points (16 to 128)."""
    return int(round(float(defaults.read(_DOMAIN, "tilesize", default=64))))


def set_size(points: int) -> None:
    """Set the size of the Dock's icons, from 16 to 128 points, like the Size slider in System Settings."""
    if not 16 <= points <= 128:
        raise ValueError("size must be from 16 to 128 points, not {}".format(points))
    defaults.write(_DOMAIN, "tilesize", float(points))
    restart()


def position() -> str:
    """Where the Dock is: ``'left'``, ``'bottom'`` or ``'right'``."""
    found = defaults.read(_DOMAIN, "orientation", default="bottom")
    return found if found in _POSITIONS else "bottom"


def set_position(where: str) -> None:
    """Move the Dock to the ``'left'``, ``'bottom'`` or ``'right'`` of the screen."""
    if where not in _POSITIONS:
        raise ValueError("position must be 'left', 'bottom' or 'right', not {!r}".format(where))
    defaults.write(_DOMAIN, "orientation", where)
    restart()


def _tiles() -> List[Dict[str, Any]]:
    return list(defaults.read(_DOMAIN, "persistent-apps", default=[]))


def _tile_path(tile: Dict[str, Any]) -> Optional[Path]:
    url = tile.get("tile-data", {}).get("file-data", {}).get("_CFURLString", "")
    if not url.startswith("file://"):
        return None
    # Resolved, like the app paths it's compared with: /Applications/Safari.app is a link.
    return Path(os.path.realpath(unquote(urlparse(url).path).rstrip("/")))


def apps() -> List[DockApp]:
    """The apps kept in the Dock, left to right (or top to bottom): not the running ones that aren't kept."""
    found = []
    for tile in _tiles():
        data = tile.get("tile-data", {})
        path = _tile_path(tile)
        name = data.get("file-label") or (path.stem if path else "")
        found.append(DockApp(name=name, path=path, bundle_id=data.get("bundle-identifier")))
    return found


def _matches(tile: Dict[str, Any], app: str) -> bool:
    data = tile.get("tile-data", {})
    path = _tile_path(tile)
    wanted = app.casefold()
    return wanted in (
        str(data.get("file-label", "")).casefold(),
        str(data.get("bundle-identifier", "")).casefold(),
        str(path).casefold() if path else "",
    )


def add_app(app: str, *, index: Optional[int] = None) -> DockApp:
    """
    Keep ``app`` in the Dock, at the end or at ``index``, and return it.

    ``app`` is a name (``"Safari"``), a bundle ID or the path of a ``.app``,
    found as :func:`macos.apps.open` finds apps. An app already kept isn't
    added twice.
    """
    path = Path(_apps._locate(app))
    if not path.exists():
        raise AppNotFoundError("{!r} is not an installed app".format(app))
    tiles = _tiles()
    existing = [tile for tile in tiles if _tile_path(tile) == path]
    if existing:
        return next(entry for entry in apps() if entry.path == path)
    bundle_id = _apps._bundle_id(str(path))
    name = path.stem
    tile = {
        "tile-data": {
            "file-data": {"_CFURLString": "file://{}/".format(quote(str(path))), "_CFURLStringType": _FILE_URL},
            "file-label": name,
            **({"bundle-identifier": bundle_id} if bundle_id else {}),
        },
        "tile-type": "file-tile",
    }
    tiles.insert(len(tiles) if index is None else index, tile)
    defaults.write(_DOMAIN, "persistent-apps", tiles)
    restart()
    return DockApp(name=name, path=path, bundle_id=bundle_id)


def remove_app(app: str) -> bool:
    """Take ``app`` (a name, bundle ID or path) out of the Dock; return whether it was there. It stays installed."""
    target = os.path.realpath(os.path.expanduser(app)) if app.endswith(".app") else app
    tiles = _tiles()
    kept = [tile for tile in tiles if not _matches(tile, target)]
    if len(kept) == len(tiles):
        return False
    defaults.write(_DOMAIN, "persistent-apps", kept)
    restart()
    return True
