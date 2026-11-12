"""One masking job: a set of input files, your decisions, and the export.

Typical use from Python::

    from twinwise import Job
    job = Job.create(["report.xlsx"])
    job.export("out/")             # writes twins, key file and report

The review interface uses the same object: it changes ``overrides`` and calls
``rebuild()`` to refresh the plan.
"""
from __future__ import annotations

import copy
import json
import re
import secrets
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import __version__
from .analyze import SheetAnalysis, _norm, analyze
from .document import HIDDEN_LABELS, Document, cell_ref, expand_inputs, load, save_twin
from .keyfile import build_key, save_key
from .library import Library
from .twin import FileTwin, Settings, build_file_twin
from . import rag
from .verify import leak_test, leak_test_files, risk_check


@dataclass
class FileJob:
    doc: Document
    analyses: list[SheetAnalysis]
    overrides: dict = field(default_factory=lambda: {"columns": {}, "cells": {}})
    template: dict | None = None
    template_score: float = 0.0
    template_name: str = ""
    twin: FileTwin | None = None

    def fingerprint(self) -> list[str]:
        out = []
        for a in self.analyses:
            out.extend(a.fingerprint())
        return out


@dataclass
class Job:
    files: list[FileJob]
    library: Library
    settings: Settings = field(default_factory=Settings)
    seed: int = field(default_factory=lambda: secrets.randbelow(10**9))
    workdir: Path = field(default_factory=lambda: Path(tempfile.mkdtemp(prefix="twinwise_")))
    id: str = field(default_factory=lambda: secrets.token_hex(6))
    scratch: Library | None = None

    # ---------- creation ----------
    @classmethod
    def create(cls, paths: list[Path | str], library: Library | None = None, settings: Settings | None = None,
               seed: int | None = None) -> "Job":
        lib = library or Library.load()
        job = cls(files=[], library=lib, settings=settings or Settings())
        if seed is not None:
            job.seed = seed
        for path, display in expand_inputs([Path(p) for p in paths], job.workdir):
            doc = load(path, display)
            fj = FileJob(doc=doc, analyses=analyze(doc))
            job._match_template(fj)
            job.files.append(fj)
        if not job.files:
            raise ValueError("No supported files found (.xlsx, .xlsm, .csv, .tsv or a .zip of them).")
        job.rebuild()
        return job

    def _match_template(self, fj: FileJob) -> None:
        fp = set(fj.fingerprint())
        best, score = None, 0.0
        for t in self.library.list_templates():
            tfp = set(t.get("fingerprint", []))
            if not fp or not tfp:
                continue
            s = len(fp & tfp) / len(fp | tfp)
            if s > score:
                best, score = t, s
        if best and score >= 0.6:
            fj.template, fj.template_score, fj.template_name = best, score, best["name"]
            # apply column decisions by header name
            for a in fj.analyses:
                for c, col in a.columns.items():
                    o = best.get("columns", {}).get(_norm(col.header)) if col.header else None
                    if o:
                        fj.overrides["columns"][f"{a.sheet.name}!{c}"] = dict(o)
            if best.get("settings") and not getattr(self, "_settings_locked", False):
                self.settings = Settings.from_dict(best["settings"])
        else:
            fj.template_name = _suggest_template_name(fj)

    # ---------- planning ----------
    def rebuild(self) -> None:
        """Recompute every twin from the saved library plus this job's decisions."""
        self.scratch = copy.deepcopy(self.library)
        for i, fj in enumerate(self.files):
            fj.twin = build_file_twin(fj.doc, fj.analyses, self.scratch, self.settings, fj.overrides,
                                      seed=self.seed + i)

    def set_cell(self, file_index: int, sheet: str, ref: str, decision: str | None) -> None:
        cells = self.files[file_index].overrides["cells"]
        k = f"{sheet}!{ref}"
        if decision in (None, "auto"):
            cells.pop(k, None)
        else:
            cells[k] = decision
        self.rebuild()

    def set_column(self, file_index: int, sheet: str, col: int, **opts) -> None:
        cols = self.files[file_index].overrides["columns"]
        k = f"{sheet}!{col}"
        cur = cols.get(k, {})
        for key, val in opts.items():
            if val is None:
                cur.pop(key, None)
            else:
                cur[key] = val
        if cur:
            cols[k] = cur
        else:
            cols.pop(k, None)
        self.rebuild()

    def counts(self) -> dict:
        tot: dict[str, int] = {}
        for fj in self.files:
            for k, v in fj.twin.counts().items():
                tot[k] = tot.get(k, 0) + v
        return tot

    # ---------- export ----------
