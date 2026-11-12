"""End-to-end tests on made-up demo files."""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path

import openpyxl
import pytest

from twinwise import Job, Library, Settings, load_key, restore
from twinwise.demo import ppv_report, statement_csv, vendor_report, write_demo


@pytest.fixture()
def home(tmp_path, monkeypatch):
    from twinwise import library as L
    h = tmp_path / "lib"
    monkeypatch.setenv("TWINWISE_HOME", str(h))
    L.lock()
    yield h
    L.lock()


DATA = Path(__file__).parent / "data"


@pytest.fixture()
def demo(tmp_path):
    return write_demo(tmp_path / "demo")


def _sum_ok(job):
    for fj in job.files:
        for st in fj.twin.sheets:
            a = st.analysis
            for (tr, c), rows in a.totals.items():
                tv = st.cells[(tr, c)].twin
                assert abs(_num(tv) - sum(_num(st.cells[(r, c)].twin) for r in rows)) <= 0.011, (fj.doc.name, tr, c)
            for t, (x, y, div, rows) in a.derived.items():
                for r in rows:
                    vx, vy, vt = (_num(st.cells[(r, k)].twin) for k in (x, y, t))
                    exp = {0: max(vx, vy), -1: vx - vy, -2: vx + vy, -3: (vx + vy) / 2}.get(div, vx * vy / (div or 1))
                    assert abs(exp - vt) <= 0.011, (fj.doc.name, r, t)


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).replace("$", "").replace(",", "").replace("%", ""))


def test_twins_have_no_leaks_and_still_add_up(home, demo, tmp_path):
    job = Job.create(demo[:1] + demo[2:], seed=5)
    _sum_ok(job)
    rep = job.export(tmp_path / "out")
    assert rep["all_clear"]
    for f in rep["files"]:
        assert f["leak"]["leak_count"] == 0


def test_every_masked_number_changes(home, demo):
    job = Job.create(demo[:1], seed=8)
    for st in job.files[0].twin.sheets:
        for co in st.cells.values():
            if co.status == "number" and _num(co.original) != 0 and "recalculated" not in co.note and not co.note.startswith("="):
                assert _num(co.twin) != _num(co.original)


def test_names_are_consistent_across_files(home, demo):
    job = Job.create([demo[0], demo[1]], seed=3)
    a = job.files[0].twin.sheets[0].cells[(2, 2)].twin
    b = job.files[1].twin.sheets[0].cells[(2, 2)].twin
    assert a == b and a != "LANTERN FAMILY CHANNEL"


def test_real_names_are_gone_from_saved_twin(home, demo, tmp_path):
    job = Job.create([demo[0], demo[2], demo[3]], seed=2)
    rep = job.export(tmp_path / "out")
    for f in rep["files"]:
        p = Path(f["twin"])
        if p.suffix == ".csv":
            text = p.read_text(encoding="utf-8")
        else:
            wb = openpyxl.load_workbook(p)
            text = " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)
            text += " " + (wb.properties.creator or "")
        for secret in ("Northwind", "LANTERN", "Bluepeak", "Harbor Media", "Aldermoor", "Quiet Orchard", "harbormedia",
                       "418207", "Maya Fernandes", "Reporting"):
            assert secret.lower() not in text.lower(), (p.name, secret)
        assert "Northwind" not in p.name and "LANTERN" not in p.name


def test_csv_keeps_formatting_and_totals(home, demo, tmp_path):
    job = Job.create([demo[3]], seed=4)
    rep = job.export(tmp_path / "out")
    rows = list(csv.reader(io.StringIO(Path(rep["files"][0]["twin"]).read_text(encoding="utf-8"))))
    assert rows[0][0] == "Partner"
    assert rows[1][5].startswith("$") and rows[1][6].endswith("%")
    body = [r for r in rows[1:] if r[0] != "Total"]
    total = [r for r in rows if r[0] == "Total"][0]
    assert sum(int(r[3]) for r in body) == int(total[3])
    assert abs(sum(_num(r[7]) for r in body) - _num(total[7])) < 0.02


