"""Reading and writing spreadsheets.

Excel files are edited *in place* through openpyxl so layout, formatting,
column widths and merged cells survive. CSV files are read as text and
written back as text.
"""
from __future__ import annotations

import csv
import io
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
        return Document(path=path, kind="xlsx", sheets=sheets, display_name=display_name, _wb=wb)
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
            # comments can hold names and notes - remove them
            for row in ws.iter_rows():
                for cell in row:
                    if getattr(cell, "comment", None):
                        cell.comment = None
            ws.oddHeader.center.text = ws.oddHeader.left.text = ws.oddHeader.right.text = None
            ws.oddFooter.center.text = ws.oddFooter.left.text = ws.oddFooter.right.text = None
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
