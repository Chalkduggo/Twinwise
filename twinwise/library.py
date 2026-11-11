"""The local library: everything Twinwise learns, stored on this computer only.

Layout of the library folder (default ``~/.twinwise``; override with the
``TWINWISE_HOME`` environment variable):

    safe_words.txt      one safe word or phrase per line (added by you)
    names.json          real name -> fake label, with category
    ids.json            real ID -> fake ID
    factors.json        stable scale factors per column name, so trends survive month to month
    templates/*.json    saved layouts with your column decisions
    history.jsonl       one line per exported twin (local audit trail)

With library protection switched on, the files that hold real values (names,
IDs, factors and history) are replaced by one password-encrypted file,
``library.enc``. Safe words and templates stay as plain files: they hold
headings and your column rules, not data values.
"""
from __future__ import annotations

import json
import os
import secrets
import random
import re
import string
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import crypto
from .crypto import WrongPassword

_LOCK = threading.RLock()
_PASSWORD: str | None = None          # held in memory only while Twinwise runs
ENC_FILE = "library.enc"
PLAIN_FILES = ("names.json", "ids.json", "factors.json", "history.jsonl")


class LibraryLocked(Exception):
    """The library is password-protected and has not been unlocked in this session."""


def is_protected(home: Path | str | None = None) -> bool:
    return (Path(home).expanduser() if home else default_home()).joinpath(ENC_FILE).exists()


def is_unlocked() -> bool:
    return _PASSWORD is not None


def lock() -> None:
    global _PASSWORD
    _PASSWORD = None
    crypto.forget_keys()


def current_password() -> str | None:
    return _PASSWORD


def unlock(password: str, home: Path | str | None = None) -> None:
    """Check ``password`` against the protected library and remember it for this session."""
    global _PASSWORD
    h = Path(home).expanduser() if home else default_home()
    env = json.loads((h / ENC_FILE).read_text(encoding="utf-8"))
    crypto.decrypt(env, password)          # raises WrongPassword
    _PASSWORD = password


def set_protection(new_password: str | None, home: Path | str | None = None) -> None:
    """Turn protection on (or change the password) with ``new_password``; turn it off with ``None``."""
    global _PASSWORD
    lib = Library.load(home)               # needs to be unlocked if currently protected
    if new_password:
        crypto.check_password(new_password)
    _PASSWORD = new_password or None
    lib._kdf_salt = None
    lib.save()


def default_home() -> Path:
    env = os.environ.get("TWINWISE_HOME")
    return Path(env).expanduser() if env else Path.home() / ".twinwise"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip()).lower()


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


