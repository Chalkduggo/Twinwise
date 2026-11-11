"""Local web server for the review screen.

Binds to 127.0.0.1 only and rejects requests whose Host header is not local, so
other machines and websites cannot reach it. Nothing is sent anywhere.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import tempfile
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .analyze import ROLE_LABELS
from .document import cell_ref
from .engine import Job
from .keyfile import restore
from .library import Library
from .twin import Settings

UI_DIR = Path(__file__).parent / "ui"
JOBS: dict[str, Job] = {}
EXPORT_DIRS: set[Path] = set()
_LOCK = threading.RLock()
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "testserver"}

app = FastAPI(title="Twinwise", version=__version__, docs_url=None, redoc_url=None)


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = (request.headers.get("host") or "").rsplit(":", 1)[0]
    if host not in LOCAL_HOSTS:
        return JSONResponse({"detail": "Twinwise only accepts requests from this computer."}, status_code=403)
    return await call_next(request)


app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    return (UI_DIR / "index.html").read_text(encoding="utf-8")


def _job(job_id: str) -> Job:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "This session has expired. Please upload the files again.")
    return job


def _display(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        s = f"{v:,.4f}".rstrip("0").rstrip(".")
        return s
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _summary(job: Job) -> dict:
    files = []
    for i, fj in enumerate(job.files):
        files.append({
            "index": i, "name": fj.doc.name, "twin_name": fj.twin.new_filename,
            "template": fj.template_name, "template_found": fj.template is not None,
            "template_score": round(fj.template_score, 2), "counts": fj.twin.counts(),
            "sheets": [{"index": si, "name": st.analysis.sheet.name, "new_name": st.new_name,
                        "rows": st.analysis.sheet.max_row, "cols": st.analysis.sheet.max_col,
                        "hidden": st.analysis.sheet.hidden, "counts": st.counts()}
                       for si, st in enumerate(fj.twin.sheets)],
        })
    return {"id": job.id, "settings": job.settings.to_dict(), "files": files, "counts": job.counts()}


@app.get("/api/status")
def status():
    lib = Library.load()
    return {"version": __version__, "home": str(lib.home), "templates": len(lib.list_templates()),
            "names": len(lib.names), "safe_words": len(lib.safe_words), "history": len(lib.history())}


@app.post("/api/jobs")
async def create_job(files: list[UploadFile] = File(...)):
    up = Path(tempfile.mkdtemp(prefix="twinwise_up_"))
    paths = []
    for f in files:
        name = Path(f.filename or "upload").name
        target = up / name
        with open(target, "wb") as out:
            while chunk := await f.read(1 << 20):
                out.write(chunk)
        paths.append(target)
    try:
        job = Job.create(paths)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # unreadable or corrupt file
        raise HTTPException(400, f"Could not read the file: {e}")
    with _LOCK:
        JOBS[job.id] = job
    return _summary(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _summary(_job(job_id))


@app.get("/api/jobs/{job_id}/grid")
def grid(job_id: str, file: int = 0, sheet: int = 0, offset: int = 0, limit: int = 400):
    job = _job(job_id)
    fj = job.files[file]
    st = fj.twin.sheets[sheet]
    a = st.analysis
    sh = a.sheet
    cols = []
    from openpyxl.utils import get_column_letter
    cell_over = fj.overrides.get("cells", {})
    col_over = fj.overrides.get("columns", {})
    for c in range(1, sh.max_col + 1):
        role = st.roles.get(c, {})
        r = role.get("role", "empty")
        label = ROLE_LABELS.get(r, r)
        if role.get("action") == "keep":
            label = "Kept by you"
        elif r == "entity" and role.get("category"):
            label = f"{role['category']} · replace"
        elif c in a.derived and job.settings.mode == "consistent":
            label = "Formula · recalc"
        cols.append({"index": c, "letter": get_column_letter(c), "header": role.get("header", ""), "role": r,
                     "category": role.get("category"), "action": role.get("action", "auto"), "label": label,
                     "price_points": role.get("price_points", True), "derived": c in a.derived,
                     "override_role": col_over.get(f"{sh.name}!{c}", {}).get("role", "auto")})
    rows = []
    last = min(sh.max_row, offset + limit)
    for r in range(offset + 1, last + 1):
        cells = []
        for c in range(1, sh.max_col + 1):
            co = st.cells.get((r, c))
            if co is None:
                v = sh.get(r, c)
                if v is None or (isinstance(v, str) and not v.strip()):
                    continue
                cells.append({"c": c, "s": "keep", "o": _display(v), "t": _display(v), "n": ""})
            else:
                cells.append({"c": c, "s": co.status, "o": _display(co.original), "t": _display(co.twin), "n": co.note,
                              "d": cell_over.get(f"{sh.name}!{cell_ref(r, c)}", "auto")})
        rows.append({"r": r, "cells": cells, "total": r in a.total_rows, "header": r in a.header_rows})
    merged = [m for m in sh.merged if m[0] <= last]
    return {"columns": cols, "rows": rows, "max_row": sh.max_row, "max_col": sh.max_col, "offset": offset,
            "merged": merged, "header_rows": a.header_rows, "sheet": sh.name, "new_name": st.new_name}


@app.post("/api/jobs/{job_id}/cell")
async def set_cell(job_id: str, request: Request):
    body = await request.json()
    job = _job(job_id)
    fj = job.files[body["file"]]
    sheet = fj.twin.sheets[body["sheet"]].analysis.sheet.name
    with _LOCK:
        job.set_cell(body["file"], sheet, body["ref"], body.get("decision"))
    return _summary(job)


@app.post("/api/jobs/{job_id}/column")
async def set_column(job_id: str, request: Request):
    body = await request.json()
    job = _job(job_id)
    fj = job.files[body["file"]]
    sheet = fj.twin.sheets[body["sheet"]].analysis.sheet.name
    opts = {k: body[k] for k in ("role", "category", "action", "price_points") if k in body}
    if opts.get("action") == "auto":
        opts["action"] = None
    if opts.get("role") == "auto":
        opts["role"] = None
        opts["category"] = None
    with _LOCK:
        job.set_column(body["file"], sheet, int(body["col"]), **opts)
    return _summary(job)


@app.post("/api/jobs/{job_id}/settings")
async def set_settings(job_id: str, request: Request):
    body = await request.json()
    job = _job(job_id)
    with _LOCK:
        job.settings = Settings.from_dict({**job.settings.to_dict(), **body})
        job._settings_locked = True
        job.rebuild()
    return _summary(job)


@app.post("/api/jobs/{job_id}/template")
async def name_template(job_id: str, request: Request):
    body = await request.json()
    job = _job(job_id)
    job.files[body["file"]].template_name = (body.get("name") or "").strip()[:80] or job.files[body["file"]].template_name
    return _summary(job)


@app.get("/api/jobs/{job_id}/preview")
def preview(job_id: str, file: int = 0, max_rows: int = 60):
    """Plain-text view of the twin: exactly the values an AI tool will read."""
    job = _job(job_id)
    fj = job.files[file]
    out = []
    for st in fj.twin.sheets:
        sh = st.analysis.sheet
        out.append(f"## {st.new_name}")
        widths = {}
        grid_rows = []
        for r in range(1, min(sh.max_row, max_rows) + 1):
            row = []
            for c in range(1, sh.max_col + 1):
                co = st.cells.get((r, c))
                v = co.twin if co else sh.get(r, c)
                s = " ".join(_display(v).split())
                row.append(s)
                widths[c] = min(max(widths.get(c, 0), len(s)), 34)
            if any(row):
                grid_rows.append(row)
        keep = [c for c in range(1, sh.max_col + 1) if widths.get(c)]
        for row in grid_rows:
            out.append("  ".join(row[c - 1][:34].ljust(widths[c]) for c in keep).rstrip())
        if sh.max_row > max_rows:
            out.append(f"… {sh.max_row - max_rows} more rows")
        out.append("")
    return {"file": fj.twin.new_filename, "text": "\n".join(out)}


@app.post("/api/jobs/{job_id}/verify")
def verify(job_id: str):
    job = _job(job_id)
    tmp = job.workdir / "verify" / datetime.now().strftime("%H%M%S%f")
    rep = job.export(tmp, save_learning=False)
    return {"all_clear": rep["all_clear"], "files": rep["files"]}


@app.post("/api/jobs/{job_id}/export")
async def export(job_id: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    job = _job(job_id)
    out = Path(body.get("out_dir") or (Path.home() / "Twinwise" / "exports" / datetime.now().strftime("%Y-%m-%d_%H%M%S")))
    with _LOCK:
        rep = job.export(out, save_learning=True)
    EXPORT_DIRS.add(Path(rep["out_dir"]).resolve())
    files = [{"label": "Twin", "name": f["twin_name"], "path": f["twin"], "kind": "twin"} for f in rep["files"]]
    files.append({"label": "Private key", "name": Path(rep["key_path"]).name, "path": rep["key_path"], "kind": "key"})
    return {**rep, "downloads": files}


@app.get("/api/download")
def download(path: str):
    p = Path(path).resolve()
    if not any(str(p).startswith(str(d)) for d in EXPORT_DIRS) or not p.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(p, filename=p.name)


@app.post("/api/open-folder")
async def open_folder(request: Request):
    body = await request.json()
    p = Path(body["path"]).resolve()
    if not any(str(p).startswith(str(d)) for d in EXPORT_DIRS):
        raise HTTPException(404, "Folder not found")
    folder = p if p.is_dir() else p.parent
    try:
        if platform.system() == "Windows":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as e:
        raise HTTPException(500, f"Could not open the folder: {e}")
    return {"ok": True}


# ---------------- library ----------------
@app.get("/api/library")
def library():
    lib = Library.load()
    names = sorted(lib.names.values(), key=lambda e: (e["category"], e["fake"]))
    return {"home": str(lib.home), "safe_words": sorted(lib.safe_words), "names": names,
            "templates": lib.list_templates(), "history": lib.history()}


@app.post("/api/library/safe")
async def lib_safe(request: Request):
    body = await request.json()
    lib = Library.load()
    word = (body.get("word") or "").strip()
    if not word:
        raise HTTPException(400, "Enter a word or phrase")
    if body.get("remove"):
        lib.remove_safe(word)
    else:
        lib.add_safe(word)
    lib.save()
    return {"ok": True}


@app.post("/api/library/name")
async def lib_name(request: Request):
    body = await request.json()
    lib = Library.load()
    real = (body.get("real") or "").strip()
    if not real:
        raise HTTPException(400, "Enter the real name")
    if body.get("delete"):
        lib.forget_name(real)
    else:
        fake = (body.get("fake") or "").strip()
        cat = body.get("category") or "Name"
        if fake:
            lib.set_name(real, fake, cat)
        else:
            lib.fake_name(real, cat)
    lib.save()
    return {"ok": True}


@app.delete("/api/library/templates/{file_name}")
def lib_template_delete(file_name: str):
    lib = Library.load()
    lib.delete_template(file_name)
    return {"ok": True}


@app.post("/api/restore")
async def restore_text(request: Request):
    body = await request.json()
    key = body.get("key")
    if isinstance(key, str):
        key = json.loads(key)
    if not key or key.get("format") != "twinwise-key/1":
        raise HTTPException(400, "That is not a Twinwise key file.")
    return restore(body.get("text", ""), key)


def run(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    import uvicorn

    if host not in ("127.0.0.1", "localhost"):
        print("Note: Twinwise is designed to run on this computer only.")
    url = f"http://{host}:{port}"
    print(f"Twinwise {__version__} is running at {url}\nPress Ctrl+C to stop. Your files never leave this computer.")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
