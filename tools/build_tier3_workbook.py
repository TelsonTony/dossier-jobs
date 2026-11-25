"""Builds data/APIKey_Based_Search.xlsx (How to Use, Tier3).

Run once to create the workbook; afterwards edit the workbook in Excel directly.
    python tools/build_tier3_workbook.py            # refuses to overwrite an existing workbook
    python tools/build_tier3_workbook.py --force
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.registry import REGISTRY  # noqa: E402
from pipeline.tier3 import SHEET, TIER3_WORKBOOK  # noqa: E402

HOW_TO = [
    ("Dossier — Tier 3 Job Sites", "title"),
    ("", None),
    ("What this is", "h"),
    ("Tier 3 = job-site APIs that need a free API key: Adzuna, Jooble, Careerjet, Reed, USAJOBS, Findwork.", None),
    ("The pipeline reads the Tier3 sheet. Only the provider_id and enabled columns are used; the rest are notes.", None),
    ("", None),
    ("When Tier 3 runs", "h"),
    ("Only on MANUAL runs: GitHub → Actions → Fetch jobs → Run workflow (GitLab: Build → Pipelines → Run pipeline).", None),
    ("Scheduled runs (every 6 hours) skip Tier 3 and keep the Tier 3 jobs from the last manual run.", None),
    ("", None),
    ("Which cells to edit", "h"),
    ("enabled: TRUE = fetch this site on manual runs; FALSE or empty = off (its jobs leave the app on the next run).", None),
    ("After editing: save, commit and push the file, then start a manual run.", None),
    ("", None),
    ("API keys", "h"),
    ("Never put keys in this file. Add them as GitHub Actions secrets (Settings → Secrets and variables → Actions)", None),
    ("or GitLab CI/CD variables (Masked). Secret names are in the secrets column. A site switched on without its", None),
    ("key shows 'Missing key' in the app and fetches nothing.", None),
    ("", None),
    ("Not here", "h"),
    ("Tier 1 companies: data/Workflow.xlsx (Companies sheet).", None),
    ("Tier 2 sites (Arbeitnow, Remotive, RemoteOK, Jobicy, We Work Remotely, The Muse): fixed in code.", None),
    ("Search words, countries and page limits for Tier 3: pipeline/config.json.", None),
]


def build(path: Path) -> None:
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

    ts = wb.create_sheet(SHEET)
    headers = ["provider_id", "name", "enabled", "secrets", "daily_quota", "notes"]
    for col, h in enumerate(headers, start=1):
        c = ts.cell(row=1, column=col, value=h)
        c.font = bold
        c.fill = head_fill
    tier3 = [e for e in REGISTRY if e["tier"] == 3]
    for r, e in enumerate(tier3, start=2):
        ts.cell(row=r, column=1, value=e["provider_id"])
        ts.cell(row=r, column=2, value=e["name"])
        ts.cell(row=r, column=3, value=True).font = blue
        ts.cell(row=r, column=4, value=", ".join(e.get("secrets") or []))
        ts.cell(row=r, column=5, value=e.get("daily_quota"))
        ts.cell(row=r, column=6).font = blue
    for i, w in enumerate([14, 12, 10, 38, 12, 50]):
        ts.column_dimensions[chr(65 + i)].width = w
    ts.freeze_panes = "A2"
    dv = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True)
    ts.add_data_validation(dv)
    dv.add("C2:C100")

    wb.active = 1
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


if __name__ == "__main__":
    if TIER3_WORKBOOK.exists() and "--force" not in sys.argv:
        print(f"{TIER3_WORKBOOK} already exists; use --force to rebuild it (your edits would be lost).")
        sys.exit(1)
    build(TIER3_WORKBOOK)
    print(f"Wrote {TIER3_WORKBOOK}")
