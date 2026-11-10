"""Builds data/Dossier_ATS_Company_List.xlsx (How to Use, Companies, ATS Endpoints).

Run once to create the workbook; afterwards edit the workbook in Excel directly.
    python tools/build_workbook.py            # refuses to overwrite an existing workbook
    python tools/build_workbook.py --force
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

OUT = Path(__file__).resolve().parent.parent / "data" / "Dossier_ATS_Company_List.xlsx"

V_SEVERAL = "Listed by several tools; test once"
V_ONE = "Listed by one tool; test once"
V_DISAGREE = "Sources disagree on ATS; test both"
V_LIVE = "Verified live, Jul 2026 (JobsPipe check)"
V_EMPTY = "Account verified Jul 2026; no open postings at check"

COMPANIES = [
    ("Stripe", "greenhouse", "stripe", V_SEVERAL, "Fintech"),
    ("Airbnb", "greenhouse", "airbnb", V_SEVERAL, "Travel"),
    ("Cloudflare", "greenhouse", "cloudflare", V_SEVERAL, "Infrastructure"),
    ("Databricks", "greenhouse", "databricks", V_SEVERAL, "Data / AI"),
    ("Figma", "greenhouse", "figma", V_SEVERAL, "Design software"),
    ("Gusto", "greenhouse", "gusto", V_ONE, "HR / payroll"),
    ("Robinhood", "greenhouse", "robinhood", V_ONE, "Fintech"),
    ("Duolingo", "greenhouse", "duolingo", V_ONE, "Education"),
    ("GitLab", "greenhouse", "gitlab", V_SEVERAL, "Dev tools"),
    ("Airtable", "greenhouse", "airtable", V_ONE, "SaaS"),
    ("Discord", "greenhouse", "discord", V_SEVERAL, "Consumer"),
    ("Okta", "greenhouse", "okta", V_ONE, "Security"),
    ("Anthropic", "greenhouse", "anthropic", V_ONE, "AI"),
    ("Adyen", "greenhouse", "adyen", V_ONE, "Fintech (Europe)"),
    ("Brex", "greenhouse", "brex", V_DISAGREE, "Fintech; one tool lists Lever"),
    ("Spotify", "lever", "spotify", V_LIVE, "Music / tech"),
    ("Palantir", "lever", "palantir", V_LIVE, "Software"),
    ("Match Group", "lever", "matchgroup", V_LIVE, "Consumer apps"),
    ("Zoox", "lever", "zoox", V_LIVE, "Autonomous vehicles"),
    ("WHOOP", "lever", "whoop", V_LIVE, "Health tech"),
    ("Gopuff", "lever", "gopuff", V_LIVE, "Delivery"),
    ("Ro", "lever", "ro", V_LIVE, "Health"),
    ("Aircall", "lever", "aircall", V_LIVE, "SaaS (Europe)"),
    ("Ledger", "lever", "ledger", V_LIVE, "Crypto hardware (Europe)"),
    ("Entrata", "lever", "entrata", V_LIVE, "Property software"),
    ("Netflix", "lever", "netflix", V_EMPTY, "May not post here anymore"),
    ("Plaid", "lever", "plaid", V_EMPTY, "Fintech"),
    ("Kraken", "lever", "kraken", V_EMPTY, "Crypto"),
    ("Mistral AI", "lever", "mistral", V_EMPTY, "AI (Europe); may need api.eu.lever.co"),
    ("Mixpanel", "lever", "mixpanel", V_ONE, "Analytics"),
    ("Clari", "lever", "clari", V_ONE, "SaaS"),
    ("Outreach", "lever", "outreach", V_ONE, "Sales software"),
    ("OpenAI", "ashby", "openai", V_LIVE, "AI; very large board"),
    ("Notion", "ashby", "notion", V_LIVE, "Productivity"),
    ("Ramp", "ashby", "ramp", V_LIVE, "Fintech"),
    ("Linear", "ashby", "linear", V_LIVE, "Dev tools"),
    ("Cursor", "ashby", "cursor", V_LIVE, "Dev tools; slug not confirmed"),
    ("ElevenLabs", "ashby", "elevenlabs", V_LIVE, "AI voice"),
    ("Replit", "ashby", "replit", V_LIVE, "Dev tools"),
    ("Supabase", "ashby", "supabase", V_LIVE, "Dev tools"),
    ("Docker", "ashby", "docker", V_LIVE, "Dev tools"),
    ("PostHog", "ashby", "posthog", V_LIVE, "Analytics"),
    ("Substack", "ashby", "substack", V_LIVE, "Media"),
    ("Mercury", "ashby", "mercury", V_LIVE, "Fintech"),
    ("Vercel", "ashby", "vercel", V_DISAGREE, "Some tools list Greenhouse"),
    ("Deel", "ashby", "deel", V_LIVE, "HR / payroll"),
    ("Perplexity", "ashby", "perplexity", V_ONE, "AI"),
    ("Vanta", "ashby", "vanta", V_ONE, "Security"),
    ("LangChain", "ashby", "langchain", V_ONE, "AI"),
    ("Hugging Face", "workable", "huggingface", V_DISAGREE, "AI; also listed under Greenhouse"),
    ("SoundCloud", "workable", "soundcloud", V_ONE, "Music"),
]

HOW_TO = [
    ("Dossier — ATS Company List", "title"),
    ("", None),
    ("What this is", "h"),
    ("Companies whose job boards run on Greenhouse, Lever, Ashby or Workable. Each has a free public JSON endpoint with no API key.", None),
    ("The scheduled GitHub Actions job reads the Companies sheet on every run (enabled rows only).", None),
    ("", None),
    ("Which cells to edit", "h"),
    ("Blue text = your input: company_name, ats_type, slug, enabled (and endpoint for custom rows).", None),
    ("api_url and board_url are formulas built from ats_type + slug. Do not type over them.", None),
    ("To add a company: copy the last row down, then change the blue cells.", None),
    ("Example row: Stripe | greenhouse | stripe | (formula) | (formula) | ... | TRUE", None),
    ("", None),
    ("Finding the ATS and slug", "h"),
    ("Open the company's careers page and click a job. The link shows the ATS and slug:", None),
    ("  boards.greenhouse.io/stripe  or  job-boards.greenhouse.io/stripe  →  greenhouse, stripe", None),
    ("  jobs.lever.co/spotify  →  lever, spotify", None),
    ("  jobs.ashbyhq.com/ramp  →  ashby, ramp", None),
    ("  apply.workable.com/huggingface  →  workable, huggingface", None),
    ("If the company uses its own domain, view the page source and search for greenhouse, lever, ashby or workable.", None),
    ("", None),
    ("Verification column", "h"),
    ("Verified live, Jul 2026: confirmed against the ATS's public endpoint by JobsPipe (jobspipe.dev/companies-using) in July 2026.", None),
    ("Listed by several / one tool: named as a sample slug by public scraper tools (Apify listings); not independently tested.", None),
    ("Sources disagree: different sources name different ATS; test both endpoints.", None),
    ("Companies switch ATS over time. A 404 means the slug is wrong or the company moved. None of these URLs were tested from here.", None),
    ("", None),
    ("Your Excel sheet", "h"),
    ("Add your own companies from your existing sheet here. Mark Workday or custom-system companies as custom or unsupported.", None),
    ("custom rows need an https URL in the endpoint column (found in browser DevTools → Network → Fetch/XHR).", None),
]

ENDPOINTS = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", "https://job-boards.greenhouse.io/{slug}", "No", "Returns all jobs in one call; add content=true for descriptions"),
    ("lever", "https://api.lever.co/v0/postings/{slug}?mode=json", "https://jobs.lever.co/{slug}", "No", "EU boards use api.eu.lever.co; supports &limit=N; no salary field"),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true", "https://jobs.ashbyhq.com/{slug}", "No", "Slug may be case-sensitive; large boards can be several MB"),
    ("workable", "https://apply.workable.com/api/v1/widget/accounts/{slug}", "https://apply.workable.com/{slug}", "No", "Add ?details=true for descriptions"),
    ("smartrecruiters", "https://api.smartrecruiters.com/v1/companies/{slug}/postings", "https://jobs.smartrecruiters.com/{slug}", "No", "Paginate with limit/offset; descriptions need a second call per job"),
    ("custom", "Endpoint found via browser DevTools (Network → Fetch/XHR)", "Company careers page", "Varies", "Unofficial; may change without notice"),
    ("unsupported", "—", "—", "—", "Workday, iCIMS, own systems etc. Needs a different approach"),
]


def api_formula(r: int) -> str:
    return (f'=IF(B{r}="greenhouse","https://boards-api.greenhouse.io/v1/boards/"&C{r}&"/jobs?content=true",'
            f'IF(B{r}="lever","https://api.lever.co/v0/postings/"&C{r}&"?mode=json",'
            f'IF(B{r}="ashby","https://api.ashbyhq.com/posting-api/job-board/"&C{r}&"?includeCompensation=true",'
            f'IF(B{r}="workable","https://apply.workable.com/api/v1/widget/accounts/"&C{r},'
            f'IF(B{r}="smartrecruiters","https://api.smartrecruiters.com/v1/companies/"&C{r}&"/postings",'
            f'IF(B{r}="custom",I{r},""))))))')


def board_formula(r: int) -> str:
    return (f'=IF(B{r}="greenhouse","https://job-boards.greenhouse.io/"&C{r},'
            f'IF(B{r}="lever","https://jobs.lever.co/"&C{r},'
            f'IF(B{r}="ashby","https://jobs.ashbyhq.com/"&C{r},'
            f'IF(B{r}="workable","https://apply.workable.com/"&C{r},'
            f'IF(B{r}="smartrecruiters","https://jobs.smartrecruiters.com/"&C{r},"")))))')


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

    cs = wb.create_sheet("Companies")
    headers = ["company_name", "ats_type", "slug", "api_url", "board_url", "verification", "notes", "enabled", "endpoint"]
    for col, h in enumerate(headers, start=1):
        c = cs.cell(row=1, column=col, value=h)
        c.font = bold
        c.fill = head_fill
    for r, (name, ats, slug, ver, notes) in enumerate(COMPANIES, start=2):
        cs.cell(row=r, column=1, value=name).font = blue
        cs.cell(row=r, column=2, value=ats).font = blue
        cs.cell(row=r, column=3, value=slug).font = blue
        cs.cell(row=r, column=4, value=api_formula(r))
        cs.cell(row=r, column=5, value=board_formula(r))
        cs.cell(row=r, column=6, value=ver)
        cs.cell(row=r, column=7, value=notes)
        cs.cell(row=r, column=8, value=True).font = blue
        cs.cell(row=r, column=9).font = blue
    widths = [18, 16, 16, 70, 44, 46, 38, 9, 40]
    for i, w in enumerate(widths):
        cs.column_dimensions[chr(65 + i)].width = w
    cs.freeze_panes = "A2"
    dv = DataValidation(type="list", formula1='"greenhouse,lever,ashby,workable,smartrecruiters,custom,unsupported"',
                        allow_blank=False)
    cs.add_data_validation(dv)
    dv.add("B2:B1000")
    dv2 = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True)
    cs.add_data_validation(dv2)
    dv2.add("H2:H1000")

    es = wb.create_sheet("ATS Endpoints")
    for col, h in enumerate(["ats_type", "API endpoint (replace {slug})", "Hosted board URL", "Key needed", "Notes"], start=1):
        c = es.cell(row=1, column=col, value=h)
        c.font = bold
        c.fill = head_fill
    for r, row in enumerate(ENDPOINTS, start=2):
        for col, v in enumerate(row, start=1):
            es.cell(row=r, column=col, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    for i, w in enumerate([16, 70, 42, 11, 60]):
        es.column_dimensions[chr(65 + i)].width = w

    wb.active = 1
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


if __name__ == "__main__":
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT} already exists; use --force to rebuild it (your edits would be lost).")
        sys.exit(1)
    build(OUT)
    print(f"Wrote {OUT} with {len(COMPANIES)} companies")
