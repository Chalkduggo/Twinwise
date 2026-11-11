"""Safety checks run on the saved twin file itself.

* Leak test   - every value Twinwise replaced must be absent from the saved twin
                (cells, formulas, sheet names, file name, document properties).
* Risk check  - basic warnings about things that can still identify a partner or
                person even after masking (small counts, kept percentages, kept text
                that looks like a name).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from .numbers import is_number, parse_number_text
from .twin import FileTwin
from .vocab import ACRONYMS, COMMON, MONTHS, STOP_WORDS


@dataclass
class LeakReport:
    checked_values: int = 0
    leaks: list[dict] = field(default_factory=list)          # real problems
    coincidences: list[dict] = field(default_factory=list)   # a fake number happens to equal a real one elsewhere

    @property
    def ok(self) -> bool:
        return not self.leaks

    def to_dict(self):
        return {"checked_values": self.checked_values, "leaks": self.leaks[:200], "leak_count": len(self.leaks),
                "coincidences": len(self.coincidences), "ok": self.ok}


def _strings_in_twin(path: Path) -> list[tuple[str, str]]:
    """(where, text) for everything readable in the saved twin."""
    out = [("file name", path.name)]
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(path, data_only=False)
        p = wb.properties
        for attr in ("creator", "lastModifiedBy", "title", "subject", "description", "keywords", "category"):
            v = getattr(p, attr, None)
            if v:
                out.append((f"document {attr}", str(v)))
        for ws in wb.worksheets:
            out.append(("sheet name", ws.title))
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is not None:
                        out.append((f"{ws.title}!{cell.coordinate}", str(cell.value)))
                    if cell.comment:
                        out.append((f"{ws.title}!{cell.coordinate} comment", cell.comment.text))
    else:
        import csv
        with open(path, encoding="utf-8") as f:
            for r, row in enumerate(csv.reader(f), start=1):
                for c, v in enumerate(row, start=1):
                    if v:
                        out.append((f"R{r}C{c}", v))
    return out


def leak_test(ft: FileTwin, twin_path: Path) -> LeakReport:
    rep = LeakReport()
    strings = _strings_in_twin(twin_path)
    blob = [(w, s.lower()) for w, s in strings]

    secrets: set[str] = set()
    for fake, info in ft.names.items():
        real = str(info["real"]).strip()
        if len(re.sub(r"\W", "", real)) >= 3:
            secrets.add(real)
    for fake, real in ft.ids.items():
        if len(re.sub(r"\W", "", real)) >= 3:
            secrets.add(real)
    fakes_lower = {f.lower() for f in ft.names} | {f.lower() for f in ft.ids}

    for s in secrets:
        sl = s.lower()
        pat = re.compile(r"(?<![a-z0-9])" + re.escape(sl) + r"(?![a-z0-9])")
        for where, text in blob:
            if pat.search(text):
                # ignore hits that are fully inside a fake label (e.g. a fake that contains the word)
                if any(sl in f and pat.search(f) for f in fakes_lower if f in text):
                    continue
                rep.leaks.append({"where": where, "value": s, "type": "text"})
                break
    rep.checked_values += len(secrets)

    # numbers: the masked cells must not still hold their real value
    twin_vals = {}
    if twin_path.suffix.lower() in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(twin_path, data_only=False)
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    twin_vals[(ws.title, cell.coordinate)] = cell.value
    sheet_map = {s.analysis.sheet.name: s.new_name for s in ft.sheets}
    real_set = {}
    for n in ft.numbers:
        real_set.setdefault(round(n["real"], 6), []).append(n)
    for n in ft.numbers:
        rep.checked_values += 1
        if n["real"] == 0:
            continue
        tv = twin_vals.get((sheet_map.get(n["sheet"], n["sheet"]), n["cell"]))
        if tv is None and twin_path.suffix.lower() not in (".xlsx", ".xlsm"):
            continue
        tnum = float(tv) if is_number(tv) else (parse_number_text(tv)[0] if isinstance(tv, str) and parse_number_text(tv) else None)
        if tnum is not None and abs(tnum - n["real"]) < 1e-9 and n.get("computed"):
            rep.coincidences.append({"where": f"{n['sheet']}!{n['cell']}", "value": tnum})
        elif tnum is not None and abs(tnum - n["real"]) < 1e-9:
            rep.leaks.append({"where": f"{n['sheet']}!{n['cell']}", "value": n["real"], "type": "number unchanged"})
        elif tnum is not None and round(tnum, 6) in real_set and abs(tnum) >= 10:
            rep.coincidences.append({"where": f"{n['sheet']}!{n['cell']}", "value": tnum})
    return rep


_WORD = re.compile(r"[A-Za-z][A-Za-z'.&]+")


def risk_check(ft: FileTwin) -> dict:
    warnings = []
    small = 0
    for st in ft.sheets:
        for (r, c), co in st.cells.items():
            role = st.roles.get(c, {}).get("role")
            if co.status == "number" and role == "count" and isinstance(co.original, (int, float)) and 0 < co.original < 5:
                small += 1
    if small:
        warnings.append({"level": "medium", "title": f"{small} small counts (1–4)",
                         "detail": "Very small numbers can point to a specific customer or location even after masking. "
                                   "Consider removing those rows or grouping them before sharing."})
    kept_pct = [st.roles[c]["header"] for st in ft.sheets for c in st.roles
                if st.roles[c]["role"] == "percent" and st.roles[c]["action"] == "keep"]
    if kept_pct:
        warnings.append({"level": "medium", "title": "Percentages kept as-is",
                         "detail": f"Columns {', '.join(kept_pct)} keep their real values. Contract terms like split % can identify a deal."})
    suspicious = set()
    for st in ft.sheets:
        for co in st.cells.values():
            if co.status == "keep" and isinstance(co.original, str):
                for w in _WORD.findall(co.original):
                    k = w.lower().strip(".")
                    if w[0].isupper() and k not in COMMON and k not in ACRONYMS and k not in MONTHS and k not in STOP_WORDS:
                        suspicious.add(w)
    if suspicious:
        warnings.append({"level": "low", "title": "Kept text you may want to glance at",
                         "detail": ", ".join(sorted(suspicious)[:25]) + (" …" if len(suspicious) > 25 else "")})
    review = sum(s.counts().get("review", 0) for s in ft.sheets)
    if review:
        warnings.append({"level": "medium", "title": f"{review} cells were masked automatically without your review",
                         "detail": "They are masked (safe), but reviewing them teaches Twinwise for next time."})
    level = "high" if any(w["level"] == "high" for w in warnings) else (
        "medium" if sum(w["level"] == "medium" for w in warnings) >= 2 else "low")
    return {"level": level, "warnings": warnings}