def test_template_is_recognised_next_month(home, demo, tmp_path):
    Job.create([demo[0]], seed=1).export(tmp_path / "o1")
    job = Job.create([demo[1]], seed=1)
    fj = job.files[0]
    assert fj.template is not None and fj.template_score >= 0.9
    # the title row names were reviewed automatically last month; nothing new now
    assert fj.twin.counts().get("review", 0) == 0


def test_keep_decision_is_learned(home, demo, tmp_path):
    job = Job.create([demo[0]], seed=1)
    assert job.files[0].twin.sheets[0].cells[(1, 1)].status == "review"
    job.set_cell(0, "Sheet1", "A1", "keep")
    assert job.files[0].twin.sheets[0].cells[(1, 1)].status == "keep"
    job.export(tmp_path / "o1")
    assert Library.load().is_safe("Northwind")


def test_column_keep_override(home, demo):
    job = Job.create([demo[0]], seed=1)
    job.set_column(0, "Sheet1", 7, action="keep")
    st = job.files[0].twin.sheets[0]
    assert all(co.twin == co.original for (r, c), co in st.cells.items() if c == 7)


def test_restore_round_trip(home, demo, tmp_path):
    job = Job.create([demo[0]], seed=1)
    st = job.files[0].twin.sheets[0]
    fake_vendor = st.cells[(2, 2)].twin
    fake_region = st.cells[(6, 1)].twin.split(" for ")[1]
    rep = job.export(tmp_path / "o")
    key = load_key(rep["key_path"])
    out = restore(f"{fake_vendor} sold the most in {fake_region}.", key)
    assert "LANTERN FAMILY CHANNEL" in out["text"] and "Aldermoor" in out["text"]


@pytest.mark.parametrize("mode", ["consistent", "scale", "random"])
def test_modes(home, demo, tmp_path, mode):
    job = Job.create([demo[0], demo[2]], settings=Settings(mode=mode), seed=6)
    rep = job.export(tmp_path / mode, save_learning=False)
    assert rep["all_clear"]
    if mode != "random":
        for fj in job.files:
            for st in fj.twin.sheets:
                for (tr, c), rows in st.analysis.totals.items():
                    assert abs(_num(st.cells[(tr, c)].twin) - sum(_num(st.cells[(r, c)].twin) for r in rows)) <= 0.011


def test_zip_input(home, demo, tmp_path):
    import zipfile
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in demo:
            zf.write(p, p.name)
        zf.writestr("../evil.xlsx", b"not really")  # path traversal attempt is ignored safely
    with pytest.raises(Exception):
        Job.create([z])  # the fake xlsx is unreadable -> clear error
    with zipfile.ZipFile(z, "w") as zf:
        for p in demo:
            zf.write(p, "reports/" + p.name)
    job = Job.create([z])
    assert len(job.files) == 4
    assert all(f.doc.path.parent.name.endswith("_unzipped") for f in job.files)


def test_server_flow(home, demo):
    from fastapi.testclient import TestClient
    from twinwise.server import app

    c = TestClient(app)
    with open(demo[0], "rb") as f:
        r = c.post("/api/jobs", files=[("files", (demo[0].name, f.read()))])
    assert r.status_code == 200, r.text
    job = r.json()
    g = c.get(f"/api/jobs/{job['id']}/grid?file=0&sheet=0").json()
    assert g["columns"][0]["role"] == "entity"
    r = c.post(f"/api/jobs/{job['id']}/cell", json={"file": 0, "sheet": 0, "ref": "A1", "decision": "mask_all"})
    assert r.status_code == 200
    v = c.post(f"/api/jobs/{job['id']}/verify").json()
    assert v["all_clear"]
    pv = c.get(f"/api/jobs/{job['id']}/preview?file=0").json()
    assert "LANTERN" not in pv["text"] and "Northwind" not in pv["text"]
    assert c.get("/api/status", headers={"host": "evil.example"}).status_code == 403


def test_mask_all_decision_is_learned(home, demo, tmp_path):
    job = Job.create([demo[0]], seed=1)
    job.set_cell(0, "Sheet1", "A1", "mask_all")
    job.export(tmp_path / "o1")
    nxt = Job.create([demo[1]], seed=1)
    assert nxt.files[0].twin.counts().get("review", 0) == 0


