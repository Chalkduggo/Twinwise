"""Safety checks run on the saved twin file itself.

* Leak test   - every value Twinwise replaced must be absent from the saved twin
                (cells, formulas, sheet names, file name, document properties).
* Package scan - for Excel files, every part inside the saved .xlsx package is
                searched too (not only the cells), and parts that can hold copies
                of the original data (pivot caches, charts, images, external links,
                macros) must not be present at all.
* Risk check  - basic warnings about things that can still identify a partner or
                person even after masking (small counts, kept percentages, kept text
                that looks like a name).
"""
from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

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

    # file and sheet names must not keep any word of a replaced name ("harbor_media_statement.csv")
    from .twin import name_words
    words = name_words(ft)
    for where, text in strings:
        if where in ("file name", "sheet name"):
            for w in re.findall(r"[A-Za-z]{3,}", text):
                if w.lower() in words and not any(w.lower() in f for f in fakes_lower):
                    rep.leaks.append({"where": where, "value": w, "type": "name word"})

<<<<<<< Updated upstream
    if twin_path.suffix.lower() in (".xlsx", ".xlsm"):
        _scan_package(twin_path, secrets, fakes_lower, rep)

=======
>>>>>>> Stashed changes
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


FORBIDDEN_PARTS = (
    ("pivot", "pivot table data"), ("/charts/", "chart"), ("/chartsheets/", "chart sheet"), ("/media/", "image"),
    ("/drawings/", "drawing"), ("externallink", "link to another workbook"), ("vbaproject", "macro"),
    ("/embeddings/", "embedded file"), ("customxml", "custom XML"), ("/comments", "comment"),
    ("/activex/", "ActiveX control"), ("/ctrlprops/", "form control"), ("/slicer", "slicer"), ("/querytables/", "query"),
    ("/connections", "data connection"), ("docprops/custom", "custom property"),
)
_SKIP_PARTS = ("xl/theme/",)            # theme files hold only colour and font names
_SKIP_TAGS = {"Application", "AppVersion", "DocSecurity"}
_APP_CONSTANTS = {"Worksheets", "Named Ranges", "Charts", "Microsoft Excel"}


def _part_strings(name: str, data: bytes) -> list[str]:
    """Every piece of text in one package part that could hold workbook content.

    Purely structural values are left out so ordinary words do not cause false alarms: internal part
    links, font names, built-in cell-style names and the fixed labels Excel writes in app.xml.
    """
    low = name.lower()
    if low == "[content_types].xml":
        return []
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return [html.unescape(data.decode("utf-8", "ignore"))]
    out = []
    is_rels, is_styles, is_app = low.endswith(".rels"), low.endswith("styles.xml"), low.endswith("docprops/app.xml")
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in _SKIP_TAGS:
            continue
        if is_rels:
            if el.attrib.get("TargetMode") == "External" and el.attrib.get("Target"):
                out.append(el.attrib["Target"])
            continue
        if is_styles and (tag in ("name", "family", "scheme", "charset") or (tag == "cellStyle" and "builtinId" in el.attrib)):
            continue
        if el.text and el.text.strip() and not (is_app and el.text.strip() in _APP_CONSTANTS):
            out.append(el.text)
        if el.tail and el.tail.strip():
            out.append(el.tail)
        out.extend(v for v in el.attrib.values() if v)
    return out


