"""Password, passphrase and PIN generator (uses the secrets module)."""
from __future__ import annotations

import secrets
import string

AMBIGUOUS = set("0Oo1lI|`'\";:,.")
_rng = secrets.SystemRandom()

# Romaji-like syllables: readable "words" without shipping a word list.
_CONSONANTS = ["", "k", "s", "t", "n", "h", "m", "y", "r", "w", "g", "z", "d", "b", "p"]
_SKIP = {"yi", "ye", "wi", "wu", "we", "di", "du"}
_FIX = {"si": "shi", "ti": "chi", "tu": "tsu", "hu": "fu", "zi": "ji"}
SYLLABLES = [_FIX.get(c + v, c + v) for c in _CONSONANTS for v in "aiueo" if c + v not in _SKIP]


def random_password(length: int = 16, upper: bool = True, lower: bool = True, digits: bool = True,
                    symbols: bool = True, symbol_set: str = "!#$%&*+-=?@_", avoid_ambiguous: bool = True) -> str:
    groups = []
    if lower:
        groups.append(string.ascii_lowercase)
    if upper:
        groups.append(string.ascii_uppercase)
    if digits:
        groups.append(string.digits)
    if symbols and symbol_set:
        groups.append(symbol_set)
    if not groups:
        groups = [string.ascii_lowercase]
    if avoid_ambiguous:
        groups = ["".join(c for c in g if c not in AMBIGUOUS) or g for g in groups]
    length = max(int(length), len(groups), 4)
    chars = [secrets.choice(g) for g in groups]  # at least one from each group
    pool = "".join(groups)
    chars += [secrets.choice(pool) for _ in range(length - len(chars))]
    _rng.shuffle(chars)
    return "".join(chars)


def pseudo_word(syllables: int = 3) -> str:
    return "".join(secrets.choice(SYLLABLES) for _ in range(syllables))


def passphrase(words: int = 4, separator: str = "-", capitalize: bool = False, add_digit: bool = True) -> str:
    parts = [pseudo_word(secrets.choice((2, 3, 3))) for _ in range(max(int(words), 2))]
    if capitalize:
        parts = [p.capitalize() for p in parts]
    if add_digit:
        i = secrets.randbelow(len(parts))
        parts[i] = parts[i] + str(secrets.randbelow(10))
    return separator.join(parts)


def pin(length: int = 4) -> str:
    length = max(int(length), 3)
    while True:
        p = "".join(str(secrets.randbelow(10)) for _ in range(length))
        if len(set(p)) == 1:
            continue
        steps = {(int(b) - int(a)) % 10 for a, b in zip(p, p[1:])}
        if steps in ({1}, {9}):
            continue
        return p


def generate(opts: dict) -> str:
    mode = opts.get("mode", "random")
    if mode == "words":
        return passphrase(opts.get("words", 4), opts.get("separator", "-"), opts.get("capitalize", False),
                          opts.get("word_digit", True))
    if mode == "pin":
        return pin(opts.get("pin_length", 4))
    return random_password(opts.get("length", 16), opts.get("upper", True), opts.get("lower", True),
                           opts.get("digits", True), opts.get("symbols", True),
                           opts.get("symbol_set", "!#$%&*+-=?@_"), opts.get("avoid_ambiguous", True))