def test_ai_context_files(home, demo, tmp_path):
    import json as _json
    job = Job.create([demo[0], demo[3]], seed=2)
    rep = job.export(tmp_path / "out")
    assert rep["all_clear"]
    for f in rep["files"]:
        md, jl = sorted(f["context"], key=lambda p: p.endswith(".jsonl"))
<<<<<<< Updated upstream
        text = Path(md).read_text(encoding="utf-8")
        assert "synthetic twin" in text and "**Columns**" in text
        chunks = [_json.loads(l) for l in Path(jl).read_text(encoding="utf-8").splitlines()]
        assert any(c["type"] == "row" for c in chunks) and all(c["text"] and c["id"] for c in chunks)
        blob = (text + Path(jl).read_text(encoding="utf-8")).lower()
        for secret in ("northwind", "lantern", "harbor media", "aldermoor", "quiet orchard", "418207"):
            assert secret not in blob, secret
    ppv = Path([c for c in rep["files"][0]["context"] if c.endswith(".md")][0]).read_text(encoding="utf-8")
    assert "Revenue = Number of Buys × Sale Price" in ppv


# ---------------------------------------------------------------- 0.3.0

def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    return path


def _ratios(job, col):
    st = job.files[0].twin.sheets[0]
    return [_num(co.twin) / _num(co.original) for (r, c), co in sorted(st.cells.items())
            if c == col and co.status == "number" and r not in st.analysis.total_rows]


def test_row_variation_hides_the_column_factor(home, tmp_path):
    rows = [["Region", "Amount"]] + [[f"Area {chr(65 + i)}", f"{1000 + 137.5 * i:.2f}"] for i in range(12)]
    f = _write_csv(tmp_path / "amounts.csv", rows)
    flat = _ratios(Job.create([f], settings=Settings(variation=0), seed=1), 2)
    assert max(flat) - min(flat) < 0.002                      # one factor: one known value reveals the column
    varied = _ratios(Job.create([f], settings=Settings(variation=0.10), seed=1), 2)
    assert max(varied) - min(varied) > 0.03                   # per-row change: it no longer does
    mid = sorted(varied)[len(varied) // 2]
    assert all(abs(x / mid - 1) < 0.25 for x in varied)


def test_row_variation_keeps_row_trends_between_months(home, tmp_path):
    names = [f"Area {chr(65 + i)}" for i in range(8)]
    m1 = _write_csv(tmp_path / "m1.csv", [["Region", "Amount"]] + [[n, f"{2000 + 310 * i:.2f}"] for i, n in enumerate(names)])
    m2 = _write_csv(tmp_path / "m2.csv", [["Region", "Amount"]] + [[n, f"{(2000 + 310 * i) * 1.5:.2f}"] for i, n in enumerate(names)])
    j1 = Job.create([m1], seed=1)
    j1.export(tmp_path / "o1")
    j2 = Job.create([m2], seed=99)
    a = [_num(co.twin) for (r, c), co in sorted(j1.files[0].twin.sheets[0].cells.items()) if c == 2 and r > 1]
    b = [_num(co.twin) for (r, c), co in sorted(j2.files[0].twin.sheets[0].cells.items()) if c == 2 and r > 1]
    assert all(abs(y / x - 1.5) < 0.001 for x, y in zip(a, b))    # every row still shows +50%


def test_totals_still_add_up_with_variation(home, demo, tmp_path):
    for v in (0.05, 0.2):
        job = Job.create([demo[0], demo[2], demo[3]], settings=Settings(variation=v), seed=4)
        _sum_ok(job)
        assert job.export(tmp_path / f"v{v}", save_learning=False)["all_clear"]


def test_key_file_password(home, demo, tmp_path):
    import json as _json
    from twinwise.keyfile import WrongPassword
    job = Job.create([demo[0]], seed=1)
    rep = job.export(tmp_path / "o", key_password="correct horse 9")
    raw = Path(rep["key_path"]).read_text(encoding="utf-8")
    assert rep["key_protected"] and _json.loads(raw)["format"] == "twinwise-encrypted/1"
    for secret in ("LANTERN", "Aldermoor", "Northwind", "418207"):
        assert secret not in raw
    with pytest.raises(WrongPassword):
        load_key(rep["key_path"], "wrong password")
    with pytest.raises(WrongPassword):
        load_key(rep["key_path"])
    key = load_key(rep["key_path"], "correct horse 9")
    assert any(n["real"] == "Aldermoor" for n in key["names"])
    with pytest.raises(ValueError):
        job.export(tmp_path / "o2", key_password="short")


def test_library_protection(home, demo, tmp_path):
    from twinwise import library as L
    Job.create([demo[0]], seed=1).export(tmp_path / "o1")
    assert "Aldermoor" in (home / "names.json").read_text(encoding="utf-8")
    L.set_protection("library pass 77")
    assert L.is_protected() and not (home / "names.json").exists() and not (home / "history.jsonl").exists()
    blob = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in home.rglob("*") if p.is_file())
    for secret in ("Aldermoor", "LANTERN", "Northwind", "418207"):
        assert secret not in blob
    rep = Job.create([demo[1]], seed=2).export(tmp_path / "o2")       # works while unlocked, key uses library password
    assert rep["all_clear"] and rep["key_protected"]
    assert load_key(rep["key_path"], "library pass 77")["names"]
    assert len(Library.load().history()) == 2
    L.lock()
    with pytest.raises(L.LibraryLocked):
        Job.create([demo[0]])
    with pytest.raises(L.WrongPassword):
        L.unlock("not the password")
    L.unlock("library pass 77")
    assert Library.load().lookup_name("Aldermoor")
    L.set_protection(None)
    assert not L.is_protected() and "Aldermoor" in (home / "names.json").read_text(encoding="utf-8")


