"""Reads the Companies sheet of data/Dossier_ATS_Company_List.xlsx.

Columns are found by header name, so they can be reordered. The URL is always built in
code from ats_type + slug (the api_url column is a formula kept for people to check;
formula values may not be saved in the file).
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .adapters import Company

KNOWN_TYPES = {"greenhouse", "lever", "ashby", "workable", "smartrecruiters", "custom", "unsupported"}
WORKBOOK = Path(__file__).resolve().parent.parent / "data" / "Dossier_ATS_Company_List.xlsx"


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True  # an empty cell does not pause a company
    return str(value).strip().lower() not in ("false", "0", "no", "n", "off", "paused")


def load_companies(path: Path = WORKBOOK) -> tuple[list[Company], list[str]]:
    """Returns (companies, warnings). Rows with an unknown ats_type are reported, not fetched."""
    wb = load_workbook(path, read_only=True, data_only=False)
    if "Companies" not in wb.sheetnames:
        raise ValueError("Workbook has no 'Companies' sheet")
    ws = wb["Companies"]
    rows = ws.iter_rows(values_only=True)
    header = [str(h or "").strip().lower() for h in next(rows)]
    col = {name: i for i, name in enumerate(header) if name}
    for required in ("company_name", "ats_type", "slug"):
        if required not in col:
            raise ValueError(f"Companies sheet is missing the '{required}' column")
    companies: list[Company] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for idx, row in enumerate(rows, start=2):
        def cell(name: str) -> object:
            i = col.get(name)
            return row[i] if i is not None and i < len(row) else None

        name = str(cell("company_name") or "").strip()
        ats = str(cell("ats_type") or "").strip().lower()
        slug = str(cell("slug") or "").strip()
        if not name and not slug:
            continue
        if ats not in KNOWN_TYPES:
            warnings.append(f"Row {idx} ({name}): unknown ats_type '{ats}', skipped")
            continue
        if ats != "unsupported" and not slug:
            warnings.append(f"Row {idx} ({name}): missing slug, skipped")
            continue
        if (ats, slug.lower()) in seen:
            warnings.append(f"Row {idx} ({name}): duplicate {ats}/{slug}, skipped")
            continue
        seen.add((ats, slug.lower()))
        endpoint = cell("endpoint")
        companies.append(Company(
            company_name=name or slug,
            ats_type=ats,
            slug=slug,
            enabled=_truthy(cell("enabled")),
            endpoint=str(endpoint).strip() if endpoint else None,
            notes=str(cell("notes") or ""),
            verification=str(cell("verification") or ""),
            row=idx,
        ))
    wb.close()
    return companies, warnings
