"""Reading and writing spreadsheets.

Excel files are edited *in place* through openpyxl so layout, formatting,
column widths and merged cells survive. CSV files are read as text and
written back as text.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

SUPPORTED = {".xlsx", ".xlsm", ".csv", ".tsv"}


@dataclass
class Sheet:
    name: str
    values: dict[tuple[int, int], object] = field(default_factory=dict)  # (row, col) 1-based
    max_row: int = 0
    max_col: int = 0
    merged: list[tuple[int, int, int, int]] = field(default_factory=list)
    hidden: bool = False
    has_comments: bool = False

    def get(self, r: int, c: int):
        return self.values.get((r, c))


@dataclass
class Document:
    path: Path
    kind: str                      # "xlsx" | "csv"
    sheets: list[Sheet]
    display_name: str = ""         # name shown to the user (e.g. path inside a zip)
    hidden_parts: dict = field(default_factory=dict)   # what will be removed from the twin, with counts
    _wb: object = None
    _csv_dialect: str = ","

    @property
    def name(self) -> str:
        return self.display_name or self.path.name


def cell_ref(r: int, c: int) -> str:
    return f"{get_column_letter(c)}{r}"


def load(path: Path | str, display_name: str = "") -> Document:
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(path, data_only=False, keep_vba=False)
        sheets = []
        for ws in wb.worksheets:
            sh = Sheet(name=ws.title, hidden=ws.sheet_state != "visible")
            for row in ws.iter_rows():
                for cell in row:
                    v = cell.value
                    if v is None or (isinstance(v, str) and v == ""):
                        if cell.comment:
                            sh.has_comments = True
                        continue
                    sh.values[(cell.row, cell.column)] = v
                    if cell.comment:
                        sh.has_comments = True
            if sh.values:
                sh.max_row = max(r for r, _ in sh.values)
                sh.max_col = max(c for _, c in sh.values)
            sh.merged = [(m.min_row, m.min_col, m.max_row, m.max_col) for m in ws.merged_cells.ranges]
            sheets.append(sh)
        return Document(path=path, kind="xlsx", sheets=sheets, display_name=display_name, _wb=wb,
                        hidden_parts=_hidden_parts(wb, path))
    if ext in (".csv", ".tsv"):
        raw = path.read_bytes()
        text = None
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        delim = "\t" if ext == ".tsv" else ","
        if ext == ".csv":
            try:
                delim = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
            except csv.Error:
                delim = ","
        sh = Sheet(name=path.stem[:31] or "Sheet1")
        for r, row in enumerate(csv.reader(io.StringIO(text), delimiter=delim), start=1):
            for c, v in enumerate(row, start=1):
                if v != "":
                    sh.values[(r, c)] = v
        if sh.values:
            sh.max_row = max(r for r, _ in sh.values)
            sh.max_col = max(c for _, c in sh.values)
        return Document(path=path, kind="csv", sheets=[sh], display_name=display_name, _csv_dialect=delim)
    raise ValueError(f"Unsupported file type: {path.suffix}. Twinwise reads .xlsx, .xlsm, .csv and .tsv (and .zip of them).")


# ---------------------------------------------------------------------------------------------
# Hidden parts of an Excel file.
#
# Besides the cells you can see, a workbook can carry copies of the original data: pivot tables
# keep a cache of every source row, charts keep the plotted values and labels, images are often
# partner logos, hyperlinks hold addresses, drop-down lists and conditional formats can hold names.
# None of these are rewritten when cells are masked, so the twin is saved without them.
# ---------------------------------------------------------------------------------------------
HIDDEN_LABELS = {
    "pivot_tables": "pivot tables (they store a copy of the source data)",
    "charts": "charts (they store the plotted values and labels)",
    "images": "images (often logos)",
    "comments": "comments",
    "hyperlinks": "hyperlinks",
    "validations": "drop-down lists / validation rules",
    "tables": "Excel tables (converted to plain ranges)",
    "conditional_formats": "conditional formats with text",
    "external_links": "links to other workbooks",
    "defined_names": "named ranges",
    "macros": "macros",
    "headers_footers": "page headers / footers",
    "custom_properties": "custom document properties",
}


def _cf_rules(ws):
    try:
        return [(cf, rule) for cf in ws.conditional_formatting for rule in cf.rules]
    except Exception:
        return []


def _has_text_formula(rule) -> bool:
    return any('"' in str(f) for f in (getattr(rule, "formula", None) or []))


def _hf_used(ws) -> bool:
    for name in ("oddHeader", "oddFooter", "evenHeader", "evenFooter", "firstHeader", "firstFooter"):
        hf = getattr(ws, name, None)
        if hf is not None and any(getattr(getattr(hf, part), "text", None) for part in ("left", "center", "right")):
            return True
    return False


def _hidden_parts(wb, path: Path) -> dict:
    found: dict[str, int] = {}

    def add(k, n):
        if n:
            found[k] = found.get(k, 0) + int(n)

    for ws in wb.worksheets:
        add("pivot_tables", len(getattr(ws, "_pivots", []) or []))
        add("charts", len(getattr(ws, "_charts", []) or []))
        add("images", len(getattr(ws, "_images", []) or []))
        add("hyperlinks", max(len(getattr(ws, "_hyperlinks", []) or []),
                              sum(1 for row in ws.iter_rows() for cell in row if cell.hyperlink is not None)))
        add("tables", len(getattr(ws, "tables", {}) or {}))
        try:
            add("validations", len(ws.data_validations.dataValidation))
        except Exception:
            pass
        add("conditional_formats", sum(1 for _, rule in _cf_rules(ws) if _has_text_formula(rule)))
        add("comments", sum(1 for row in ws.iter_rows() for cell in row if cell.comment))
        add("headers_footers", 1 if _hf_used(ws) else 0)
    add("external_links", len(getattr(wb, "_external_links", []) or []))
    try:
        add("defined_names", len(wb.defined_names))
    except Exception:
        pass
    try:
        add("custom_properties", len(wb.custom_doc_props))
    except Exception:
        pass
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
        add("macros", 1 if any(n.lower().endswith("vbaproject.bin") for n in names) else 0)
        # anything the reader did not load as an object but that exists in the file
        if "charts" not in found:
            add("charts", sum(1 for n in names if re.match(r"xl/charts/chart\d+\.xml$", n)))
        if "pivot_tables" not in found:
            add("pivot_tables", sum(1 for n in names if re.match(r"xl/pivotTables/pivotTable\d+\.xml$", n)))
        if "images" not in found:
            add("images", sum(1 for n in names if n.startswith("xl/media/")))
    except (OSError, zipfile.BadZipFile):
        pass
    return found


def _strip_sheet(ws) -> None:
    from openpyxl.formatting.formatting import ConditionalFormattingList
    from openpyxl.worksheet.datavalidation import DataValidationList

    for row in ws.iter_rows():
        for cell in row:
            if getattr(cell, "comment", None):
                cell.comment = None
            if getattr(cell, "hyperlink", None) is not None:
                cell.hyperlink = None
    ws._hyperlinks = []
    ws._pivots = []
    ws._charts = []
    ws._images = []
    ws.legacy_drawing = None
    ws.data_validations = DataValidationList()
    keep = [(cf, rule) for cf, rule in _cf_rules(ws) if not _has_text_formula(rule)]
    if len(keep) != len(_cf_rules(ws)):
        fresh = ConditionalFormattingList()
        for cf, rule in keep:
            fresh.add(str(cf.sqref), rule)
        ws.conditional_formatting = fresh
    for name in list(ws.tables.keys()):
        del ws.tables[name]
    for name in ("oddHeader", "oddFooter", "evenHeader", "evenFooter", "firstHeader", "firstFooter"):
        hf = getattr(ws, name, None)
        if hf is not None:
            for part in ("left", "center", "right"):
                getattr(hf, part).text = None


def _strip_workbook(wb) -> None:
    wb._external_links = []
    wb._pivots = []
    # custom cell-style names can hold names ("Northwind header"); built-in ones are kept
    n = 0
    for style in getattr(wb, "_named_styles", []):
        if getattr(style, "builtinId", None) is None and style.name != "Normal":
            n += 1
            style.name = f"Style {n}"
    try:
        from openpyxl.packaging.custom import CustomPropertyList
        wb.custom_doc_props = CustomPropertyList()
    except Exception:
        pass


def expand_inputs(paths: list[Path], workdir: Path) -> list[tuple[Path, str]]:
    """Return (file path, display name) for every supported file, unpacking zips into ``workdir``."""
    out: list[tuple[Path, str]] = []
    for p in paths:
        p = Path(p)
        if p.suffix.lower() == ".zip":
            dest = workdir / (p.stem + "_unzipped")
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(p) as z:
                for info in z.infolist():
                    inner = Path(info.filename)
                    if info.is_dir() or inner.name.startswith(("~$", ".")) or "__MACOSX" in inner.parts:
                        continue
                    if inner.suffix.lower() not in SUPPORTED:
                        continue
                    # never trust paths inside archives
                    target = dest / inner.name
                    i = 1
                    while target.exists():
                        target = dest / f"{inner.stem}_{i}{inner.suffix}"
                        i += 1
                    with z.open(info) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    out.append((target, f"{p.name} › {inner.name}"))
        elif p.suffix.lower() in SUPPORTED:
            out.append((p, p.name))
        else:
            raise ValueError(f"Unsupported file type: {p.name}")
    return out


def save_twin(doc: Document, new_values: dict[str, dict[tuple[int, int], object]], sheet_names: dict[str, str],
              out_path: Path) -> Path:
    """Write the twin. ``new_values`` maps sheet name -> {(r,c): value}."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if doc.kind == "xlsx":
        wb = openpyxl.load_workbook(doc.path, data_only=False, keep_vba=False)
        for ws in wb.worksheets:
            vals = new_values.get(ws.title, {})
            for (r, c), v in vals.items():
                cell = ws.cell(row=r, column=c)
                if type(cell).__name__ == "MergedCell":
                    continue
                cell.value = v
            _strip_sheet(ws)
        for ws in wb.worksheets:
            new = sheet_names.get(ws.title)
            if new and new != ws.title:
                ws.title = new[:31]
        # wipe document properties (author, company, title...)
        props = wb.properties
        for attr in ("creator", "lastModifiedBy", "title", "subject", "description", "keywords", "category",
                     "identifier", "contentStatus", "version", "revision"):
            try:
                setattr(props, attr, None)
            except Exception:
                pass
        props.creator = "Twinwise"
        try:
            wb.defined_names.clear()
        except Exception:
            pass
        _strip_workbook(wb)
        wb.save(out_path)
    else:
        sh = doc.sheets[0]
        vals = new_values.get(sh.name, {})
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=doc._csv_dialect)
            for r in range(1, sh.max_row + 1):
                row = []
                for c in range(1, sh.max_col + 1):
                    v = vals.get((r, c), sh.get(r, c))
                    row.append("" if v is None else v)
                w.writerow(row)
    return out_path
