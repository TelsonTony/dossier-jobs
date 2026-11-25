"""Builds data/Company_Based_Search.xlsx: the list for SEARCHING companies (not read by the workflow).

Use it to note companies you want, find their ATS + slug, and only then add them to
data/Workflow.xlsx (Companies tab), which is the file the workflow fetches.
Starts with every company already in that workflow file, so you can see what is covered.
    python tools/build_company_search_workbook.py            # refuses to overwrite
    python tools/build_company_search_workbook.py --force
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.companies import load_companies  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "Company_Based_Search.xlsx"
STATUSES = ["to check", "found", "not found", "in workflow", "paused in workflow"]

HOW_TO = [
    ("Dossier — Tier 1 Company Search", "title"),
    ("", None),
    ("What this is", "h"),
    ("Your working list for finding companies. The workflow does NOT read this file.", None),
    ("The workflow fetches only data/Workflow.xlsx (Companies tab).", None),
    ("", None),
    ("How to use", "h"),
    ("1. Add a company: company_name (+ careers_page if you know it), status = to check.", None),
    ("2. Open its careers page, click a job, and read the ATS and slug from the link:", None),
    ("     job-boards.greenhouse.io/stripe → greenhouse, stripe      jobs.lever.co/spotify → lever, spotify", None),
    ("     jobs.ashbyhq.com/ramp → ashby, ramp                       apply.workable.com/huggingface → workable, huggingface", None),
    ("3. Fill ats_type + slug and set status = found (or not found if it uses another system, e.g. Workday).", None),
    ("4. Copy found companies into Workflow.xlsx (Companies tab), set status = in workflow,", None),
    ("   then commit + push. The next run fetches them.", None),
    ("", None),
    ("Status values", "h"),
    ("to check · found · not found · in workflow · paused in workflow", None),
]


def build(path: Path) -> None:
    companies, _ = load_companies()
    wb = Workbook()
    blue = Font(color="1F4E9E")
    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="E7E2D8")

    ws = wb.active
    ws.title = "How to Use"
    for i, (text, kind) in enumerate(HOW_TO, start=1):
        c = ws.cell(row=i, column=1, value=text)
        if kind == "title":
            c.font = Font(bold=True, size=14)
        elif kind == "h":
            c.font = bold
    ws.column_dimensions["A"].width = 120

    ss = wb.create_sheet("Company Search")
    headers = ["company_name", "careers_page", "status", "ats_type", "slug", "notes"]
    for col, h in enumerate(headers, start=1):
        c = ss.cell(row=1, column=col, value=h)
        c.font = bold
        c.fill = head_fill
    for r, co in enumerate(sorted(companies, key=lambda c: c.company_name.lower()), start=2):
        values = [co.company_name, None, "in workflow" if co.enabled else "paused in workflow",
                  co.ats_type, co.slug, co.notes or None]
        for col, v in enumerate(values, start=1):
            ss.cell(row=r, column=col, value=v).font = blue
    for i, w in enumerate([20, 40, 18, 14, 18, 50]):
        ss.column_dimensions[chr(65 + i)].width = w
    ss.freeze_panes = "A2"
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True)
    ss.add_data_validation(dv)
    dv.add("C2:C2000")
    dv2 = DataValidation(type="list", formula1='"greenhouse,lever,ashby,workable,smartrecruiters,custom,unsupported"',
                         allow_blank=True)
    ss.add_data_validation(dv2)
    dv2.add("D2:D2000")

    wb.active = 1
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


if __name__ == "__main__":
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT} already exists; use --force to rebuild it (your edits would be lost).")
        sys.exit(1)
    build(OUT)
    print(f"Wrote {OUT}")
