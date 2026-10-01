# -*- coding: utf-8 -*-

"""
Run shortcuts from the Shortcuts app.

::

    macos.shortcuts.list()                           # ['Resize Image', ...]
    macos.shortcuts.run("Make GIF", input=["a.png", "b.png"])
    macos.shortcuts.run("Translate", input="Hola")   # 'Hello'

Uses the ``shortcuts`` command that ships with macOS 12 and later.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Union

from ._system import require_macos, run as _system_run
from .errors import CommandError, NotSupportedError, ShortcutNotFoundError

__all__ = ["list", "run", "ShortcutNotFoundError"]

_list = list

PathLike = Union[str, "os.PathLike[str]"]


def _run(args: List[str]) -> str:
    require_macos()
    try:
        return _system_run(args)
    except NotSupportedError:
        raise NotSupportedError("running shortcuts needs macOS 12 or later (the 'shortcuts' command)") from None


def _exists(name: str) -> bool:
    # Each line reads "Name (IDENTIFIER)"; `run` accepts either.
    for line in _run(["shortcuts", "list", "--show-identifiers"]).splitlines():
        title, _, identifier = line.rpartition(" (")
        if name in (line, title, identifier.rstrip(")")):
            return True
    return False


def list(*, folder: Optional[str] = None) -> List[str]:
    """Return the names of the shortcuts in the Shortcuts app, or only those in ``folder``."""
    args = ["shortcuts", "list"]
    if folder is not None:
        args += ["--folder-name", folder]
    return [name for name in _run(args).splitlines() if name]


def run(
    name: str,
    *,
    input: Union[str, PathLike, Sequence[PathLike], None] = None,
    output: Optional[PathLike] = None,
) -> Optional[str]:
    """
    Run a shortcut and return its text output (``None`` if it produced none).

    ``input`` is what the shortcut receives as *Shortcut Input*:

    - a :class:`str` is passed as text;
    - a :class:`pathlib.Path` (or any path-like object), or a list of them,
      is passed as files.

    When the shortcut outputs a file (an image, a PDF...), pass ``output`` to
    save it there; the return value is then ``None``.
    """
    args = ["shortcuts", "run", name]
    text_file = None

    if isinstance(input, str):
        # The command only takes input as files. A text file becomes text
        # for the shortcut, so write the string to one.
        descriptor, text_file = tempfile.mkstemp(prefix="shortcut-input-", suffix=".txt")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(input)
        args += ["--input-path", text_file]
    elif input is not None:
        paths = [input] if isinstance(input, os.PathLike) else _list(input)
        for path in paths:
            resolved = Path(path).expanduser()
            if not resolved.exists():
                raise FileNotFoundError(str(resolved))
            args += ["--input-path", str(resolved)]

    if output is not None:
        args += ["--output-path", str(Path(output).expanduser())]

    try:
        result = _run(args)
    except CommandError as error:
        # The error message is localized, so ask the app whether the shortcut
        # exists instead of parsing it.
        if not _exists(name):
            raise ShortcutNotFoundError(error.cmd, error.returncode, error.stderr) from None
        raise
    finally:
        if text_file is not None:
            os.unlink(text_file)

    if output is not None or not result:
        return None
    # The command ends text output with a newline of its own.
    return result[:-1] if result.endswith("\n") else result
