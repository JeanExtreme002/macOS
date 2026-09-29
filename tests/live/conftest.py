"""Fixtures shared by the live tests."""

import time

import pytest


@pytest.fixture
def speech(tmp_path):
    """
    A few seconds of speech, made by ``say``, or of a warbling tone when ``say`` fails.

    On CI runners, say now and then writes files of a few milliseconds, even
    several times in a row (afinfo, independent of pymacos, agrees). The tone
    keeps the editing tests running; only the speech classifier needs real
    speech, and checks the file's name.
    """
    import math
    import re
    import subprocess
    import wave

    path = tmp_path / "speech.aiff"
    for attempt in range(3):
        time.sleep(attempt)
        subprocess.run(["say", "-o", str(path), "Good morning everyone, today we talk about the ocean."], check=True)
        details = subprocess.run(["afinfo", str(path)], capture_output=True, text=True, check=True).stdout
        found = re.search(r"estimated duration: ([0-9.]+)", details)
        if found and float(found.group(1)) > 2:
            return path
    rate, seconds = 22050, 2.6
    samples = bytearray()
    for index in range(int(rate * seconds)):
        moment = index / rate
        pitch = 220 + 80 * math.sin(2 * math.pi * 3 * moment)
        level = 0.3 + 0.2 * math.sin(2 * math.pi * 2 * moment)
        samples += int(32767 * level * math.sin(2 * math.pi * pitch * moment)).to_bytes(2, "little", signed=True)
    raw = tmp_path / "tone.wav"
    with wave.open(str(raw), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(bytes(samples))
    tone = tmp_path / "tone.aiff"
    subprocess.run(["afconvert", "-f", "AIFF", "-d", "BEI16", str(raw), str(tone)], check=True)
    return tone
