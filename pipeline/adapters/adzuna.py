"""Adzuna search API. app_id + app_key in the URL; country code in the path.
Secrets: ADZUNA_APP_ID, ADZUNA_APP_KEY. Countries: config "adzuna_countries".
Docs: https://developer.adzuna.com/  [Verify] limits and redistribution terms (Section 14).
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse, MissingKey, SourceError
from ..normalize import make_job, salary_text
from . import FetchContext

URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    app_id, app_key = ctx.keys.get("ADZUNA_APP_ID"), ctx.keys.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise MissingKey()
    jobs: list[dict[str, Any]] = []
    errors: list[SourceError] = []
    keywords = ctx.config.get("tier3_keywords") or [""]
    for country in ctx.config.get("adzuna_countries", ["gb"]):
        for what in keywords:
            for page in range(1, ctx.page_cap + 1):
                params = {"app_id": app_id, "app_key": app_key, "results_per_page": 50,
                          "max_days_old": 30, "content-type": "application/json"}
                if what:
                    params["what"] = what
                try:
                    data = http.get(URL.format(country=country.lower(), page=page), params=params, budget=ctx.budget)
                except SourceError as exc:
                    if exc.status in ("Invalid key", "Quota exhausted", "Rate limited"):
                        raise
                    errors.append(exc)
                    break
                batch = parse(data, country)
                jobs.extend(batch)
                if len(batch) < 50:
                    break
    if not jobs and errors:
        raise errors[0]
    return jobs


def parse(data: Any, country: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise InvalidResponse("Expected an object with a 'results' list")
    jobs = []
    for item in data["results"]:
        if not isinstance(item, dict):
            continue
        job = make_job(
            provider="adzuna",
            tier=3,
            provider_job_id=item.get("id"),
            title=item.get("title"),
            company=(item.get("company") or {}).get("display_name"),
            location=(item.get("location") or {}).get("display_name"),
            country=country.upper().replace("UK", "GB"),
            description_html=item.get("description"),
            salary=salary_text(item.get("salary_min"), item.get("salary_max")),
            published_at=item.get("created"),
            apply_url=item.get("redirect_url"),
            source_url=item.get("redirect_url"),
            source_name="Adzuna",
        )
        if job:
            jobs.append(job)
    return jobs
