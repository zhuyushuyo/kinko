"""Cryptography for KINKO vaults.

* A random 256-bit data key (DEK) encrypts every record with AES-256-GCM.
* The DEK is stored twice, wrapped by
  - a key derived from the master password with Argon2id (random salt per vault), and
  - a key derived from the recovery key with HKDF-SHA256.
* Changing the master password only re-wraps the DEK.
"""
from __future__ import annotations

import os
import unicodedata

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

DEFAULT_KDF = {"alg": "argon2id", "t": 3, "m": 65536, "p": 4}  # 64 MiB
NONCE_LEN = 12
KEY_LEN = 32
SALT_LEN = 16

# Crockford base32: no I, L, O, U, so the key is easy to read and type.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_RK_BYTES = 20  # 160 bits -> 32 characters


class CryptoError(Exception):
    """Decryption failed: wrong key or tampered data."""


def random_bytes(n: int) -> bytes:
    return os.urandom(n)


def new_data_key() -> bytes:
    return os.urandom(KEY_LEN)


def _password_bytes(password: str) -> bytes:
    return unicodedata.normalize("NFC", password).encode("utf-8")


def derive_password_key(password: str, salt: bytes, kdf: dict) -> bytes:
    if kdf.get("alg") != "argon2id":
        raise CryptoError(f"unsupported kdf {kdf.get('alg')}")
    return hash_secret_raw(
        _password_bytes(password), salt,
        time_cost=int(kdf["t"]), memory_cost=int(kdf["m"]), parallelism=int(kdf["p"]),
        hash_len=KEY_LEN, type=Type.ID,
    )


def derive_recovery_key(raw: bytes, salt: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=KEY_LEN, salt=salt, info=b"kinko recovery v1").derive(raw)


def seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(NONCE_LEN)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def unseal(key: bytes, blob: bytes, aad: bytes) -> bytes:
    blob = bytes(blob)
    if len(blob) < NONCE_LEN + 16:
        raise CryptoError("ciphertext too short")
    try:
        return AESGCM(key).decrypt(blob[:NONCE_LEN], blob[NONCE_LEN:], aad)
    except InvalidTag as exc:
        raise CryptoError("authentication failed") from exc


# ---------------------------------------------------------------- recovery key

def new_recovery_key() -> tuple[str, bytes]:
    raw = os.urandom(_RK_BYTES)
    return format_recovery_key(raw), raw


def format_recovery_key(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    chars = []
    for _ in range(_RK_BYTES * 8 // 5):
        chars.append(_ALPHABET[n & 31])
        n >>= 5
    s = "".join(reversed(chars))
    return "-".join(s[i:i + 4] for i in range(0, len(s), 4))


def parse_recovery_key(text: str) -> bytes:
    s = unicodedata.normalize("NFKC", text).upper()
    s = "".join(ch for ch in s if ch.isalnum())
    s = s.translate(str.maketrans({"O": "0", "I": "1", "L": "1", "U": "V"}))
    if len(s) != _RK_BYTES * 8 // 5:
        raise ValueError("recovery key must be 32 characters")
    n = 0
    for ch in s:
        i = _ALPHABET.find(ch)
        if i < 0:
            raise ValueError(f"invalid character {ch!r}")
        n = (n << 5) | i
    return n.to_bytes(_RK_BYTES, "big")
