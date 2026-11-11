"""The key file: the private link between the twin and the real data.

The key never leaves your computer. Use it to turn an AI answer written about
the twin ("Channel A grew 12%") back into real names and numbers.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import crypto
from .crypto import WrongPassword  # noqa: F401  (re-exported)
from .twin import FileTwin

FORMAT = "twinwise-key/1"


def build_key(twins: list[FileTwin], settings: dict) -> dict:
    names, ids, numbers, files = {}, {}, [], []
    factors = {}
    for ft in twins:
        names.update(ft.names)
        ids.update(ft.ids)
        numbers.extend({**n, "file": ft.new_filename} for n in ft.numbers)
        factors.update(ft.factors)
        files.append({"original": ft.doc.name, "twin": ft.new_filename})
    return {
        "format": FORMAT,
        "created": datetime.now().isoformat(timespec="seconds"),
        "warning": "PRIVATE - this file contains the real values. Never upload it to an AI tool or share it.",
        "settings": settings,
        "files": files,
        "names": [{"fake": f, "real": v["real"], "category": v["category"]} for f, v in sorted(names.items())],
        "ids": [{"fake": f, "real": r} for f, r in sorted(ids.items())],
        "numbers": numbers,
        "factors": factors,
    }


def save_key(key: dict, path: Path, password: str | None = None) -> Path:
    """Write the key file. With a password it is encrypted (AES-256-GCM); without, it is plain JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(key, indent=2, ensure_ascii=False, default=str)
    if password:
        crypto.check_password(password)
        text = crypto.dumps(crypto.encrypt(text.encode("utf-8"), password, "key"))
    path.write_text(text, encoding="utf-8")
    return path


def open_key(obj: dict, password: str | None = None) -> dict:
    """Return the usable key from a loaded key file, decrypting it if needed."""
    if crypto.is_envelope(obj):
        obj = json.loads(crypto.decrypt(obj, password).decode("utf-8"))
    if not isinstance(obj, dict) or obj.get("format") != FORMAT:
        raise ValueError("This is not a Twinwise key file.")
    return obj


def is_encrypted_key(path: Path | str) -> bool:
    try:
        return crypto.is_envelope(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def load_key(path: Path | str, password: str | None = None) -> dict:
    return open_key(json.loads(Path(path).read_text(encoding="utf-8")), password)


_NUM = re.compile(r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w])")


def restore(text: str, key: dict) -> dict:
    """Replace fake names, IDs and exact fake numbers in ``text`` with the real ones."""
    out = text
    replaced = []
    pairs = [(n["fake"], n["real"]) for n in key.get("names", [])] + [(i["fake"], i["real"]) for i in key.get("ids", [])]
    pairs.sort(key=lambda p: -len(p[0]))
    tokens = {}
    for i, (fake, real) in enumerate(pairs):
        pat = re.compile(r"(?<![\w])" + re.escape(fake) + r"(?![\w])", re.I)
        if pat.search(out):
            tok = f"\x00{i}\x01"
            tokens[tok] = real
            out = pat.sub(tok, out)
            replaced.append({"fake": fake, "real": real, "type": "name/id"})

    # exact numbers that appear in the twin map back to one real value
    by_fake: dict[float, set] = {}
    for n in key.get("numbers", []):
        by_fake.setdefault(round(float(n["fake"]), 6), set()).add(n["real"])
    unresolved = []

    def _num(m):
        s = m.group(0)
        try:
            v = round(float(s.replace(",", "")), 6)
        except ValueError:
            return s
        reals = by_fake.get(v)
        if reals and len(reals) == 1:
            real = next(iter(reals))
            dec = len(s.split(".")[1]) if "." in s else 0
            rs = f"{real:,.{dec}f}" if "," in s else f"{real:.{dec}f}"
            replaced.append({"fake": s, "real": rs, "type": "number"})
            return rs
        if abs(v) >= 10:
            unresolved.append(s)
        return s

    parts = re.split(r"(\x00\d+\x01)", out)
    out = "".join(p if p in tokens else _NUM.sub(_num, p) for p in parts)
    for tok, real in tokens.items():
        out = out.replace(tok, real)
    note = ""
    if unresolved:
        mode = key.get("settings", {}).get("mode")
        if mode == "scale" and "__whole file__" in key.get("factors", {}):
            f = key["factors"]["__whole file__"]
            note = (f"{len(unresolved)} numbers were calculated by the AI and are not in the twin. "
                    f"In 'scale' mode, divide amounts by {f} to estimate the real figure.")
        else:
            note = (f"{len(unresolved)} numbers were calculated by the AI (totals, averages, growth) and are not in the twin, "
                    "so they cannot be mapped back exactly. Percent changes and rankings stay valid in 'consistent' mode.")
    return {"text": out, "replaced": replaced, "unresolved": unresolved, "note": note}
