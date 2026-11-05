"""A small, dependency-free password strength estimate (score 0-4)."""
from __future__ import annotations

import math
import re
import string
from dataclasses import dataclass

LABEL_KEYS = ("strength.0", "strength.1", "strength.2", "strength.3", "strength.4")

_COMMON = {
    "password", "passw0rd", "p@ssw0rd", "qwerty", "qwertyuiop", "asdfgh", "asdfghjkl", "zxcvbn", "zxcvbnm",
    "123456", "1234567", "12345678", "123456789", "1234567890", "111111", "000000", "123123", "654321",
    "abc123", "iloveyou", "admin", "letmein", "welcome", "monkey", "dragon", "sunshine", "princess",
    "football", "baseball", "master", "login", "hello", "secret", "shadow", "superman", "trustno1",
    "qwe123", "1q2w3e", "1qaz2wsx", "zaq12wsx", "pokemon", "naruto", "sakura", "doraemon", "tokyo",
    "nippon", "japan", "kawaii", "aishiteru", "daisuki", "yamada", "suzuki", "tanaka", "test", "guest",
    "pass", "abcd", "abcdef", "aaaaaa",
}
_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890", "abcdefghijklmnopqrstuvwxyz")


@dataclass
class Strength:
    score: int
    bits: float

    @property
    def label_key(self) -> str:
        return LABEL_KEYS[self.score]


def _charset(pw: str) -> int:
    size = 0
    if any(c in string.ascii_lowercase for c in pw):
        size += 26
    if any(c in string.ascii_uppercase for c in pw):
        size += 26
    if any(c in string.digits for c in pw):
        size += 10
    if any(c in string.punctuation or c == " " for c in pw):
        size += 33
    if any(ord(c) > 127 for c in pw):
        size += 100
    return max(size, 10)


def _effective_length(pw: str) -> float:
    eff = 0.0
    prev = ""
    for c in pw:
        if prev and (c == prev or abs(ord(c) - ord(prev)) == 1):
            eff += 0.4
        else:
            eff += 1.0
        prev = c
    low = pw.lower()
    for row in _ROWS:
        for n in range(len(row), 3, -1):
            for i in range(len(row) - n + 1):
                if row[i:i + n] in low:
                    eff -= (n - 2) * 0.5
                    break
            else:
                continue
            break
    return max(eff, 1.0)


def estimate(pw: str) -> Strength:
    if not pw:
        return Strength(0, 0.0)
    low = pw.lower()
    if low in _COMMON or len(set(pw)) == 1:
        return Strength(0, 0.0)
    bits = _effective_length(pw) * math.log2(_charset(pw))
    for word in _COMMON:
        if len(word) >= 4 and word in low:
            bits -= 12
    if re.search(r"(19|20)\d\d", pw):
        bits -= 6
    if pw.isdigit():
        bits = min(bits, len(pw) * 3.3)
    bits = max(bits, 0.0)
    if bits < 28:
        score = 0
    elif bits < 40:
        score = 1
    elif bits < 60:
        score = 2
    elif bits < 80:
        score = 3
    else:
        score = 4
    return Strength(score, round(bits, 1))