@dataclass
class Library:
    home: Path = field(default_factory=default_home)
    safe_words: set[str] = field(default_factory=set)
    names: dict[str, dict] = field(default_factory=dict)      # norm(real) -> {real, fake, category}
    ids: dict[str, str] = field(default_factory=dict)          # real -> fake
    factors: dict[str, float] = field(default_factory=dict)    # norm(column name) -> factor
    counters: dict[str, int] = field(default_factory=dict)     # category -> last number used
    salt: str = ""                                             # secret used for per-row variation
    protected: bool = False
    _history: list = field(default_factory=list)               # used only when protected
    _kdf_salt: bytes | None = None

    # ---------- persistence ----------
    @classmethod
    def load(cls, home: Path | str | None = None) -> "Library":
        lib = cls(home=Path(home).expanduser() if home else default_home())
        with _LOCK:
            sw = lib.home / "safe_words.txt"
            if sw.exists():
                lib.safe_words = {_norm(l) for l in sw.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
            enc = lib.home / ENC_FILE
            if enc.exists():
                if _PASSWORD is None:
                    raise LibraryLocked("The library is password-protected. Unlock it first.")
                env = json.loads(enc.read_text(encoding="utf-8"))
                data = json.loads(crypto.decrypt(env, _PASSWORD).decode("utf-8"))
                lib._kdf_salt = crypto.envelope_salt(env)
                lib.protected = True
                lib.names, lib.counters = data.get("names", {}), data.get("counters", {})
                lib.ids, lib.factors = data.get("ids", {}), data.get("factors", {})
                lib.salt, lib._history = data.get("salt", ""), data.get("history", [])
            else:
                data = _read_json(lib.home / "names.json", {})
                lib.names = data.get("names", {})
                lib.counters = data.get("counters", {})
                lib.salt = data.get("salt", "")
                lib.ids = _read_json(lib.home / "ids.json", {})
                lib.factors = _read_json(lib.home / "factors.json", {})
            if not lib.salt:
                lib.salt = secrets.token_hex(16)
        return lib

    def save(self) -> None:
        with _LOCK:
            self.home.mkdir(parents=True, exist_ok=True)
            lines = ["# Twinwise safe words - text on this list is never masked", *sorted(self.safe_words)]
            (self.home / "safe_words.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            if _PASSWORD:
                if not self.protected:          # switching protection on: carry the plain history over
                    self._history = self._plain_history()
                payload = {"names": self.names, "counters": self.counters, "ids": self.ids, "factors": self.factors,
                           "salt": self.salt, "history": self._history}
                env = crypto.encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"), _PASSWORD, "library",
                                     salt=self._kdf_salt)
                self._kdf_salt = crypto.envelope_salt(env)
                tmp = self.home / (ENC_FILE + ".tmp")
                tmp.write_text(crypto.dumps(env), encoding="utf-8")
                tmp.replace(self.home / ENC_FILE)
                for name in PLAIN_FILES:
                    _wipe(self.home / name)
                self.protected = True
            else:
                _write_json(self.home / "names.json", {"names": self.names, "counters": self.counters, "salt": self.salt})
                _write_json(self.home / "ids.json", self.ids)
                _write_json(self.home / "factors.json", self.factors)
                if self.protected:              # switching protection off: write the history back as a plain file
                    with open(self.home / "history.jsonl", "w", encoding="utf-8") as f:
                        for e in self._history:
                            f.write(json.dumps(e, ensure_ascii=False) + "\n")
                    (self.home / ENC_FILE).unlink(missing_ok=True)
                    self.protected = False

    def _plain_history(self) -> list:
        p = self.home / "history.jsonl"
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    # ---------- safe words ----------
    def is_safe(self, text: str) -> bool:
        return _norm(text) in self.safe_words

    def add_safe(self, text: str) -> None:
        self.safe_words.add(_norm(text))
        self.names.pop(_norm(text), None)

    def remove_safe(self, text: str) -> None:
        self.safe_words.discard(_norm(text))

    # ---------- names ----------
    def lookup_name(self, real: str) -> dict | None:
        return self.names.get(_norm(real))

    def fake_name(self, real: str, category: str, *, upper: bool = False) -> str:
        """Return the stable fake label for ``real``, creating one if needed."""
        key = _norm(real)
        entry = self.names.get(key)
        if entry is None:
            entry = {"real": str(real).strip(), "category": category, "fake": self._next_label(category)}
            self.names[key] = entry
        fake = entry["fake"]
        return fake.upper() if upper else fake

    def set_name(self, real: str, fake: str, category: str = "Name") -> None:
        self.names[_norm(real)] = {"real": str(real).strip(), "category": category, "fake": fake}
        self.safe_words.discard(_norm(real))

    def forget_name(self, real: str) -> None:
        self.names.pop(_norm(real), None)

    def _next_label(self, category: str) -> str:
        n = self.counters.get(category, 0) + 1
        self.counters[category] = n
        if category == "Channel":
            return f"Channel {_letters(n)}"
        if category == "Title":
            return f"Title {n:03d}"
        if category == "Email":
            return f"user{n}@example.com"
        if category == "Address":
            return f"{100 + n} Sample Street"
        if category == "Code":
            rnd = random.Random(f"code-{n}")
            return "".join(rnd.choice(string.ascii_uppercase) for _ in range(3))
        return f"{category} {n}"

    # ---------- ids ----------
    def fake_id(self, real: str, rng: random.Random) -> str:
        real = str(real)
        if real in self.ids:
            return self.ids[real]
        used = set(self.ids.values())
        for _ in range(1000):
            fake = "".join(
                (rng.choice("123456789") if i == 0 and ch.isdigit() and ch != "0" else rng.choice(string.digits))
                if ch.isdigit() else
                (rng.choice(string.ascii_uppercase) if ch.isupper() else rng.choice(string.ascii_lowercase) if ch.isalpha() else ch)
                for i, ch in enumerate(real)
            )
            if fake != real and fake not in used:
                break
        self.ids[real] = fake
        return fake

    # ---------- stable factors ----------
    def factor_for(self, column: str, rng: random.Random, stable: bool) -> float:
        key = _norm(column) or "_"
        if stable and key in self.factors:
            return self.factors[key]
        f = rng.uniform(0.55, 0.85) if rng.random() < 0.5 else rng.uniform(1.15, 1.45)
        f = round(f, 4)
        if stable:
            self.factors[key] = f
        return f

    # ---------- templates ----------
    @property
    def templates_dir(self) -> Path:
        return self.home / "templates"

    def list_templates(self) -> list[dict]:
        out = []
        if self.templates_dir.exists():
            for p in sorted(self.templates_dir.glob("*.json")):
                t = _read_json(p, None)
                if t:
                    t["_file"] = p.name
                    out.append(t)
        return out

    def save_template(self, template: dict) -> dict:
        with _LOCK:
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", template["name"].lower()).strip("-") or "template"
            path = self.templates_dir / f"{slug}.json"
            old = _read_json(path, None)
            template["version"] = (old or {}).get("version", 0) + 1
            template["created"] = (old or {}).get("created", _now())
            template["updated"] = _now()
            template.pop("_file", None)
            _write_json(path, template)
            template["_file"] = path.name
            return template

    def delete_template(self, file_name: str) -> None:
        p = self.templates_dir / Path(file_name).name
        if p.exists():
            p.unlink()

    # ---------- history ----------
    def log(self, entry: dict) -> None:
        with _LOCK:
            self.home.mkdir(parents=True, exist_ok=True)
            entry = {"time": _now(), **entry}
            if self.protected:
                self._history.append(entry)
                self.save()
                return
            with open(self.home / "history.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def history(self, limit: int = 200) -> list[dict]:
        rows = self._history if self.protected else self._plain_history()
        return rows[-limit:][::-1]


def _wipe(path: Path) -> None:
    """Overwrite then delete a plain file that held real values (best effort)."""
    try:
        if path.exists():
            size = path.stat().st_size
            with open(path, "r+b") as f:
                f.write(b"\0" * size)
                f.flush()
                os.fsync(f.fileno())
            path.unlink()
    except OSError:
        path.unlink(missing_ok=True)


def _letters(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
