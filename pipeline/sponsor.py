"""Visa sponsorship signal (Architecture v7.1 Section 9).

* UK: Home Office Register of Licensed Sponsors (public CSV on gov.uk), refreshed monthly.
* US: names listed in data/sponsors_us.txt (build it from DOL LCA / USCIS H-1B employer
  files with tools/build_us_sponsors.py; those files are too large to fetch on every run).
* Job descriptions are scanned for sponsorship phrases; negative phrases win.

The signal never claims a role is sponsored: the app shows "Company holds a sponsor licence"
or "Sponsorship mentioned in description".
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import http
from .dedupe import normalize_company
from .http import SourceError

UK_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
US_FILE = Path(__file__).resolve().parent.parent / "data" / "sponsors_us.txt"

POSITIVE = re.compile(
    r"(visa sponsorship (is )?(available|provided|offered)|we (can|will|do) sponsor|sponsorship (is )?available|"
    r"able to sponsor|offer(s|ing)? (visa )?sponsorship|skilled worker visa sponsorship|h-?1b sponsorship (is )?available|"
    r"relocation and visa support|visa support (is )?(available|provided))", re.I)
NEGATIVE = re.compile(
    r"(not (able|in a position) to (offer |provide )?(visa )?sponsor|unable to (offer |provide )?(visa )?sponsor|"
    r"(cannot|can't|can not|do not|don't|does not|doesn't|will not|won't) (offer |provide )?(visa )?sponsor|"
    r"no (visa )?sponsorship|sponsorship (is )?not (available|provided|offered)|without (the need for )?(visa )?sponsorship|"
    r"must (already )?have (the )?right to work)", re.I)


def mentioned_in_jd(description: str | None) -> bool:
    if not description:
        return False
    if NEGATIVE.search(description):
        return False
    return bool(POSITIVE.search(description))


def refresh_uk_register(state: dict[str, Any], log=print) -> None:
    """Refresh the UK register at most once every 30 days; keep the old copy on failure."""
    uk = state.get("uk_sponsors") or {}
    fetched = uk.get("fetched_at")
    if fetched:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(fetched.replace("Z", "+00:00"))
            if age < timedelta(days=30) and uk.get("names"):
                return
        except ValueError:
            pass
    try:
        page = http.get(UK_PAGE, expect="text", retries=1)
        m = re.search(r'href="(https://assets\.publishing\.service\.gov\.uk/[^"]+\.csv)"', page)
        if not m:
            raise SourceError("CSV link not found on gov.uk page")
        text = http.get(m.group(1), expect="text", retries=1)
        reader = csv.DictReader(io.StringIO(text))
        names = sorted({normalize_company(row.get("Organisation Name") or "") for row in reader} - {""})
        if len(names) < 1000:
            raise SourceError("Register looked too small; keeping previous copy")
        state["uk_sponsors"] = {"fetched_at": datetime.now(timezone.utc).isoformat(), "names": names,
                                "source": m.group(1)}
        log(f"UK sponsor register refreshed: {len(names)} organisations")
    except SourceError as exc:
        log(f"UK sponsor register not refreshed ({exc.status}: {exc}); using previous copy")


def load_us_names() -> set[str]:
    if not US_FILE.exists():
        return set()
    out = set()
    for line in US_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(normalize_company(line))
    return out - {""}


def apply_signals(jobs: list[dict[str, Any]], state: dict[str, Any]) -> int:
    uk = set((state.get("uk_sponsors") or {}).get("names") or [])
    us = load_us_names()
    flagged = 0
    for job in jobs:
        name = normalize_company(job.get("company"))
        country = job.get("country")
        signal = "none"
        if name and ((name in uk and country in (None, "GB")) or (name in us and country in (None, "US"))):
            signal = "sponsor_register_match"
        elif mentioned_in_jd(job.get("description")):
            signal = "mentioned_in_jd"
        job["visa_sponsor_signal"] = signal
        if signal != "none":
            flagged += 1
    return flagged
