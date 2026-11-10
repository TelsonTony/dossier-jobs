"""Phase 0 check: makes ONE test call to every company row (and, with --apis, every API)
and prints a table, so "Test once" / "Sources disagree" rows can be updated in the workbook.

    python tools/test_sources.py            # company boards only
    python tools/test_sources.py --apis     # also Tier 2 APIs (and Tier 3 if keys are in env)
    python tools/test_sources.py --try-other-ats   # for 404 rows, try the other ATS types too
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import http  # noqa: E402
from pipeline.adapters import Company, FetchContext, api_adapters, ats_adapters  # noqa: E402
from pipeline.companies import load_companies  # noqa: E402
from pipeline.main import SECRET_NAMES  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apis", action="store_true")
    ap.add_argument("--try-other-ats", action="store_true")
    a = ap.parse_args()
    ctx = FetchContext(config={"smartrecruiters_detail_cap": 0}, page_cap=1)
    companies, warnings = load_companies()
    for w in warnings:
        print("workbook:", w)
    adapters = ats_adapters()
    print(f"{'company':22} {'ats':16} {'slug':16} result")
    for c in companies:
        if c.ats_type in ("unsupported",) or c.ats_type not in adapters:
            continue
        try:
            jobs = adapters[c.ats_type](c, ctx)
            result = f"OK, {len(jobs)} jobs"
        except http.SourceError as exc:
            result = exc.status
            if a.try_other_ats and isinstance(exc, http.BoardNotFound):
                for other in ("greenhouse", "lever", "ashby", "workable"):
                    if other == c.ats_type:
                        continue
                    try:
                        jobs = adapters[other](Company(c.company_name, other, c.slug), ctx)
                        result += f" — but {other}/{c.slug} works ({len(jobs)} jobs)"
                        break
                    except http.SourceError:
                        pass
        print(f"{c.company_name[:22]:22} {c.ats_type:16} {c.slug[:16]:16} {result}")
    if a.apis:
        keys = {k: os.environ[k] for k in SECRET_NAMES if os.environ.get(k)}
        actx = FetchContext(config={"tier3_keywords": ["software"], "adzuna_countries": ["gb"]}, keys=keys, page_cap=1)
        for pid, fetch in api_adapters().items():
            try:
                jobs = fetch(actx)
                result = f"OK, {len(jobs)} jobs"
            except http.SourceError as exc:
                result = exc.status
            print(f"{pid:22} {'api':16} {'':16} {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
