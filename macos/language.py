# -*- coding: utf-8 -*-

"""
Detect the language and the sentiment of a text, offline.

::

    macos.language.detect("Olá, tudo bem?")        # 'pt'
    macos.language.guess("Olá, tudo bem?")         # [('pt', 0.99), ('es', 0.004), ...]
    macos.language.sentiment("I love this!")       # 1.0

Uses Apple's NaturalLanguage framework: nothing to install, no network and
no permission.
"""

import ctypes
from functools import lru_cache
from typing import List, Optional, Tuple

from . import _objc
from ._objc import NSInteger, NSUInteger
from ._system import framework

__all__ = ["detect", "guess", "sentiment"]

_PARAGRAPH = 2  # NLTokenUnitParagraph


@lru_cache(maxsize=None)
def _load() -> ctypes.CDLL:
    framework("Foundation")
    return framework("NaturalLanguage")


def _recognizer(text: str) -> int:
    recognizer = _objc.send(_objc.send(_objc.send(_objc.cls("NLLanguageRecognizer"), "alloc"), "init"), "autorelease")
    _objc.send(recognizer, "processString:", _objc.nsstring(text), argtypes=(_objc.id,), restype=None)
    return recognizer


def detect(text: str) -> Optional[str]:
    """
    Return the most likely language of ``text`` as an ISO code (``'pt'``, ``'en'``, ``'zh-Hans'``...).

    Returns ``None`` when there's nothing to detect. A few words are enough,
    but a single word is often guessed wrong: check :func:`guess` for how sure
    the answer is.
    """
    _load()
    if not text.strip():
        return None
    with _objc.autorelease_pool():
        return _objc.pystring(_objc.send(_recognizer(text), "dominantLanguage"))


def guess(text: str, *, limit: int = 3) -> List[Tuple[str, float]]:
    """Return the ``limit`` most likely languages of ``text``, with their probability (0.0 to 1.0)."""
    if limit <= 0:
        raise ValueError("limit must be positive, not {}".format(limit))
    _load()
    if not text.strip():
        return []
    with _objc.autorelease_pool():
        hypotheses = _objc.send(_recognizer(text), "languageHypothesesWithMaximum:", limit, argtypes=(NSUInteger,))
        found = []
        for key in _objc.nsarray(_objc.send(hypotheses, "allKeys")):
            value = _objc.send(hypotheses, "objectForKey:", key, argtypes=(_objc.id,))
            probability = float(_objc.send(value, "doubleValue", restype=ctypes.c_double))
            found.append((_objc.pystring(key) or "", round(probability, 4)))
    return sorted(found, key=lambda pair: -pair[1])


def sentiment(text: str) -> Optional[float]:
    """
    Score how positive ``text`` sounds, from -1.0 (very negative) to 1.0 (very positive).

    Returns ``None`` for empty text. The score is a rough signal, best for
    comparing texts such as reviews or messages: a neutral sentence won't
    always come out at exactly 0.
    """
    library = _load()
    # The tagger scores one paragraph at a time: treat the text as one.
    flat = " ".join(text.split())
    if not flat:
        return None
    scheme = ctypes.c_void_p.in_dll(library, "NLTagSchemeSentimentScore").value
    if scheme is None:  # NaturalLanguage without sentiment support (before macOS 10.15)
        return None
    with _objc.autorelease_pool():
        tagger = _objc.send(_objc.cls("NLTagger"), "alloc")
        tagger = _objc.send(tagger, "initWithTagSchemes:", _objc.nsarray_of([scheme]), argtypes=(_objc.id,))
        _objc.send(tagger, "autorelease")
        _objc.send(tagger, "setString:", _objc.nsstring(flat), argtypes=(_objc.id,), restype=None)
        tag = _objc.send(
            tagger,
            "tagAtIndex:unit:scheme:tokenRange:",
            0,
            _PARAGRAPH,
            scheme,
            None,
            argtypes=(NSUInteger, NSInteger, _objc.id, ctypes.c_void_p),
        )
        score = _objc.pystring(tag)
    return float(score) if score else None
