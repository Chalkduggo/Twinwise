"""Building the twin of one file."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from .analyze import SheetAnalysis, num_value
from .document import Document, cell_ref
from .library import Library
from .numbers import (decimals_of, format_number_text, is_number, noisy, parse_number_text, price_point,
                      round_like)
from .textmask import mask_text

MODES = ("consistent", "scale", "random")


@dataclass
class Settings:
    mode: str = "consistent"       # consistent | scale | random
    price_points: bool = True      # 3.64 -> 3.99 for price columns
    stable_factors: bool = True    # same hidden factor per column name across files and months

    def to_dict(self):
        return {"mode": self.mode, "price_points": self.price_points, "stable_factors": self.stable_factors}

    @classmethod
    def from_dict(cls, d: dict | None):
        d = d or {}
        s = cls()
        if d.get("mode") in MODES:
            s.mode = d["mode"]
        for k in ("price_points", "stable_factors"):
            if k in d:
                setattr(s, k, bool(d[k]))
        return s


@dataclass
class CellOut:
    status: str          # keep | number | id | name | date | review | formula
    original: object
    twin: object
    note: str = ""


@dataclass
class SheetTwin:
    analysis: SheetAnalysis
    cells: dict[tuple[int, int], CellOut] = field(default_factory=dict)
    new_name: str = ""
    roles: dict[int, dict] = field(default_factory=dict)   # effective column role/category/action

    def counts(self) -> dict:
        out = {"number": 0, "name": 0, "id": 0, "date": 0, "keep": 0, "review": 0, "formula": 0}
        for co in self.cells.values():
            out[co.status] = out.get(co.status, 0) + 1
        return out


@dataclass
class FileTwin:
    doc: Document
    sheets: list[SheetTwin]
    new_filename: str
    names: dict[str, dict] = field(default_factory=dict)   # fake -> {real, category}
    ids: dict[str, str] = field(default_factory=dict)       # fake -> real
    numbers: list[dict] = field(default_factory=list)
    factors: dict[str, float] = field(default_factory=dict)

    def counts(self) -> dict:
        tot: dict[str, int] = {}
        for s in self.sheets:
            for k, v in s.counts().items():
                tot[k] = tot.get(k, 0) + v
        return tot

    def values_for_save(self) -> tuple[dict, dict]:
        values, names = {}, {}
        renames = {s.analysis.sheet.name: s.new_name for s in self.sheets if s.new_name != s.analysis.sheet.name}
        for s in self.sheets:
            d = {}
            for rc, co in s.cells.items():
                tw = co.twin
                if co.status == "formula" and renames and isinstance(tw, str):
                    for old, new in renames.items():
                        tw = tw.replace(f"'{old}'!", f"'{new}'!")
                        if re.fullmatch(r"\w+", old):
                            tw = re.sub(rf"(?<![\w']){re.escape(old)}!", f"'{new}'!", tw)
                if tw != co.original:
                    d[rc] = tw
            values[s.analysis.sheet.name] = d
            names[s.analysis.sheet.name] = s.new_name
        return values, names


def _key(sheet: str, c: int | str) -> str:
    return f"{sheet}!{c}"


def build_file_twin(doc: Document, analyses: list[SheetAnalysis], lib: Library, settings: Settings,
                    overrides: dict | None = None, seed: int = 7) -> FileTwin:
    overrides = overrides or {}
    col_over = overrides.get("columns", {})
    cell_over = overrides.get("cells", {})
    ft = FileTwin(doc=doc, sheets=[], new_filename="")

    def record(res):
        for rp in res.replacements:
            if rp.kind in ("name", "email"):
                ft.names[rp.fake] = {"real": rp.original, "category": rp.category}
            elif rp.kind == "id":
                ft.ids[rp.fake] = rp.original

    for si, a in enumerate(analyses):
        rng = random.Random(f"{seed}-{si}-{a.sheet.name}")
        st = SheetTwin(analysis=a)
        sh = a.sheet
        hr = a.header_row

        # effective column roles
        for c, col in a.columns.items():
            o = col_over.get(_key(sh.name, c), {})
            st.roles[c] = {
                "role": o.get("role", col.role),
                "category": o.get("category", col.category),
                "action": o.get("action", "auto"),
                "price_points": o.get("price_points", settings.price_points),
                "header": col.header,
            }

        numeric_cells: list[tuple[int, int, str, str]] = []   # (r, c, role, factor key)

        for (r, c), kind in sorted(a.kinds.items()):
            v = sh.get(r, c)
            ref = cell_ref(r, c)
            co_over = cell_over.get(_key(sh.name, ref))
            role = st.roles.get(c, {})
            col_keep = role.get("action") == "keep" and r > hr

            if kind in ("empty", "bool", "other"):
                continue
            if kind == "formula":
                st.cells[(r, c)] = CellOut("formula", v, v, "formula kept; values are recalculated by Excel")
                continue
            if kind == "date":
                st.cells[(r, c)] = CellOut("date", v, v)
                continue
            if co_over == "keep" or col_keep:
                if kind == "text" and co_over == "keep":
                    # learn: everything new in this cell is safe from now on
                    probe = mask_text(v, _copy_lib(lib), rng)
                    for rp in probe.replacements:
                        if rp.kind == "name":
                            lib.add_safe(rp.original)
                            for w in re.findall(r"[A-Za-z][A-Za-z'&.]*", rp.original):
                                lib.add_safe(w)
                st.cells[(r, c)] = CellOut("keep", v, v, "kept by your decision")
                continue

            if kind == "text":
                lab = a.labelled.get((r, c))
                if co_over == "mask_all":
                    # learn the names inside the cell too, so next month's file needs no review
                    record(mask_text(v, lib, rng))
                    cat = (lab[1] if lab else None) or (role.get("category") if r > hr else None) or "Name"
                    res = mask_text(v, lib, rng, category=cat, mask_all=True)
                    record(res)
                    st.cells[(r, c)] = CellOut("name", v, res.text, "whole cell replaced by your decision")
                    continue
                if lab and lab[0] == "id" or (r > hr and role.get("role") == "id" and r not in a.total_rows):
                    fake = lib.fake_id(v.strip(), rng)
                    ft.ids[fake] = v.strip()
                    st.cells[(r, c)] = CellOut("id", v, fake, "ID replaced")
                    continue
                if lab and lab[0] == "entity":
                    res = mask_text(v, lib, rng, category=lab[1], strict=True)
                    note = f"{lab[1]} name (from label)"
                    strict = True
                elif r > hr and role.get("role") == "entity" and r not in a.total_rows and r not in a.label_rows:
                    res = mask_text(v, lib, rng, category=role.get("category"), strict=True)
                    note = f"{role.get('category')} column"
                    strict = True
                else:
                    res = mask_text(v, lib, rng)
                    note = "header" if r in a.header_rows else "text"
                    strict = False
                record(res)
                if not res.changed:
                    st.cells[(r, c)] = CellOut("keep", v, v)
                elif not strict and res.has_new_names:
                    found = ", ".join(sorted({rp.original for rp in res.replacements if rp.kind == "name" and rp.new}))
                    st.cells[(r, c)] = CellOut("review", v, res.text, f"new text found: {found}")
                else:
                    st.cells[(r, c)] = CellOut("name", v, res.text, note)
                continue

            if kind in ("number", "numtext"):
                lab = a.labelled.get((r, c))
                if lab and lab[0] == "id" or (r > hr and role.get("role") == "id"):
                    s = str(v).strip() if not is_number(v) else str(int(v)) if float(v).is_integer() else str(v)
                    fake = lib.fake_id(s, rng)
                    ft.ids[fake] = s
                    tw = int(fake) if isinstance(v, int) and fake.isdigit() else fake
                    st.cells[(r, c)] = CellOut("id", v, tw, "ID replaced")
                    continue
                if r > hr and role.get("role") == "date":
                    st.cells[(r, c)] = CellOut("date", v, v)
                    continue
                nrole = role.get("role") if r > hr and role.get("role") in ("measure", "count", "price", "percent") else "measure"
                if lab and lab[0] == "measure":
                    fkey = str(sh.get(r, c - 1) or f"label {ref}")
                    nrole = "measure"
                else:
                    fkey = role.get("header") or f"column {c}"
                numeric_cells.append((r, c, nrole, fkey))

        _mask_numbers(st, a, numeric_cells, lib, rng, settings, ft)

        sres = mask_text(sh.name, lib, rng)
        record(sres)
        st.new_name = sres.text[:31] if sres.changed else sh.name
        ft.sheets.append(st)

    stem, dot, ext = doc.path.name.rpartition(".")
    fres = mask_text(stem.replace("_", " "), lib, random.Random(f"{seed}-name"))
    record(fres)
    ft.new_filename = (fres.text if fres.changed else stem.replace("_", " ")).strip() + "_TWIN." + ext.lower()
    ft.new_filename = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", ft.new_filename)
    return ft


def _copy_lib(lib: Library) -> Library:
    import copy
    return copy.deepcopy(lib)


def _mask_numbers(st: SheetTwin, a: SheetAnalysis, cells, lib: Library, rng: random.Random, settings: Settings,
                  ft: FileTwin) -> None:
    sh = a.sheet
    new: dict[tuple[int, int], float] = {}
    orig: dict[tuple[int, int], float] = {}
    fmt: dict[tuple[int, int], dict | None] = {}
    roles: dict[tuple[int, int], str] = {}
    factors: dict[str, float] = {}

    def factor(key: str, role: str) -> float:
        k = f"{role}:{key}" if role == "percent" else key
        if settings.mode == "scale" and role != "percent":
            k = "__whole file__"
        if k not in factors:
            if role == "percent":
                if settings.stable_factors and k in lib.factors:
                    factors[k] = lib.factors[k]
                else:
                    f = round(rng.uniform(0.82, 0.94) if rng.random() < 0.5 else rng.uniform(1.06, 1.18), 4)
                    factors[k] = f
                    if settings.stable_factors:
                        lib.factors[k] = f
            else:
                factors[k] = lib.factor_for(k, rng, settings.stable_factors)
        return factors[k]

    for r, c, role, fkey in cells:
        v = sh.get(r, c)
        if is_number(v):
            val, f = float(v), None
        else:
            val, f = parse_number_text(v)
        orig[(r, c)] = val
        fmt[(r, c)] = f
        roles[(r, c)] = role
        if settings.mode == "random":
            nv = noisy(val, rng)
        else:
            nv = val * factor(fkey, role)
        new[(r, c)] = _shape(nv, val, v, role, st.roles.get(c, {}).get("price_points", settings.price_points), f)

    for (r, c), nv in list(new.items()):  # no masked number may keep its real value
        if orig[(r, c)] != 0 and abs(nv - orig[(r, c)]) < 1e-9:
            dec = (fmt[(r, c)] or {}).get("dec") if fmt[(r, c)] else decimals_of(sh.get(r, c))
            step = 1 if not dec else 10 ** (-dec) * max(1, round(abs(nv) * 0.07 * 10 ** dec))
            nv = nv + step if (nv > 0 and rng.random() < 0.6) or nv < 0 else nv - step
            if orig[(r, c)] > 0 and nv <= 0:
                nv = orig[(r, c)] + step
            new[(r, c)] = round(nv, dec or 0) if dec else int(round(nv))
    recalc = settings.mode in ("consistent", "scale")
    col_dec = {}
    for t, (_, _, _, rows) in a.derived.items():
        decs = [decimals_of(sh.get(r, t)) for r in rows]
        any_float = any(not isinstance(sh.get(r, t), int) for r in rows)
        col_dec[t] = max(decs + [2 if any_float else 0])
    if settings.mode == "consistent":
        for _ in range(max(1, len(a.derived))):
            for t, (x, y, div, rows) in a.derived.items():
                for r in rows:
                    if (r, t) in new and (r, x) in new and (r, y) in new:
                        nx, ny = new[(r, x)], new[(r, y)]
                        if div == 0:
                            val = max(nx, ny)
                        elif div == -1:
                            val = nx - ny
                        elif div == -2:
                            val = nx + ny
                        elif div == -3:
                            val = (nx + ny) / 2
                        else:
                            val = nx * ny / div
                        new[(r, t)] = round(val, col_dec[t])
    if recalc:
        for (tr, c) in sorted(a.totals):
            rows = a.totals[(tr, c)]
            if (tr, c) in new and all((r, c) in new for r in rows):
                dec = max([decimals_of(sh.get(r, c)) if is_number(sh.get(r, c)) else (fmt[(r, c)] or {}).get("dec", 0)
                           for r in rows + [tr]] + [decimals_of(new[(r, c)]) for r in rows] or [0])
                s = sum(new[(r, c)] for r in rows)
                new[(tr, c)] = int(round(s)) if dec == 0 else round(s, dec)

    for (r, c), nv in new.items():
        v = sh.get(r, c)
        f = fmt[(r, c)]
        if f:
            tw = format_number_text(nv, f)
        elif isinstance(v, int) and float(nv).is_integer():
            tw = int(nv)
        else:
            tw = nv
        note = "scaled"
        if (r, c) in a.totals and recalc:
            note = "total recalculated"
        elif c in a.derived and r in a.derived[c][3] and settings.mode == "consistent":
            x, y, div, _ = a.derived[c]
            from openpyxl.utils import get_column_letter as L
            note = {0: f"= max({L(x)}, {L(y)})", -1: f"= {L(x)} − {L(y)}", -2: f"= {L(x)} + {L(y)}", -3: f"= average of {L(x)}, {L(y)}"}.get(
                div, f"= {L(x)} × {L(y)}" + (" ÷ 100" if div == 100 else ""))
        elif settings.mode == "random":
            note = "random value"
        st.cells[(r, c)] = CellOut("number", v, tw, note)
        ft.numbers.append({"sheet": sh.name, "cell": cell_ref(r, c), "real": orig[(r, c)], "fake": nv,
                           "computed": note.startswith("=") or note == "total recalculated"})
    ft.factors.update({k: v for k, v in factors.items()})


def _shape(nv: float, val: float, raw, role: str, price_points: bool, f: dict | None) -> float:
    if val == 0:
        return 0
    dec = f["dec"] if f else decimals_of(raw)
    if role == "count":
        n = int(round(nv))
        return n if n != 0 else (1 if val > 0 else -1)
    if role == "percent":
        if 0 <= val <= 100:
            nv = min(max(nv, 0.0), 100.0)
        return round(nv, dec) if dec else int(round(nv))
    if role == "price" and price_points:
        return price_point(nv)
    out = round_like(nv, raw if is_number(raw) else (int(val) if dec == 0 else val), dec)
    return out
