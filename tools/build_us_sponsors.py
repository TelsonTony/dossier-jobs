"""Builds data/sponsors_us.txt from a downloaded DOL LCA disclosure file or USCIS H-1B
Employer Data Hub export (xlsx or csv). [Verify] the current file format and download page:
  * DOL: https://www.dol.gov/agencies/eta/foreign-labor/performance  (LCA Programs, H-1B)
  * USCIS: https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub

    python tools/build_us_sponsors.py LCA_Disclosure_Data_FY2026_Q3.xlsx
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "sponsors_us.txt"
NAME_COLUMNS = ("EMPLOYER_NAME", "Employer (Petitioner) Name", "Employer", "EMPLOYER_BUSINESS_NAME")
STATUS_COLUMNS = ("CASE_STATUS",)


def rows(path: Path):
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
            yield from csv.DictReader(f)
        return
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    header = [str(h or "") for h in next(it)]
    for r in it:
        yield dict(zip(header, r))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    names: set[str] = set()
    for row in rows(Path(sys.argv[1])):
        status = next((row.get(c) for c in STATUS_COLUMNS if c in row), "Certified")
        if status and "certified" not in str(status).lower():
            continue
        name = next((row.get(c) for c in NAME_COLUMNS if row.get(c)), None)
        if name:
            names.add(" ".join(str(name).split()))
    header = OUT.read_text(encoding="utf-8").splitlines() if OUT.exists() else []
    header = [h for h in header if h.startswith("#")]
    OUT.write_text("\n".join(header + sorted(names)) + "\n", encoding="utf-8")
    print(f"Wrote {len(names)} employer names to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
