"""Understanding a sheet: cell kinds, header row, column roles, totals and formulas.

Nothing here changes data. The output (``SheetAnalysis``) tells the twin builder
what each cell is and how numbers relate to each other, so the twin can be
rebuilt to "add up" like the original.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .document import Document, Sheet
from .numbers import is_date_text, is_date_value, is_number, parse_number_text
from .vocab import (CATEGORY_KEYWORDS, COUNT_KEYWORDS, DATE_KEYWORDS, ID_KEYWORDS, PERCENT_KEYWORDS,
                    PRICE_KEYWORDS)

_TOTAL = re.compile(r"\b(grand\s+)?(sub\s*-?\s*)?totals?\b", re.I)

ROLE_LABELS = {
    "measure": "Number · scale",
    "count": "Count · scale",
    "price": "Price · scale",
    "percent": "Percent · scale",
    "id": "ID · replace",
    "date": "Date · keep",
    "entity": "Name · replace",
    "text": "Text · check",
    "empty": "Empty",
}


def cell_kind(v) -> str:
    if v is None or (isinstance(v, str) and not v.strip()):
        return "empty"
    if isinstance(v, bool):
        return "bool"
    if is_number(v):
        return "number"
    if is_date_value(v):
        return "date"
    if isinstance(v, str):
        if v.startswith("="):
            return "formula"
        if parse_number_text(v):
            return "numtext"
        if is_date_text(v):
            return "date"
        return "text"
    return "other"


def _has_kw(text: str, keywords) -> bool:
    t = " " + re.sub(r"[_\-]+", " ", text.lower()) + " "
    for k in keywords:
        if not k.isalnum() and len(k) <= 2:
            if k in t:
                return True
        elif re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", t):
            return True
    return False


def category_for(label: str) -> str | None:
    for cat, kws in CATEGORY_KEYWORDS:
        if _has_kw(label, kws):
            return cat
    return None


@dataclass
class Column:
    index: int
    header: str = ""
    role: str = "text"
    category: str | None = None

    @property
    def label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)


@dataclass
class SheetAnalysis:
    sheet: Sheet
    header_row: int = 0
    columns: dict[int, Column] = field(default_factory=dict)
    kinds: dict[tuple[int, int], str] = field(default_factory=dict)
    total_rows: set[int] = field(default_factory=set)
    data_rows: list[int] = field(default_factory=list)
    # value cells next to labels above the table: (r,c) -> ("id"|"entity"|"measure", category)
    labelled: dict[tuple[int, int], tuple[str, str | None]] = field(default_factory=dict)
    header_rows: list[int] = field(default_factory=list)
    label_rows: set[int] = field(default_factory=set)
    # derived[col] = (a, b, divisor, rows) meaning col = a*b/divisor on those rows
    derived: dict[int, tuple[int, int, float, set[int]]] = field(default_factory=dict)
    # totals[(r,c)] = list of rows summed
    totals: dict[tuple[int, int], list[int]] = field(default_factory=dict)

    def fingerprint(self) -> list[str]:
        return [_norm(c.header) for _, c in sorted(self.columns.items()) if c.header]


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def num_value(v):
    if is_number(v):
        return float(v)
    p = parse_number_text(v) if isinstance(v, str) else None
    return p[0] if p else None


def analyze_sheet(sheet: Sheet) -> SheetAnalysis:
    a = SheetAnalysis(sheet=sheet)
    for (r, c), v in sheet.values.items():
        a.kinds[(r, c)] = cell_kind(v)

    a.header_row = _find_header(a)
    header_rows = [a.header_row] if a.header_row else []
    # multi-row headers: a text-only row right below (or above) the header joins it
    if a.header_row:
        r = a.header_row + 1
        while r <= sheet.max_row and _is_text_row(a, r, min_texts=2) and r - a.header_row <= 2:
            header_rows.append(r)
            r += 1
        r = a.header_row - 1
        if r >= 1 and _is_text_row(a, r, min_texts=2):
            header_rows.insert(0, r)
    a.header_rows = header_rows
    if header_rows:
        a.header_row = max(header_rows)
    hr = a.header_row

    # data rows and total rows
    rows = sorted({r for (r, _), k in a.kinds.items() if r > hr and k != "empty"})
    for r in rows:
        texts = [sheet.get(r, c) for c in range(1, sheet.max_col + 1) if a.kinds.get((r, c)) == "text"]
        if any(_TOTAL.search(t) for t in texts):
            a.total_rows.add(r)
        else:
            a.data_rows.append(r)

    # small label rows inside the table ("Adjustments: | Month | Year | Amount")
    from .vocab import ACRONYMS, COMMON, MONTHS, STOP_WORDS
    known = COMMON | STOP_WORDS | ACRONYMS | MONTHS
    for r in rows:
        if _is_text_row(a, r, min_texts=2):
            words = [w.lower().strip(".:'") for c in range(1, sheet.max_col + 1) if a.kinds.get((r, c)) == "text"
                     for w in re.findall(r"[A-Za-z][A-Za-z'.]*", str(sheet.get(r, c)))]
            if words and all(w in known for w in words):
                a.label_rows.add(r)

    # columns
    for c in range(1, sheet.max_col + 1):
        parts = [re.sub(r"\s+", " ", str(sheet.get(r, c))).strip() for r in header_rows if a.kinds.get((r, c)) == "text"]
        header = " ".join(p for p in parts if p)
        col = Column(index=c, header=header)
        ks = [a.kinds.get((r, c), "empty") for r in a.data_rows]
        ks = [k for k in ks if k != "empty"]
        col.role = _role(header, ks, [sheet.get(r, c) for r in a.data_rows], a)
        if col.role == "entity":
            col.category = category_for(header)
        a.columns[c] = col

    _find_labels(a)
    _find_derived(a)
    _find_totals(a)
    return a


def _is_text_row(a: SheetAnalysis, r: int, min_texts: int = 2) -> bool:
    ks = [a.kinds.get((r, c), "empty") for c in range(1, a.sheet.max_col + 1)]
    filled = [k for k in ks if k != "empty"]
    return len(filled) >= min_texts and all(k == "text" for k in filled) and not any(
        _TOTAL.search(str(a.sheet.get(r, c))) for c in range(1, a.sheet.max_col + 1) if a.kinds.get((r, c)) == "text")


def _find_header(a: SheetAnalysis) -> int:
    sh = a.sheet
    best, best_score = 0, 0
    for r in range(1, min(sh.max_row, 40) + 1):
        cells = [(c, a.kinds.get((r, c), "empty")) for c in range(1, sh.max_col + 1)]
        filled = [(c, k) for c, k in cells if k != "empty"]
        texts = [c for c, k in filled if k == "text"]
        if len(texts) < 2 or len(texts) / max(len(filled), 1) < 0.75:
            continue
        below_rows = range(r + 1, min(r + 6, sh.max_row) + 1)
        numeric_cols = sum(
            1 for c in texts
            if any(a.kinds.get((rr, c)) in ("number", "numtext", "date", "formula") for rr in below_rows)
        )
        filled_cols_below = sum(1 for c in texts if any(a.kinds.get((rr, c), "empty") != "empty" for rr in below_rows))
        if filled_cols_below == 0:
            continue
        score = len(texts) + 2 * numeric_cols + filled_cols_below
        if score > best_score:
            best, best_score = r, score
    return best


def _role(header: str, kinds: list[str], values: list, a: SheetAnalysis) -> str:
    if not kinds:
        return "empty"
    n = len(kinds)
    num = sum(1 for k in kinds if k in ("number", "numtext"))
    dat = sum(1 for k in kinds if k == "date")
    txt = sum(1 for k in kinds if k == "text")
    if dat / n >= 0.6:
        return "date"
    if num / n >= 0.6:
        h = header
        if h and _has_kw(h, ("%", "percent", "pct", "percentage")):
            return "percent"
        nums = [num_value(v) for v in values if num_value(v) is not None]
        if h and _has_kw(h, COUNT_KEYWORDS) and nums and sum(float(x).is_integer() for x in nums) >= 0.9 * len(nums):
            return "count"
        if h and _has_kw(h, PRICE_KEYWORDS):
            return "price"
        if h and _has_kw(h, PERCENT_KEYWORDS):
            return "percent"
        if h and _has_kw(h, ID_KEYWORDS):
            ints = [v for v in values if isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit())]
            if len(ints) >= num * 0.9:
                return "id"
        if h and _has_kw(h, DATE_KEYWORDS):
            ints = [v for v in values if isinstance(v, int)]
            if ints and all(1 <= v <= 12 or 1900 <= v <= 2100 for v in ints):
                return "date"
        if any(isinstance(v, str) and parse_number_text(v) and parse_number_text(v)[1]["pct"] for v in values):
            return "percent"
        return "measure"
    if txt / n >= 0.5:
        codes = [v for v in values if isinstance(v, str) and re.search(r"\d", v) and len(v.split()) == 1]
        if header and _has_kw(header, ID_KEYWORDS) and (not category_for(header) or len(codes) >= 0.6 * txt):
            return "id"
        if header and category_for(header):
            return "entity"
        return "text"
    return "text"


def _find_labels(a: SheetAnalysis) -> None:
    """Key/value pairs above (or without) a table: 'Vendor Number | 228226'."""
    sh = a.sheet
    limit = a.header_row - 1 if a.header_row else sh.max_row
    for r in range(1, limit + 1):
        c = 1
        while c <= sh.max_col:
            if a.kinds.get((r, c)) == "text":
                label = str(sh.get(r, c))
                if len(label) <= 40:
                    nc = c + 1
                    while nc <= sh.max_col and a.kinds.get((r, nc), "empty") == "empty":
                        nc += 1
                    if nc <= sh.max_col and nc - c <= 6:
                        k = a.kinds.get((r, nc))
                        lbl = label.rstrip(": ")
                        if _has_kw(lbl, ID_KEYWORDS) and not _has_kw(lbl, COUNT_KEYWORDS):
                            a.labelled[(r, nc)] = ("id", "ID")
                        elif k == "text" and category_for(lbl):
                            a.labelled[(r, nc)] = ("entity", category_for(lbl))
                        elif k in ("number", "numtext"):
                            a.labelled[(r, nc)] = ("measure", None)
                        if (r, nc) in a.labelled:
                            c = nc + 1
                            continue
            c += 1


def _numeric_cols(a: SheetAnalysis) -> list[int]:
    return [c for c, col in a.columns.items() if col.role in ("measure", "count", "price", "percent")]


def _find_derived(a: SheetAnalysis) -> None:
    cols = _numeric_cols(a)
    sh = a.sheet
    vals = {c: {r: num_value(sh.get(r, c)) for r in a.data_rows} for c in cols}
    for t in cols:
        if a.columns[t].role == "count":
            continue
        best = None
        for i, x in enumerate(cols):
            for y in cols[i:]:
                if t in (x, y):
                    continue
                for div in (1.0, 100.0):
                    ok, tested = set(), 0
                    for r in a.data_rows:
                        vx, vy, vt = vals[x].get(r), vals[y].get(r), vals[t].get(r)
                        if vx is None or vy is None or vt is None:
                            continue
                        tested += 1
                        exp = vx * vy / div
                        if abs(exp - vt) <= max(0.011, abs(vt) * 0.002):
                            ok.add(r)
                    if tested >= 2 and len(ok) >= max(2, 0.9 * tested):
                        if not any(abs(vals[x].get(r) or 0) in (0.0, 1.0) and abs(vals[y].get(r) or 0) in (0.0, 1.0) for r in ok):
                            if best is None or len(ok) > len(best[3]):
                                best = (x, y, div, ok)
        if best is None:
            # t = x - y  or  t = x + y  (net = gross - deductions)
            for x in cols:
                for y in cols:
                    if len({t, x, y}) < 3:
                        continue
                    for code, fn in ((-1.0, lambda p, q: p - q), (-2.0, lambda p, q: p + q), (-3.0, lambda p, q: (p + q) / 2)):
                        if code in (-2.0, -3.0) and y < x:
                            continue
                        ok, tested = set(), 0
                        for r in a.data_rows:
                            vx, vy, vt = vals[x].get(r), vals[y].get(r), vals[t].get(r)
                            if vx is None or vy is None or vt is None:
                                continue
                            tested += 1
                            if abs(fn(vx, vy) - vt) <= max(0.011, abs(vt) * 0.002) and vy != 0:
                                ok.add(r)
                        if tested >= 2 and len(ok) >= max(2, 0.9 * tested) and (best is None or len(ok) > len(best[3])):
                            best = (x, y, code, ok)
        if best is None:
            # t = max(x, y) - e.g. "Greater Value" of a split rate and a minimum rate
            for i, x in enumerate(cols):
                for y in cols[i + 1:]:
                    if t in (x, y):
                        continue
                    ok, tested = set(), 0
                    for r in a.data_rows:
                        vx, vy, vt = vals[x].get(r), vals[y].get(r), vals[t].get(r)
                        if vx is None or vy is None or vt is None:
                            continue
                        tested += 1
                        if abs(max(vx, vy) - vt) <= max(0.011, abs(vt) * 0.002):
                            ok.add(r)
                    if tested >= 2 and len(ok) >= max(2, 0.9 * tested) and (best is None or len(ok) > len(best[3])):
                        best = (x, y, 0.0, ok)
        if best:
            a.derived[t] = best
    # avoid cycles: a derived column may not feed one of its own inputs
    for t, (x, y, _, _) in list(a.derived.items()):
        for src in (x, y):
            if src in a.derived and t in a.derived[src][:2]:
                a.derived.pop(t, None)


def _find_totals(a: SheetAnalysis) -> None:
    sh = a.sheet
    cols = _numeric_cols(a)
    data = a.data_rows
    tot_sorted = sorted(a.total_rows)
    for c in cols:
        prev_total = a.header_row
        earlier_totals: list[int] = []
        for tr in tot_sorted:
            tv = num_value(sh.get(tr, c))
            if tv is None:
                prev_total = tr
                earlier_totals.append(tr)
                continue
            block = [r for r in data if prev_total < r < tr and num_value(sh.get(r, c)) is not None]
            allrows = [r for r in data if r < tr and num_value(sh.get(r, c)) is not None]
            cands = [block, allrows, [r for r in earlier_totals if num_value(sh.get(r, c)) is not None]]
            for rows in cands:
                if rows and abs(sum(num_value(sh.get(r, c)) for r in rows) - tv) <= max(0.02, abs(tv) * 0.001):
                    a.totals[(tr, c)] = rows
                    break
            prev_total = tr
            earlier_totals.append(tr)


def analyze(doc: Document) -> list[SheetAnalysis]:
    return [analyze_sheet(s) for s in doc.sheets]
