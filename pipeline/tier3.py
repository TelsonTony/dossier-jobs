"""Reads the Tier3 sheet of data/APIKey_Based_Search.xlsx (on/off per Tier 3 job site).

Tier 3 sites (Adzuna, Jooble, Careerjet, Reed, USAJOBS, Findwork) run only on manual workflow
runs; this sheet decides which of them run then. Columns are found by header name. Only
`provider_id` and `enabled` are read; the other columns are notes for people.
API keys never go in this file; they stay in GitHub Actions secrets / GitLab CI variables.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .companies import _truthy

TIER3_WORKBOOK = Path(__file__).resolve().parent.parent / "data" / "APIKey_Based_Search.xlsx"
SHEET = "Tier3"


def load_tier3(provider_ids: list[str], path: Path = TIER3_WORKBOOK) -> tuple[dict[str, bool], list[str]]:
    """Returns ({provider_id: enabled}, warnings) for the given Tier 3 providers.

    A provider with no row, or a missing workbook, is treated as switched off, so nothing
    runs that the sheet does not ask for.
    """
    enabled = {p: False for p in provider_ids}
    warnings: list[str] = []
    if not path.exists():
        return enabled, [f"{path.name} not found; all Tier 3 sites are off"]
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if SHEET not in wb.sheetnames:
            return enabled, [f"{path.name} has no '{SHEET}' sheet; all Tier 3 sites are off"]
        rows = wb[SHEET].iter_rows(values_only=True)
        header = [str(h or "").strip().lower() for h in next(rows, ())]
        col = {name: i for i, name in enumerate(header) if name}
        for required in ("provider_id", "enabled"):
            if required not in col:
                return enabled, [f"{SHEET} sheet is missing the '{required}' column; all Tier 3 sites are off"]
        seen: set[str] = set()
        for idx, row in enumerate(rows, start=2):
            pid = str(row[col["provider_id"]] or "").strip().lower() if col["provider_id"] < len(row) else ""
            if not pid:
                continue
            if pid not in enabled:
                warnings.append(f"Row {idx}: unknown provider_id '{pid}', skipped")
                continue
            if pid in seen:
                warnings.append(f"Row {idx}: duplicate provider_id '{pid}', skipped")
                continue
            seen.add(pid)
            value = row[col["enabled"]] if col["enabled"] < len(row) else None
            # Unlike the company list, an empty cell means OFF here: a paid/keyed site runs only when asked.
            enabled[pid] = value is not None and str(value).strip() != "" and _truthy(value)
        for pid in provider_ids:
            if pid not in seen:
                warnings.append(f"No row for '{pid}'; it stays off")
    finally:
        wb.close()
    return enabled, warnings