<<<<<<< Updated upstream
    def export(self, out_dir: Path | str, *, save_learning: bool = True, user: str = "", context: bool = True,
               key_password: str | None = None, write_key: bool = True) -> dict:
        """Write twins, context files, the key file and a report.

        ``key_password`` encrypts the key file. Without one, the library password is used if the library
        is protected; otherwise the key file is written as plain JSON.
        """
=======
    def export(self, out_dir: Path | str, *, save_learning: bool = True, user: str = "", context: bool = True) -> dict:
>>>>>>> Stashed changes
        out_dir = Path(out_dir).expanduser()
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        out_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for fj in self.files:
            values, names = fj.twin.values_for_save()
            target = out_dir / fj.twin.new_filename
            n = 1
            while target.exists():
                target = out_dir / f"{Path(fj.twin.new_filename).stem}_{n}{Path(fj.twin.new_filename).suffix}"
                n += 1
            save_twin(fj.doc, values, names, target)
            leak = leak_test(fj.twin, target)
            extras = []
            if context:
                extras = rag.write(fj.twin, target)
                extra_leak = leak_test_files(fj.twin, extras)
                leak.leaks.extend(extra_leak.leaks)
                leak.coincidences.extend(extra_leak.coincidences)
                leak.checked_values += extra_leak.checked_values
                if extra_leak.leaks:
                    for x in extras:
                        x.unlink(missing_ok=True)
                    extras = []
<<<<<<< Updated upstream
            risk = risk_check(fj.twin, self.settings)
            results.append({"original": fj.doc.name, "twin": str(target), "twin_name": target.name,
                            "context": [str(x) for x in extras],
                            "removed": [{"what": HIDDEN_LABELS.get(k, k), "count": n}
                                        for k, n in fj.doc.hidden_parts.items()],
=======
            risk = risk_check(fj.twin)
            results.append({"original": fj.doc.name, "twin": str(target), "twin_name": target.name,
                            "context": [str(x) for x in extras],
>>>>>>> Stashed changes
                            "counts": fj.twin.counts(), "leak": leak.to_dict(), "risk": risk,
                            "template": fj.template_name})
        key_path, key_protected = None, False
        if write_key:
            from .library import current_password
            pw = key_password or current_password()
            key = build_key([fj.twin for fj in self.files], self.settings.to_dict())
            key_path = save_key(key, out_dir / f"twin-key_{stamp}.json", pw)
            key_protected = bool(pw)
        report = {
            "tool": f"Twinwise {__version__}",
            "created": datetime.now().isoformat(timespec="seconds"),
            "settings": self.settings.to_dict(),
            "files": results,
            "key_file": key_path.name if key_path else None,
            "key_protected": key_protected,
            "all_clear": all(r["leak"]["ok"] for r in results),
        }
        on_disk = report
        if key_protected:
            # The report sits next to the twins in plain text, so when the key is locked it must not
            # name the real files or quote real values. The originals are inside the encrypted key.
            on_disk = dict(report, files=[
                dict({k: v for k, v in r.items() if k != "original"},
                     leak={k: v for k, v in r["leak"].items() if k in ("ok", "leak_count", "checked_values")})
                for r in results])
        (out_dir / f"twin-report_{stamp}.json").write_text(json.dumps(on_disk, indent=2, default=str), encoding="utf-8")

        if save_learning and report["all_clear"]:
            self.library = self.scratch
            for fj in self.files:
                self.save_template(fj)
            self.library.save()
            self.library.log({"user": user, "files": [{"original": r["original"], "twin": r["twin_name"],
                                                        "template": r["template"], "counts": r["counts"],
                                                        "leaks": r["leak"]["leak_count"]} for r in results],
                              "mode": self.settings.mode, "out_dir": str(out_dir)})
        report["out_dir"] = str(out_dir)
        report["key_path"] = str(key_path) if key_path else None
        return report

    def save_template(self, fj: FileJob, name: str | None = None) -> dict:
        cols = {}
        for a in fj.analyses:
            for c, col in a.columns.items():
                o = fj.overrides["columns"].get(f"{a.sheet.name}!{c}")
                if o and col.header:
                    cols[_norm(col.header)] = o
        t = {"name": name or fj.template_name, "fingerprint": fj.fingerprint(), "columns": cols,
             "settings": self.settings.to_dict(), "example_file": fj.doc.path.suffix.lower()}
        return self.library.save_template(t)

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


def _suggest_template_name(fj: FileJob) -> str:
    heads = [h for h in fj.fingerprint() if h][:4]
    base = " · ".join(h.title() for h in heads[:3]) if heads else "Layout"
    return f"{base} layout"[:60]
