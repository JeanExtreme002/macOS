# -*- coding: utf-8 -*-

"""
Search files with Spotlight and read their metadata.

::

    macos.spotlight.search("kind:pdf invoice")            # [PosixPath(...), ...]
    macos.spotlight.search_name("report", folder="~/Documents")
    macos.spotlight.metadata("photo.jpg")["kMDItemPixelHeight"]

Uses the ``mdfind`` and ``mdls`` commands, so results come instantly from the
index Spotlight already keeps, and match what the Spotlight bar finds.
"""

import os
import plistlib
import subprocess
from itertools import islice
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ._system import require_macos
from .errors import CommandError, NotSupportedError

__all__ = ["search", "search_name", "metadata"]

PathLike = Union[str, "os.PathLike[str]"]


def _folder(folder: Optional[PathLike]) -> List[str]:
    if folder is None:
        return []
    resolved = Path(folder).expanduser().resolve()
    if not resolved.is_dir():
        raise NotADirectoryError(str(resolved)) if resolved.exists() else FileNotFoundError(str(resolved))
    return ["-onlyin", str(resolved)]


_INVALID = "Failed to create query"  # what mdfind prints (on stdout) for a malformed query


def _invalid(query: str) -> ValueError:
    return ValueError("not a valid Spotlight query: {!r}".format(query))


def _mdfind(args: List[str], limit: Optional[int]) -> List[Path]:
    query = args[-1]
    if limit is not None and limit < 0:
        raise ValueError("limit must be zero or more, not {}".format(limit))

    require_macos()
    # No `-interpret`: without it, mdfind already understands Spotlight-bar
    # syntax (plain words, kind:, date:), and with it raw `kMDItem...` queries
    # are taken as text and return wrong results.
    try:
        process = subprocess.Popen(
            ["mdfind", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"
        )
    except FileNotFoundError:
        raise NotSupportedError("the 'mdfind' command was not found on this system") from None
    assert process.stdout is not None and process.stderr is not None

    try:
        # Read lazily: with a limit, stop (and stop mdfind) once there are
        # enough results, instead of collecting every match of a broad query.
        # Read at least one line even with limit=0: that's where a malformed
        # query's diagnostic shows up.
        wanted = None if limit is None else max(limit, 1)
        lines = list(islice((line.rstrip("\n") for line in process.stdout if line.strip()), wanted))
        if lines and lines[0].startswith(_INVALID):
            raise _invalid(query)
        if wanted is None or len(lines) < wanted:
            # mdfind ran to the end, so its exit status is meaningful.
            stderr = process.stderr.read()
            if process.wait() != 0:
                raise CommandError(["mdfind", *args], process.returncode, stderr)
        return [Path(line) for line in lines[:limit]]
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def search(query: str, *, folder: Optional[PathLike] = None, limit: Optional[int] = None) -> List[Path]:
    """
    Return the files matching a Spotlight query.

    ``query`` accepts what the Spotlight bar does: plain words (matched against
    names and contents), filters such as ``kind:pdf`` or ``date:today``, and
    raw metadata queries like ``kMDItemPixelHeight > 1000``. ``folder`` limits
    the search to one folder (recursively), and ``limit`` to that many results.
    """
    return _mdfind([*_folder(folder), query], limit)


def search_name(name: str, *, folder: Optional[PathLike] = None, limit: Optional[int] = None) -> List[Path]:
    """
    Return the files whose name contains ``name``, ignoring case and accents.

    Matches the full file name, extension included (``"report.pdf"``,
    ``"Calculator.app"``), unlike ``mdfind -name``, which matches the
    displayed name.
    """
    # Escape the characters that are special inside a quoted query value, so
    # the name is always matched literally.
    literal = name.replace("\\", "\\\\").replace('"', '\\"').replace("*", "\\*")
    return _mdfind([*_folder(folder), 'kMDItemFSName == "*{}*"cd'.format(literal)], limit)


def metadata(path: PathLike) -> Dict[str, Any]:
    """
    Return the Spotlight metadata of ``path`` as a dict, e.g.
    ``{"kMDItemContentType": "com.adobe.pdf", "kMDItemNumberOfPages": 3, ...}``.

    Dates are :class:`datetime.datetime` objects (in UTC, without a time
    zone) and lists are lists. Files
    outside the index (e.g. in a folder Spotlight skips) only have the basic
    ``kMDItemFS...`` attributes.
    """
    target = Path(path).expanduser().absolute()
    if not os.path.lexists(target):
        raise FileNotFoundError(str(target))

    require_macos()
    try:
        result = subprocess.run(["mdls", "-plist", "-", str(target)], capture_output=True)
    except FileNotFoundError:
        raise NotSupportedError("the 'mdls' command was not found on this system") from None
    if result.returncode != 0:
        raise CommandError(["mdls", "-plist", "-", str(target)], result.returncode, result.stderr.decode("utf-8", "replace"))
    return dict(plistlib.loads(result.stdout))