def _package_text(path):
    import zipfile
    with zipfile.ZipFile(path) as z:
        return z.namelist(), " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist())


def test_pivot_tables_and_charts_are_removed(home, tmp_path):
    """A pivot cache and a chart keep copies of the original data. The twin must not carry them."""
    from twinwise.verify import leak_test
    src = DATA / "pivot_chart.xlsx"
    names, text = _package_text(src)
    assert any("pivotCache" in n for n in names) and any("charts/" in n for n in names) and "Zephyrcast" in text
    job = Job.create([src], seed=1)
    assert job.files[0].doc.hidden_parts.get("pivot_tables") == 1 and job.files[0].doc.hidden_parts.get("charts") == 1
    rep = job.export(tmp_path / "o")
    assert rep["all_clear"]
    tnames, ttext = _package_text(rep["files"][0]["twin"])
    assert not any(k in n.lower() for n in tnames for k in ("pivot", "chart", "drawing", "media"))
    for secret in ("Zephyrcast", "Quillon", "Aldermoor", "Wexley"):
        assert secret not in ttext
    # the package scan itself must catch an unstripped file
    bad = leak_test(job.files[0].twin, src)
    assert not bad.ok and any(l["type"] == "hidden part not removed" for l in bad.leaks)


def test_hidden_cell_extras_are_removed(home, tmp_path):
    from openpyxl.chart import BarChart, Reference
    from openpyxl.comments import Comment
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Partner", "City", "Units", "Revenue"])
    for i, (p_, c_) in enumerate([("Zephyrcast Cable", "Aldermoor"), ("Quillon Media", "Orrinby"), ("Zephyrcast Cable", "Tessin")]):
        ws.append([p_, c_, 10 + i, 100.5 + i])
    ws["A2"].comment = Comment("Ask Priyanka at Zephyrcast", "Reviewer")
    ws["B2"].hyperlink = "https://zephyrcast.example/aldermoor"
    dv = DataValidation(type="list", formula1='"Zephyrcast Cable,Quillon Media"')
    ws.add_data_validation(dv)
    dv.add("A2:A4")
    ws.add_table(Table(displayName="ZephyrcastDeals", ref="A1:D4"))
    ch = BarChart()
    ch.add_data(Reference(ws, min_col=4, min_row=1, max_row=4), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=4))
    ws.add_chart(ch, "F2")
    ws.oddHeader.center.text = "Zephyrcast confidential"
    wb.properties.creator = "Quillon Finance"
    src = tmp_path / "extras.xlsx"
    wb.save(src)
    job = Job.create([src], seed=1)
    hp = job.files[0].doc.hidden_parts
    assert all(hp.get(k) for k in ("comments", "hyperlinks", "validations", "tables", "charts", "headers_footers"))
    rep = job.export(tmp_path / "o")
    assert rep["all_clear"], rep["files"][0]["leak"]["leaks"]
    tnames, ttext = _package_text(rep["files"][0]["twin"])
    assert not any(k in n.lower() for n in tnames for k in ("chart", "drawing", "comment", "table"))
    for secret in ("Zephyrcast", "Quillon", "Priyanka", "Aldermoor", "zephyrcast.example"):
        assert secret.lower() not in ttext.lower(), secret
    assert rep["files"][0]["removed"]


