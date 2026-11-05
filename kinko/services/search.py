"""Search that ignores full-/half-width, upper/lower case and hiragana/katakana differences."""
from __future__ import annotations

import unicodedata

_KATA_START, _KATA_END = 0x30A1, 0x30F6


def normalize(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "").casefold()
    return "".join(chr(ord(c) - 0x60) if _KATA_START <= ord(c) <= _KATA_END else c for c in s)


def tokens(query: str) -> list[str]:
    return [t for t in normalize(query).split() if t]


def matches(haystack: str, toks: list[str]) -> bool:
    return all(t in haystack for t in toks)
