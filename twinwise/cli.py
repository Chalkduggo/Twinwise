"""Command line: ``twinwise twin``, ``twinwise restore``, ``twinwise ui``, ``twinwise demo``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _unlock_library() -> None:
    """If the library is password-protected, get the password (environment variable or prompt)."""
    import getpass
    import os

    from . import library as L

    if not L.is_protected() or L.is_unlocked():
        return
    pw = os.environ.get("TWINWISE_PASSWORD")
    for attempt in range(3):
        if not pw:
            pw = getpass.getpass("Library password: ")
        try:
            L.unlock(pw)
            return
        except L.WrongPassword:
            print("Wrong password.", file=sys.stderr)
            pw = None
            if os.environ.get("TWINWISE_PASSWORD"):
                break
    raise SystemExit("Could not unlock the library.")


def _twin(args) -> int:
    from .engine import Job
    from .twin import Settings

    import os

    _unlock_library()
    settings = Settings(mode=args.mode, price_points=not args.no_price_points, stable_factors=not args.no_stable,
                        variation=args.variation)
    key_password = args.key_password or os.environ.get("TWINWISE_KEY_PASSWORD") or None
    job = Job.create(args.files, settings=settings)
    job._settings_locked = True
    out = Path(args.out or (Path.home() / "Twinwise" / "exports"))
    for fj in job.files:
        c = fj.twin.counts()
        tmpl = f"template '{fj.template_name}' ({fj.template_score:.0%})" if fj.template else "new layout"
        print(f"• {fj.doc.name}\n    {c.get('number', 0)} numbers, {c.get('name', 0) + c.get('id', 0)} names/IDs, "
              f"{c.get('review', 0)} auto-masked for review · {tmpl}")
    rep = job.export(out, save_learning=not args.no_learn, context=not args.no_context, key_password=key_password)
    print()
    for f in rep["files"]:
        status = "0 leaks" if f["leak"]["ok"] else f"{f['leak']['leak_count']} LEAKS - do not share"
        print(f"  {f['twin_name']}  ·  {status}  ·  risk {f['risk']['level']}")
        for c in f.get("context", []):
            print(f"    + {Path(c).name}")
        if f.get("removed"):
            print("    removed: " + ", ".join(f"{x['count']} × {x['what']}" for x in f["removed"]))
    lock_note = "password-protected" if rep["key_protected"] else "NOT password-protected - use --key-password"
    print(f"\nSaved to {rep['out_dir']}\nPrivate key: {rep['key_path']}  ({lock_note}; never share this file)")
    job.cleanup()
    return 0 if rep["all_clear"] else 2


def _restore(args) -> int:
    import getpass
    import os

    from . import library as L
    from .keyfile import WrongPassword, is_encrypted_key, load_key, restore

    pw = args.password or os.environ.get("TWINWISE_KEY_PASSWORD") or os.environ.get("TWINWISE_PASSWORD")
    if is_encrypted_key(args.key) and not pw:
        pw = getpass.getpass("Key file password: ")
    try:
        key = load_key(args.key, pw)
    except WrongPassword:
        raise SystemExit("Wrong password for this key file.")
    text = Path(args.file).read_text(encoding="utf-8") if args.file and args.file != "-" else sys.stdin.read()
    res = restore(text, key)
    print(res["text"])
    if res["note"]:
        print("\n# " + res["note"], file=sys.stderr)
    return 0


def _protect(args) -> int:
    import getpass

    from . import library as L

    _unlock_library()
    if args.off:
        L.set_protection(None)
        print("Library protection is off. The library is stored as plain files again.")
        return 0
    a = getpass.getpass("New library password (at least 8 characters): ")
    if a != getpass.getpass("Repeat the password: "):
        raise SystemExit("The two passwords are not the same.")
    try:
        L.set_protection(a)
    except ValueError as e:
        raise SystemExit(str(e))
    print("Library protection is on. There is no password recovery - keep the password safe.")
    return 0


def _ui(args) -> int:
    from .server import run

    run(host=args.host, port=args.port, open_browser=not args.no_browser)
    return 0


def _demo(args) -> int:
    from .demo import write_demo

    out = Path(args.out or (Path.home() / "Twinwise" / "demo"))
    for p in write_demo(out):
        print(p)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="twinwise", description="Make a safe twin of business spreadsheets before you use AI. Runs locally.")
    p.add_argument("--version", action="version", version=f"twinwise {__version__}")
    sub = p.add_subparsers(dest="cmd")

    t = sub.add_parser("twin", help="create twins of .xlsx/.csv/.zip files")
    t.add_argument("files", nargs="+")
    t.add_argument("-o", "--out", help="output folder (default ~/Twinwise/exports)")
    t.add_argument("--mode", choices=["consistent", "scale", "random"], default="consistent",
                   help="consistent: totals and formulas still add up (default); scale: one hidden factor; random: noise")
    t.add_argument("--no-price-points", action="store_true", help="do not round prices to .99 points")
    t.add_argument("--no-stable", action="store_true", help="new hidden factors every time (trends across months not comparable)")
    t.add_argument("--no-learn", action="store_true", help="do not save templates or names to your library")
    t.add_argument("--no-context", action="store_true", help="skip the AI-ready context doc and RAG chunks")
    t.add_argument("--variation", type=float, default=0.05, choices=[0, 0.05, 0.1, 0.2],
                   help="hidden extra change per row in consistent mode (default 0.05 = up to ±5%%)")
    t.add_argument("--key-password", help="encrypt the key file with this password (or set TWINWISE_KEY_PASSWORD)")
    t.set_defaults(fn=_twin)

    r = sub.add_parser("restore", help="turn an AI answer about the twin back into real names")
    r.add_argument("--key", required=True, help="the twin-key_*.json file")
    r.add_argument("--password", help="password of the key file (you are asked if it is needed)")
    r.add_argument("file", nargs="?", help="text file with the AI answer (default: read from stdin)")
    r.set_defaults(fn=_restore)

    pr = sub.add_parser("protect", help="password-protect the library (names, IDs, factors, history)")
    pr.add_argument("--off", action="store_true", help="turn protection off")
    pr.set_defaults(fn=_protect)

    u = sub.add_parser("ui", help="open the review screen in your browser")
    u.add_argument("--port", type=int, default=8765)
    u.add_argument("--host", default="127.0.0.1")
    u.add_argument("--no-browser", action="store_true")
    u.set_defaults(fn=_ui)

    d = sub.add_parser("demo", help="write made-up demo files to try Twinwise")
    d.add_argument("-o", "--out")
    d.set_defaults(fn=_demo)

    args = p.parse_args(argv)
    if not getattr(args, "fn", None):
        args = p.parse_args(["ui"])
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
