"""Made-up demo files that look like real partner reports.

Every company, title and person here is fictional. Use these for screenshots,
tests and public demos - never real company files.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

CITIES = ["Macon", "New Orleans", "Oklahoma City", "Tulsa", "Omaha", "Wichita", "Baton Rouge", "Lafayette",
          "Shreveport", "Little Rock", "Savannah", "Augusta"]
STATES = ["GA", "LA", "OK", "OK", "NE", "KS", "LA", "LA", "LA", "AR", "GA", "GA"]


def ppv_report(path: Path, month: str = "08/2026", period: str = "Aug-26", seed: int = 1) -> Path:
    rng = random.Random(seed)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = f"Northwind Cable PPV/VOD Activity Report for {month} thru {month}"
    ws["A1"].font = Font(bold=True, size=12)
    ws["A2"], ws["B2"] = "Vendor Name", "LANTERN FAMILY CHANNEL"
    ws["A3"], ws["B3"] = "Vendor Number", "418207"
    heads = ["\nSystem", "\nTitle", "\nUBEN", "Provider \nCode", "Actual\nPeriod", "Number\nof Buys", "Sale\nPrice",
             "\nRevenue", "\nSplit %", "Split\nRate", "Minimum\nRate", "Greater\nValue", "Total\nAmount"]
    for c, h in enumerate(heads, start=1):
        cell = ws.cell(row=4, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3864")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    r = 6
    grand_b, grand_rev, grand_tot = 0, 0.0, 0.0
    for i, city in enumerate(CITIES[:9]):
        code = 99001 + i * 41
        kind = "PPV CLU" if i % 3 == 1 else "PPV"
        system = f"{code} - {kind} for {city}"
        lines = 1 if i % 4 else 2
        blk_b, blk_rev, blk_tot = 0, 0.0, 0.0
        for j in range(lines):
            price = 4.99 if j == 0 else 3.99
            buys = rng.randint(1, 30)
            rev = round(buys * price, 2)
            split = 50
            rate = round(price * split / 100, 4)
            minimum = 2.495
            greater = max(rate, minimum)
            total = round(buys * greater, 2)
            for c, v in enumerate([system, "Lantern Channel", "LANTCH", "LANTCHNL", period, buys, price, rev, split,
                                   rate, minimum, greater, total], start=1):
                ws.cell(row=r, column=c, value=v)
            blk_b += buys
            blk_rev += rev
            blk_tot += total
            r += 1
        r += 1
        ws.cell(row=r, column=1, value=f"{system} Totals").font = Font(bold=True)
        ws.cell(row=r, column=6, value=blk_b)
        ws.cell(row=r, column=8, value=round(blk_rev, 2))
        ws.cell(row=r, column=13, value=round(blk_tot, 2))
        grand_b += blk_b
        grand_rev += blk_rev
        grand_tot += blk_tot
        r += 3
    ws.cell(row=r, column=1, value="All System Totals").font = Font(bold=True)
    ws.cell(row=r, column=6, value=grand_b)
    ws.cell(row=r, column=8, value=round(grand_rev, 2))
    ws.cell(row=r, column=13, value=round(grand_tot, 2))
    for col, w in zip("ABCDEFGHIJKLM", (34, 18, 10, 12, 10, 10, 9, 10, 8, 9, 10, 10, 11)):
        ws.column_dimensions[col].width = w
    ws.row_dimensions[4].height = 32
    wb.properties.creator = "Northwind Cable Reporting"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def vendor_report(path: Path, seed: int = 2) -> Path:
    rng = random.Random(seed)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Vendor Report"
    ws["H2"] = "Bluepeak Classics SVOD"
    ws["H2"].font = Font(bold=True, size=13)
    ws["H4"] = "August, 2026"
    ws["J8"] = "BLUEPEAK CLASSICS SVOD VIEWING SUBS"
    heads9 = {10: "Beginning", 11: "Ending", 12: "Average", 13: "Cost / Sub", 14: "Gross Amount", 15: "Bad Debt",
              16: "Net Amount"}
    heads10 = {2: "MSO", 3: "System ID", 5: "System", 9: "State"}
    for c, h in heads9.items():
        ws.cell(row=9, column=c, value=h).font = Font(bold=True)
    for c, h in heads10.items():
        ws.cell(row=10, column=c, value=h).font = Font(bold=True)
    r = 11
    rows = []
    for i, (city, st) in enumerate(zip(CITIES, STATES)):
        b = rng.randint(1, 9)
        e = max(1, b + rng.randint(-2, 3))
        avg = (b + e) / 2
        gross = round(avg * 2.495, 4)
        bad = round(gross / 100, 6)
        net = round(gross - bad, 6)
        mso = "RVC" if i < 6 else "SKL"
        ws.cell(row=r, column=2, value=mso if i in (0, 6) else None)
        ws.cell(row=r, column=3, value=f"E00{1050 + i * 7}-{10 + i:02d}")
        ws.cell(row=r, column=5, value=city.upper() if i % 2 else city)
        ws.cell(row=r, column=9, value=st)
        for c, v in zip(range(10, 17), (b, e, avg, 2.495, gross, bad, net)):
            ws.cell(row=r, column=c, value=v)
        rows.append((b, e, avg, gross, bad, net))
        r += 1
    ws.cell(row=r, column=3, value="Total").font = Font(bold=True)
    for k, c in enumerate((10, 11, 12)):
        ws.cell(row=r, column=c, value=sum(x[k] for x in rows))
    ws.cell(row=r, column=14, value=round(sum(x[3] for x in rows), 4))
    ws.cell(row=r, column=15, value=round(sum(x[4] for x in rows), 6))
    ws.cell(row=r, column=16, value=round(sum(x[5] for x in rows), 6))
    r += 3
    ws.cell(row=r, column=2, value="Prepared by: Maya Fernandes, Partner Accounting")
    wb.properties.creator = "Bluepeak Media Finance"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def statement_csv(path: Path, seed: int = 3) -> Path:
    rng = random.Random(seed)
    titles = ["The Quiet Orchard", "Midnight at Larkspur", "Copper Coast", "A Winter in Calder", "Paper Lanterns",
              "The Harbor Kids", "Saltwater Summer", "Iron Valley"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Partner", "Title", "Month", "Views", "Watch Hours", "Revenue (USD)", "Rev Share %", "Payout (USD)",
                    "Contact Email"])
        tv = th = trev = tpay = 0
        for t in titles:
            views = rng.randint(800, 25000)
            hours = round(views * rng.uniform(0.6, 1.4), 1)
            rev = round(views * rng.uniform(0.004, 0.012), 2)
            share = 55
            pay = round(rev * share / 100, 2)
            tv += views
            th += hours
            trev += rev
            tpay += pay
            w.writerow(["Harbor Media Group", t, "2026-08", views, hours, f"${rev:,.2f}", f"{share}%", f"${pay:,.2f}",
                        "royalties@harbormedia.example"])
        w.writerow(["Total", "", "", tv, round(th, 1), f"${trev:,.2f}", "", f"${tpay:,.2f}", ""])
    return path


def write_demo(out_dir: Path | str) -> list[Path]:
    out = Path(out_dir)
    return [
        ppv_report(out / "LANTERN FAMILY CHANNEL - PPV Buys - Aug-2026.xlsx"),
        ppv_report(out / "LANTERN FAMILY CHANNEL - PPV Buys - Sep-2026.xlsx", month="09/2026", period="Sep-26", seed=9),
        vendor_report(out / "Bluepeak Classics SVOD - Aug 2026 Vendor Report.xlsx"),
        statement_csv(out / "harbor_media_statement_2026-08.csv"),
    ]
