"""AI-ready context for a twin: a data card plus retrieval chunks.

Two files are written next to every twin:

* ``<twin>_CONTEXT.md``   - a readable "data card": what the file is, what each
                            column means, how columns relate, and summary figures.
                            Paste it into a chat, or index it.
* ``<twin>_chunks.jsonl`` - one JSON line per chunk (overview, column dictionary,
                            totals, and one chunk per data row) with metadata,
                            ready for a RAG / vector-store pipeline.

Everything is built from the *twin* values only, and both files go through the
same leak test as the twin itself.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from openpyxl.utils import get_column_letter

from .analyze import ROLE_LABELS
from .numbers import is_number, parse_number_text
from .twin import FileTwin, SheetTwin

ROLE_PLAIN = {
    "measure": "amount",
    "count": "count (whole numbers)",
    "price": "price / rate per unit",
    "percent": "percentage",
    "id": "identifier / code (replaced)",
    "date": "date or period (kept)",
    "entity": "name (replaced with a label)",
    "text": "text",
}


def _val(st: SheetTwin, r: int, c: int):
    co = st.cells.get((r, c))
    v = co.twin if co else st.analysis.sheet.get(r, c)
    if isinstance(v, str):
        v = " ".join(v.split())
    return v


def _num(v):
    if is_number(v):
        return float(v)
    if isinstance(v, str):
        p = parse_number_text(v)
        return p[0] if p else None
    return None


def _fmt(x: float) -> str:
    if x is None:
        return ""
    if float(x).is_integer():
        return f"{int(x):,}"
    return f"{x:,.2f}"


def _headers(st: SheetTwin) -> dict[int, str]:
    a = st.analysis
    out = {}
    for c in range(1, a.sheet.max_col + 1):
        parts = [str(_val(st, r, c)) for r in a.header_rows if _val(st, r, c) not in (None, "")]
        out[c] = " ".join(parts).strip() or f"Column {get_column_letter(c)}"
    return out


def _formula_text(st: SheetTwin, heads: dict[int, str]) -> list[str]:
    out = []
    for t, (x, y, div, rows) in st.analysis.derived.items():
        X, Y, T = heads[x], heads[y], heads[t]
        expr = {0: f"the larger of {X} and {Y}", -1: f"{X} − {Y}", -2: f"{X} + {Y}",
                -3: f"the average of {X} and {Y}"}.get(div, f"{X} × {Y}" + (" ÷ 100" if div == 100 else ""))
        out.append(f"{T} = {expr}")
    return out


def build(ft: FileTwin) -> tuple[str, list[dict]]:
    """Return (markdown data card, list of chunks)."""
    md: list[str] = []
    chunks: list[dict] = []
    fname = ft.new_filename
    md.append(f"# Data card: {fname}\n")
    md.append("> This is a **synthetic twin** created by Twinwise. Names, IDs and codes are labels "
              "(e.g. *Region 1*, *VENDOR 1*); numbers are changed but keep the file's structure — "
<<<<<<< Updated upstream
              "totals and formulas still add up, and trends and broad comparisons inside a column stay meaningful. "
              "Rows may carry a small hidden variation, so two rows with nearly equal values can swap order. "
=======
              "totals and formulas still add up, and comparisons inside a column stay meaningful. "
>>>>>>> Stashed changes
              "Do not treat any figure as a real value.\n")

    for si, st in enumerate(ft.sheets):
        a = st.analysis
        sh = a.sheet
        heads = _headers(st)
        cols = [c for c in range(1, sh.max_col + 1) if st.roles.get(c, {}).get("role") not in (None, "empty")]
        data_rows = [r for r in a.data_rows if r not in a.label_rows]
        sheet_label = st.new_name
        md.append(f"## Sheet: {sheet_label}\n")

        # report details above the table
        details = []
        top = (a.header_rows[0] if a.header_rows else a.header_row + 1) - 1 if a.header_row else sh.max_row
        for r in range(1, top + 1):
            vals = [str(_val(st, r, c)) for c in range(1, sh.max_col + 1) if _val(st, r, c) not in (None, "")]
            if vals:
                details.append(" | ".join(vals))
        if details:
            md.append("**Report details**\n")
            md.extend(f"- {d}" for d in details[:15])
            md.append("")

        md.append(f"**Size:** {len(data_rows)} data rows, {len(a.total_rows)} total rows, {len(cols)} columns.\n")

        # column dictionary
        md.append("**Columns**\n")
        md.append("| Column | Name | Meaning | Summary (twin values) |")
        md.append("|---|---|---|---|")
        col_lines = []
        for c in cols:
            role = st.roles[c]["role"]
            meaning = ROLE_PLAIN.get(role, role)
            if role == "entity" and st.roles[c].get("category"):
                meaning = f"{st.roles[c]['category'].lower()} name (replaced with a label)"
            if c in a.derived:
                meaning += "; calculated"
            vals = [_val(st, r, c) for r in data_rows]
            vals = [v for v in vals if v not in (None, "")]
            summ = ""
            if role in ("measure", "count", "price", "percent"):
                nums = [n for n in (_num(v) for v in vals) if n is not None]
                if nums:
                    summ = (f"{len(nums)} values · min {_fmt(min(nums))} · max {_fmt(max(nums))} · "
                            f"avg {_fmt(sum(nums) / len(nums))}" + ("" if role in ("price", "percent") else f" · sum {_fmt(sum(nums))}"))
            elif vals:
                cnt = Counter(str(v) for v in vals)
                top3 = ", ".join(f"{k} ({n})" if n > 1 else k for k, n in cnt.most_common(4))
                summ = f"{len(cnt)} distinct · e.g. {top3}"
            md.append(f"| {get_column_letter(c)} | {heads[c]} | {meaning} | {summ} |")
            col_lines.append(f"{heads[c]} (column {get_column_letter(c)}): {meaning}. {summ}".strip())
        md.append("")

        formulas = _formula_text(st, heads)
        if formulas or a.totals:
            md.append("**How the numbers relate**\n")
            md.extend(f"- {f}" for f in formulas)
            if a.totals:
                md.append(f"- Rows labelled *Total* are sums of the rows above them ({len(a.total_rows)} total rows).")
            md.append("")

        # totals
        tot_lines = []
        for r in sorted(a.total_rows):
            label = next((str(_val(st, r, c)) for c in range(1, sh.max_col + 1)
                          if isinstance(_val(st, r, c), str) and _val(st, r, c)), f"Row {r}")
            parts = [f"{heads[c]}: {_fmt(_num(_val(st, r, c)))}" for c in cols if _num(_val(st, r, c)) is not None]
            if parts:
                tot_lines.append(f"{label} — " + "; ".join(parts))
        if tot_lines:
            md.append("**Totals**\n")
            md.extend(f"- {t}" for t in tot_lines[:40])
            if len(tot_lines) > 40:
                md.append(f"- … {len(tot_lines) - 40} more")
            md.append("")

        base_meta = {"file": fname, "sheet": sheet_label}
        chunks.append({"id": f"{fname}#s{si}-overview", "type": "overview",
                       "text": f"{fname}, sheet {sheet_label}: synthetic twin with {len(data_rows)} data rows and "
                               f"{len(cols)} columns. " + (" ".join(details[:6]) if details else ""),
                       "metadata": base_meta})
        chunks.append({"id": f"{fname}#s{si}-columns", "type": "columns",
                       "text": f"Columns of {sheet_label}: " + " | ".join(col_lines) +
                               (" Relationships: " + "; ".join(formulas) + "." if formulas else ""),
                       "metadata": base_meta})
        for i in range(0, len(tot_lines), 10):
            chunks.append({"id": f"{fname}#s{si}-totals-{i // 10}", "type": "totals",
                           "text": f"Totals in {sheet_label}: " + " || ".join(tot_lines[i:i + 10]),
                           "metadata": base_meta})
        for r in data_rows:
            fields = {heads[c]: _val(st, r, c) for c in cols if _val(st, r, c) not in (None, "")}
            if not fields:
                continue
            text = f"{sheet_label}, row {r}: " + "; ".join(
                f"{k}: {_fmt(v) if is_number(v) else v}" for k, v in fields.items()) + "."
            meta = {**base_meta, "row": r}
            for c in cols:
                if st.roles[c]["role"] == "entity" and _val(st, r, c):
                    meta[heads[c]] = _val(st, r, c)
            chunks.append({"id": f"{fname}#s{si}-r{r}", "type": "row", "text": text, "metadata": meta})

    md.append("---\n*Generated by Twinwise. Use the private key file with “Restore AI answer” to map labels back to real names.*")
    return "\n".join(md), chunks


def write(ft: FileTwin, twin_path: Path) -> list[Path]:
    md, chunks = build(ft)
    stem = twin_path.with_suffix("")
    p_md = Path(f"{stem}_CONTEXT.md")
    p_js = Path(f"{stem}_chunks.jsonl")
    p_md.write_text(md, encoding="utf-8")
    with open(p_js, "w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False, default=str) + "\n")
    return [p_md, p_js]
