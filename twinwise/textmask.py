"""Masking names, places, codes and IDs inside text.

Two modes:

* strict - the text sits in a column known to hold names (Title, Partner, City...).
  Every word that is not structural (``for``, ``-``, ``PPV``...) is treated as part
  of a name and replaced. ``Lantern Channel`` -> ``Channel A``.
* loose  - headings, labels, notes. Ordinary business words are kept; capitalised
  words that are not known are treated as names, and company suffixes join them
  (``Northwind Communications`` is one name). Anything new found this way is flagged for
  review.

Digit runs of 3 or more (except years) are always replaced with a stable fake of
the same shape, so ``51001 - PPV for Aldermoor`` -> ``10001 - PPV for Region 1``.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from .library import Library
from .vocab import ACRONYMS, COMMON, MONTHS, ORG_SUFFIXES, STOP_WORDS

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_TOKEN = re.compile(r"[A-Za-z][A-Za-z'’&.]*[A-Za-z]|[A-Za-z]|\d[\d,]*(?:\.\d+)?|\s+|.", re.S)
_YEAR = re.compile(r"^(19|20)\d{2}$")


@dataclass
class Replacement:
    original: str
    fake: str
    kind: str          # "name" | "id" | "email" | "url"
    category: str
    new: bool          # True if this name was not in the library before


@dataclass
class TextResult:
    text: str
    replacements: list[Replacement] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.replacements)

    @property
    def has_new_names(self) -> bool:
        return any(r.new and r.kind == "name" for r in self.replacements)


def _word_key(w: str) -> str:
    return w.lower().strip(".'’")


def _is_structural(w: str, lib: Library) -> bool:
    k = _word_key(w)
    return k in STOP_WORDS or k in ACRONYMS or k in MONTHS or lib.is_safe(w)


def _is_common(w: str, lib: Library) -> bool:
    k = _word_key(w)
    if _is_structural(w, lib) or k in COMMON:
        return True
    # plain lower-case words in sentences are ordinary words, not names
    return w.islower() and lib.lookup_name(w) is None


def _case_like(fake: str, original: str) -> str:
    letters = [c for c in original if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 1:
        return fake.upper()
    return fake


def mask_text(text: str, lib: Library, rng: random.Random, *, category: str | None = None,
              strict: bool = False, mask_all: bool = False) -> TextResult:
    """Return the masked version of ``text`` and what was replaced."""
    res = TextResult(text=text)
    if not isinstance(text, str) or not text.strip():
        return res
    if lib.is_safe(text):
        return res

    # whole cell explicitly to be masked, or whole cell is a known name
    known = lib.lookup_name(text)
    # a short code alone in a name column (state "OR", "IN", "CO") is data, not the word "or"
    if strict and category and re.fullmatch(r"[A-Z]{2,3}", text.strip()) and not lib.is_safe(text):
        mask_all = True
    # inside a name column, a cell without codes or numbers is one name ("The Quiet Orchard")
    if strict and category not in (None, "Region", "Email", "Address") and not re.search(r"\d", text) and not _EMAIL.search(text) \
            and not all(_is_structural(w, lib) for w in re.findall(r"[A-Za-z]+", text)):
        mask_all = True
    if mask_all or known:
        cat = (known or {}).get("category") or category or "Name"
        new = known is None
        fake = _case_like(lib.fake_name(text, cat), text)
        res.text = fake
        res.replacements.append(Replacement(text.strip(), fake, "name", cat, new))
        return res

    # 1) emails and urls
    def _sub_email(m):
        k = lib.lookup_name(m.group(0))
        fake = lib.fake_name(m.group(0), "Email")
        res.replacements.append(Replacement(m.group(0), fake, "email", "Email", k is None))
        return "\x00" + fake + "\x01"

    t = _EMAIL.sub(_sub_email, text)
    t = _URL.sub(lambda m: (res.replacements.append(Replacement(m.group(0), "https://example.com", "url", "URL", False)) or "\x00https://example.com\x01"), t)

    # 2) known multi-word names from the library (longest first)
    names = sorted((e for e in lib.names.values() if " " in e["real"] and len(e["real"]) > 3),
                   key=lambda e: -len(e["real"]))
    for e in names:
        pat = re.compile(r"(?<![\w\x00])" + re.escape(e["real"]) + r"(?![\w\x01])", re.I)
        if pat.search(t):
            def _rep(m, e=e):
                fake = _case_like(e["fake"], m.group(0))
                res.replacements.append(Replacement(m.group(0), fake, "name", e["category"], False))
                return "\x00" + fake + "\x01"
            t = pat.sub(_rep, t)

    # 3) token pass over the unprotected parts
    out = []
    for part in re.split(r"(\x00[^\x01]*\x01)", t):
        if part.startswith("\x00"):
            out.append(part[1:-1])
            continue
        out.append(_mask_tokens(part, lib, rng, category, strict, res))
    res.text = "".join(out)
    return res


def _mask_tokens(part: str, lib: Library, rng: random.Random, category: str | None, strict: bool,
                 res: TextResult) -> str:
    toks = _TOKEN.findall(part)
    # classify tokens
    kinds = []
    for tk in toks:
        if tk.isspace():
            kinds.append("space")
        elif tk[0].isdigit():
            digits = re.sub(r"\D", "", tk)
            if _YEAR.match(tk) or len(digits) < 3:
                kinds.append("keep")
            else:
                kinds.append("digits")
        elif tk[0].isalpha():
            if lib.lookup_name(tk):
                kinds.append("name")
            elif strict:
                kinds.append("keep" if _is_structural(tk, lib) else "name")
            else:
                if _is_common(tk, lib):
                    kinds.append("keep")
                elif tk[0].isupper() or tk.isupper():
                    kinds.append("name")
                else:
                    kinds.append("keep")
        else:
            kinds.append("joiner" if tk in "&'’." else "keep")

    # loose mode: company suffixes and '&' extend an adjacent name
    if not strict:
        for i, tk in enumerate(toks):
            if kinds[i] == "keep" and tk[:1].isalpha() and _word_key(tk) in ORG_SUFFIXES:
                j = i - 1
                while j >= 0 and kinds[j] == "space":
                    j -= 1
                if j >= 0 and kinds[j] == "name":
                    kinds[i] = "name"

    # group consecutive name tokens (spaces / joiners between them belong to the name)
    out = []
    i = 0
    n = len(toks)
    while i < n:
        k = kinds[i]
        if k == "digits":
            existed = toks[i] in lib.ids
            fake = lib.fake_id(toks[i], rng)
            res.replacements.append(Replacement(toks[i], fake, "id", "ID", not existed))
            out.append(fake)
            i += 1
            continue
        if k != "name":
            out.append(toks[i])
            i += 1
            continue
        j = i
        last = i
        while j + 1 < n and kinds[j + 1] in ("space", "joiner", "name"):
            j += 1
            if kinds[j] == "name":
                last = j
        span = "".join(toks[i:last + 1])
        cat = category if strict and category else _guess_category(span, toks[i:last + 1])
        letters_only = re.sub(r"[^A-Za-z]", "", span)
        whole_cell = span.strip() == part.strip()
        if strict and not whole_cell and len(letters_only) <= 4 and span.isupper() and " " not in span and category not in ("Title",):
            # short unknown code inside a name column (e.g. "CLU")
            cat = "Code" if lib.lookup_name(span) is None else lib.lookup_name(span)["category"]
        existed = lib.lookup_name(span) is not None
        fake = _case_like(lib.fake_name(span, cat), span)
        res.replacements.append(Replacement(span, fake, "name", cat, not existed))
        out.append(fake)
        i = last + 1
    return "".join(out)


def _guess_category(span: str, toks: list[str]) -> str:
    if any(_word_key(t) in ORG_SUFFIXES for t in toks if t[:1].isalpha()):
        return "Company"
    return "Name"