def test_macro_workbook_twin_is_saved_as_xlsx(home, tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["Partner", "Amount"])
    wb.active.append(["Zephyrcast Cable", 1200.5])
    wb.active.append(["Quillon Media", 880.25])
    src = tmp_path / "book.xlsm"
    wb.save(src)
    rep = Job.create([src], seed=1).export(tmp_path / "o")
    assert rep["files"][0]["twin_name"].endswith("_TWIN.xlsx") and rep["all_clear"]
    openpyxl.load_workbook(rep["files"][0]["twin"])


def test_review_reaches_every_row_of_a_large_file(home, tmp_path):
    from fastapi.testclient import TestClient
    from twinwise.server import app
    rows = [["Region", "Amount", "Notes"]] + [[f"Area {i}", f"{100 + i}.00", ""] for i in range(1, 1300)]
    rows[950][2] = "Escalated to Zephyrcast legal"          # new text far beyond the first screen
    src = _write_csv(tmp_path / "big.csv", rows)
    c = TestClient(app)
    with open(src, "rb") as f:
        job = c.post("/api/jobs", files=[("files", ("big.csv", f.read()))]).json()
    assert job["counts"]["review"] >= 1
    n = c.get(f"/api/jobs/{job['id']}/next-review?file=0&sheet=0&r=0&c=0").json()
    assert n["r"] == 951 and n["c"] == 3
    page = c.get(f"/api/jobs/{job['id']}/grid?file=0&sheet=0&offset=800&limit=400").json()
    assert page["rows"][0]["r"] == 801 and any(cell["s"] == "review" for row in page["rows"] for cell in row["cells"])
    c.post(f"/api/jobs/{job['id']}/cell", json={"file": 0, "sheet": 0, "ref": "C951", "decision": "mask_all"})
    assert c.get(f"/api/jobs/{job['id']}/next-review?file=0&sheet=0&r=0&c=0").json().get("none")


def test_server_lock_and_unlock(home, demo):
    from fastapi.testclient import TestClient
    from twinwise import library as L
    from twinwise.server import app
    c = TestClient(app)
    assert c.get("/api/status").json()["protected"] is False
    assert c.post("/api/security", json={"action": "on", "password": "short"}).status_code == 400
    assert c.post("/api/security", json={"action": "on", "password": "a long password"}).json()["protected"]
    c.post("/api/lock")
    assert c.get("/api/status").json()["locked"] is True
    assert c.get("/api/library").status_code == 423
    with open(demo[0], "rb") as f:
        assert c.post("/api/jobs", files=[("files", (demo[0].name, f.read()))]).status_code == 423
    assert c.post("/api/unlock", json={"password": "nope nope"}).status_code == 401
    assert c.post("/api/unlock", json={"password": "a long password"}).status_code == 200
    assert c.get("/api/library").status_code == 200
    assert c.post("/api/security", json={"action": "off", "current": "wrong one"}).status_code == 401
    assert c.post("/api/security", json={"action": "off", "current": "a long password"}).json()["protected"] is False
=======
        text = Path(md).read_text()
        assert "synthetic twin" in text and "**Columns**" in text
        chunks = [_json.loads(l) for l in Path(jl).read_text().splitlines()]
        assert any(c["type"] == "row" for c in chunks) and all(c["text"] and c["id"] for c in chunks)
        blob = (text + Path(jl).read_text()).lower()
        for secret in ("northwind", "lantern", "harbor media", "macon", "quiet orchard", "418207"):
            assert secret not in blob, secret
    ppv = Path([c for c in rep["files"][0]["context"] if c.endswith(".md")][0]).read_text()
    assert "Revenue = Number of Buys × Sale Price" in ppv
>>>>>>> Stashed changes
