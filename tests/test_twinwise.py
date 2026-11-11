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
    h = tmp_path / "lib"
    monkeypatch.setenv("TWINWISE_HOME", str(h))
    return h


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
            text = p.read_text()
        else:
            wb = openpyxl.load_workbook(p)
            text = " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)
            text += " " + (wb.properties.creator or "")
        for secret in ("Northwind", "LANTERN", "Bluepeak", "Harbor Media", "Macon", "Quiet Orchard", "harbormedia",
                       "418207", "Maya Fernandes", "Reporting"):
            assert secret.lower() not in text.lower(), (p.name, secret)
        assert "Northwind" not in p.name and "LANTERN" not in p.name


def test_csv_keeps_formatting_and_totals(home, demo, tmp_path):
    job = Job.create([demo[3]], seed=4)
    rep = job.export(tmp_path / "out")
    rows = list(csv.reader(io.StringIO(Path(rep["files"][0]["twin"]).read_text())))
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
    assert "LANTERN FAMILY CHANNEL" in out["text"] and "Macon" in out["text"]


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
