# -*- coding: utf-8 -*-

"""
Text to speech with the system voices.

::

    macos.say("Hello from Python")
    macos.say("Olá!", voice="Luciana", rate=180)
    [voice.name for voice in macos.speech.voices()]
"""

import subprocess
import threading
from dataclasses import dataclass
from typing import List, Optional

from ._system import require_macos, run
from .errors import NotSupportedError

__all__ = ["say", "voices", "Voice"]


@dataclass(frozen=True)
class Voice:
    """An installed speech voice."""

    name: str
    locale: str
    sample: str


def say(text: str, *, voice: Optional[str] = None, rate: Optional[int] = None, wait: bool = True) -> None:
    """
    Speak ``text`` out loud.

    ``voice`` is a voice name from :func:`~macos.speech.voices` (the system default when
    omitted) and ``rate`` is the speed in words per minute (about 175–200 is
    normal). With ``wait=False`` this returns immediately while speech plays.

    An unknown ``voice`` is not an error: ``say`` falls back to the default
    voice, matching names loosely (``"luciana"`` and ``"Eddy"`` both work).
    """
    args = ["say"]
    if voice is not None:
        args += ["-v", voice]
    if rate is not None:
        args += ["-r", str(rate)]
    # Read the text from stdin rather than argv, so text starting with "-"
    # isn't taken for an option.
    args += ["-f", "-"]

    if wait:
        run(args, input=text)
        return

    require_macos()
    try:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise NotSupportedError("the 'say' command was not found on this system") from None

    # communicate() feeds stdin, tolerates say exiting early (no
    # BrokenPipeError) and reaps the process, so no zombie is left behind.
    threading.Thread(target=process.communicate, args=(text.encode("utf-8"),), daemon=True).start()


def voices() -> List[Voice]:
    """Return the voices installed on this Mac."""
    found = []
    for line in run(["say", "-v", "?"]).splitlines():
        # Format: "<name, may contain spaces> <locale>    # <sample sentence>"
        head, _, sample = line.partition("#")
        parts = head.split()
        if len(parts) >= 2:
            found.append(Voice(name=" ".join(parts[:-1]), locale=parts[-1], sample=sample.strip()))
    return found
