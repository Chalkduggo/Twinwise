"""Number parsing, formatting and masking helpers."""
from __future__ import annotations

import math
import random
import re
from datetime import date, datetime, time

_NUM_TEXT = re.compile(
    r"^\s*(?P<open>\()?\s*(?P<sign>[-+])?\s*(?P<cur>[$€£₹¥])?\s*(?P<sign2>[-+])?\s*"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<dec>\d+))?\s*(?P<pct>%)?\s*(?P<close>\))?\s*$"
)

_DATE_TEXT = re.compile(
    r"^\s*(?:"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s\-/'.,]*\d{2,4}"      # Aug-26, August 2026
    r"|\d{1,2}[\s\-/.](?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s\-/.]*\d{2,4}"  # 15-Aug-2026
    r"|\d{4}[\-/.]\d{1,2}(?:[\-/.]\d{1,2})?(?:[ t]\d{1,2}:\d{2}(?::\d{2})?)?"                  # 2026-08, 2026-08-15
    r"|\d{1,2}[\-/.]\d{1,2}[\-/.]\d{2,4}"                                                     # 08/15/2026
    r"|\d{1,2}/\d{4}"                                                                         # 08/2026
    r"|(?:q[1-4]|h[12]|fy)[\s\-']*\d{2,4}"                                                    # Q3 2026, FY26
    r")\s*$",
    re.I,
)


def is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not (isinstance(v, float) and math.isnan(v))


def parse_number_text(s: str):
    """'$1,234.50' -> (1234.5, fmt). Returns None if the text is not a plain number."""
    if not isinstance(s, str) or len(s) > 40:
        return None
    m = _NUM_TEXT.match(s)
    if not m:
        return None
    if m.group("open") and not m.group("close") or m.group("close") and not m.group("open"):
        return None
    ip = m.group("int")
    dec = m.group("dec") or ""
    val = float(ip.replace(",", "") + ("." + dec if dec else ""))
    neg = bool(m.group("open")) or (m.group("sign") == "-") or (m.group("sign2") == "-")
    if neg:
        val = -val
    fmt = {
        "cur": m.group("cur") or "",
        "thousands": "," in ip,
        "dec": len(dec),
        "pct": bool(m.group("pct")),
        "paren": bool(m.group("open")),
        "int": not dec,
    }
    return val, fmt


def format_number_text(v: float, fmt: dict) -> str:
    neg = v < 0
    a = abs(v)
    body = f"{a:,.{fmt['dec']}f}" if fmt["thousands"] else f"{a:.{fmt['dec']}f}"
    body = fmt["cur"] + body + ("%" if fmt["pct"] else "")
    if neg:
        return f"({body})" if fmt["paren"] else "-" + body
    return body


def is_date_text(s: str) -> bool:
    return isinstance(s, str) and len(s) <= 30 and bool(_DATE_TEXT.match(s))


def is_date_value(v) -> bool:
    return isinstance(v, (datetime, date, time))


def decimals_of(v) -> int:
    if isinstance(v, str):
        p = parse_number_text(v)
        return p[1]["dec"] if p else 0
    if isinstance(v, int) or not is_number(v):
        return 0
    s = f"{v:.10f}".rstrip("0")
    return min(len(s.split(".")[1]) if "." in s else 0, 4)


def round_like(new: float, original, dec: int | None = None):
    """Round ``new`` the way ``original`` looks: ints stay ints, decimals keep their count."""
    if dec is None:
        dec = decimals_of(original)
    if isinstance(original, int) or dec == 0:
        n = int(round(new))
        if original != 0 and n == 0:
            n = 1 if original > 0 else -1
        return n
    return round(new, dec)


def price_point(v: float) -> float:
    """3.64 -> 3.99, 12.30 -> 11.99. Keeps small values as they are."""
    if abs(v) < 1:
        return round(v, 2)
    sign = -1 if v < 0 else 1
    p = max(round(abs(v)), 1) - 0.01
    return round(sign * p, 2)


def noisy(v: float, rng: random.Random, low=0.55, high=1.45) -> float:
    f = rng.uniform(low, high)
    if abs(f - 1) < 0.08:
        f += 0.15
    return v * f
