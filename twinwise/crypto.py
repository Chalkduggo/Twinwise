"""Password protection for the key file and the library.

Uses AES-256-GCM with a key derived from your password by scrypt, both from the
widely used ``cryptography`` package. Nothing here is home-made cryptography.

There is no password recovery. If the password is lost, the protected file
cannot be opened.
"""
from __future__ import annotations

import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

FORMAT = "twinwise-encrypted/1"
MIN_PASSWORD = 8
_N, _R, _P = 2 ** 15, 8, 1
_KEY_CACHE: dict[tuple[str, bytes], bytes] = {}


class WrongPassword(Exception):
    """The password is missing or does not open this file."""


def check_password(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD:
        raise ValueError(f"Use a password of at least {MIN_PASSWORD} characters.")


def _derive(password: str, salt: bytes) -> bytes:
    ck = (password, salt)
    if ck not in _KEY_CACHE:
        if len(_KEY_CACHE) > 8:
            _KEY_CACHE.clear()
        _KEY_CACHE[ck] = Scrypt(salt=salt, length=32, n=_N, r=_R, p=_P).derive(password.encode("utf-8"))
    return _KEY_CACHE[ck]


def forget_keys() -> None:
    _KEY_CACHE.clear()


def is_envelope(obj) -> bool:
    return isinstance(obj, dict) and obj.get("format") == FORMAT


def encrypt(data: bytes, password: str, kind: str, salt: bytes | None = None) -> dict:
    """Return a JSON-serialisable envelope holding ``data`` encrypted with ``password``."""
    salt = salt or os.urandom(16)
    nonce = os.urandom(12)
    ct = AESGCM(_derive(password, salt)).encrypt(nonce, data, f"{FORMAT}|{kind}".encode())
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return {"format": FORMAT, "kind": kind, "cipher": "AES-256-GCM", "kdf": "scrypt", "n": _N, "r": _R, "p": _P,
            "salt": b64(salt), "nonce": b64(nonce), "data": b64(ct),
            "note": "Encrypted by Twinwise. Open it with Twinwise and your password."}


def decrypt(envelope: dict, password: str | None) -> bytes:
    if not is_envelope(envelope):
        raise ValueError("Not a Twinwise encrypted file.")
    if not password:
        raise WrongPassword("This file is password-protected.")
    try:
        salt = base64.b64decode(envelope["salt"])
        n, r, p = int(envelope["n"]), int(envelope["r"]), int(envelope["p"])
        if not (2 ** 14 <= n <= 2 ** 20 and r == 8 and 1 <= p <= 4):
            raise ValueError("Unsupported protection settings in this file.")
        if n == _N and r == _R and p == _P:
            key = _derive(password, salt)
        else:
            key = Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(password.encode("utf-8"))
        data = AESGCM(key).decrypt(base64.b64decode(envelope["nonce"]), base64.b64decode(envelope["data"]),
                                   f"{FORMAT}|{envelope.get('kind', '')}".encode())
    except InvalidTag:
        _KEY_CACHE.pop((password, base64.b64decode(envelope["salt"])), None)
        raise WrongPassword("Wrong password.") from None
    return data


def envelope_salt(envelope: dict) -> bytes:
    return base64.b64decode(envelope["salt"])


def dumps(envelope: dict) -> str:
    return json.dumps(envelope, indent=2)