def _scan_package(path: Path, secrets: set[str], fakes_lower: set[str], rep: LeakReport) -> None:
    """Search the raw .xlsx package: forbidden parts, then every string in every part."""
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        rep.leaks.append({"where": path.name, "value": "file could not be opened for checking", "type": "unreadable"})
        return
    pats = [(s, s.lower(), re.compile(r"(?<![a-z0-9])" + re.escape(s.lower()) + r"(?![a-z0-9])")) for s in secrets]
    with z:
        for info in z.infolist():
            low = "/" + info.filename.lower()
            hit = next((label for frag, label in FORBIDDEN_PARTS if frag in low), None)
            if hit:
                rep.leaks.append({"where": info.filename, "value": hit, "type": "hidden part not removed"})
                continue
            if any(info.filename.startswith(p) for p in _SKIP_PARTS):
                continue
            if not info.filename.lower().endswith((".xml", ".rels", ".vml", ".txt")):
                rep.leaks.append({"where": info.filename, "value": "unexpected file in the package", "type": "hidden part not removed"})
                continue
            texts = [t.lower() for t in _part_strings(info.filename, z.read(info))]
            rep.checked_values += 1
            for s, sl, pat in pats:
                for t in texts:
                    m = pat.search(t)
                    if not m:
                        continue
                    window = t[max(0, m.start() - 40): m.end() + 40]
                    if any(sl in f and f in window for f in fakes_lower):
                        continue
                    if not any(l["value"] == s for l in rep.leaks):
                        rep.leaks.append({"where": f"inside the file: {info.filename}", "value": s, "type": "text"})
                    break


_WORD = re.compile(r"[A-Za-z][A-Za-z'.&]+")


def risk_check(ft: FileTwin, settings=None) -> dict:
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
    if settings is not None:
        if settings.mode == "scale":
            warnings.append({"level": "medium", "title": "One hidden factor for every number",
                             "detail": "In this mode, anyone who knows one real figure can work out all the others. "
                                       "Use Consistent mode with row variation unless exact ratios are essential."})
        elif settings.mode == "consistent" and settings.variation <= 0:
            warnings.append({"level": "medium", "title": "Row variation is off",
                             "detail": "Each column uses a single hidden factor, so anyone who knows one real figure in "
                                       "a column can work out the rest of that column."})
        if settings.mode != "random" and settings.stable_factors:
            warnings.append({"level": "low", "title": "Same hidden factors every month",
                             "detail": "This keeps month-to-month trends true, but a figure learned from one month's twin "
                                       "helps estimate other months. Turn it off for one-off sharing."})
    review = sum(s.counts().get("review", 0) for s in ft.sheets)
    if review:
        warnings.append({"level": "medium", "title": f"{review} cell{'' if review == 1 else 's'} masked automatically without your review",
                         "detail": "They are masked (safe), but reviewing them teaches Twinwise for next time."})
    level = "high" if any(w["level"] == "high" for w in warnings) else (
        "medium" if sum(w["level"] == "medium" for w in warnings) >= 2 else "low")
    return {"level": level, "warnings": warnings}


def leak_test_files(ft: FileTwin, paths: list[Path]) -> LeakReport:
    """Search extra outputs (context doc, chunks) for every value that was replaced."""
    rep = LeakReport()
    secrets = {str(i["real"]).strip() for i in ft.names.values()} | set(ft.ids.values())
    secrets = {s for s in secrets if len(re.sub(r"\W", "", s)) >= 3}
    fakes_lower = {f.lower() for f in ft.names} | {f.lower() for f in ft.ids}
    for p in paths:
        text = p.read_text(encoding="utf-8").lower()
        for s in secrets:
            sl = s.lower()
            pat = re.compile(r"(?<![a-z0-9])" + re.escape(sl) + r"(?![a-z0-9])")
            for m in pat.finditer(text):
                # a hit inside a fake label is fine
                window = text[max(0, m.start() - 30): m.end() + 30]
                if any(sl in f and f in window for f in fakes_lower):
                    continue
                rep.leaks.append({"where": p.name, "value": s, "type": "text"})
                break
        rep.checked_values += len(secrets)
    # real numbers must not appear: check every distinctive real value that was changed
    reals = {round(n["real"], 2) for n in ft.numbers if abs(n["real"]) >= 100 and not n.get("computed")}
    fakes = {round(float(n["fake"]), 2) for n in ft.numbers}
    for p in paths:
        text = p.read_text(encoding="utf-8")
        for tok in re.findall(r"-?\d[\d,]*\.?\d*", text):
            try:
                v = round(float(tok.replace(",", "")), 2)
            except ValueError:
                continue
            if v in reals and v not in fakes:
                rep.coincidences.append({"where": p.name, "value": v})
    return rep
