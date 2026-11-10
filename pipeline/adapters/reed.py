"""Reed (UK) jobseeker API. Key as the basic-auth username. Secret: REED_API_KEY.
Docs: https://www.reed.co.uk/developers/jobseeker
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse, MissingKey
from ..normalize import make_job, salary_text
from . import FetchContext

URL = "https://www.reed.co.uk/api/1.0/search"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    key = ctx.keys.get("REED_API_KEY")
    if not key:
        raise MissingKey()
    jobs: list[dict[str, Any]] = []
    for keywords in ctx.config.get("tier3_keywords") or [""]:
        for page in range(ctx.page_cap):
            params = {"keywords": keywords, "resultsToTake": 100, "resultsToSkip": page * 100}
            data = http.get(URL, params=params, auth=(key, ""), budget=ctx.budget)
            batch = parse(data)
            jobs.extend(batch)
            if len(batch) < 100:
                break
    return jobs


def parse(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise InvalidResponse("Expected an object with a 'results' list")
    jobs = []
    for item in data["results"]:
        if not isinstance(item, dict):
            continue
        job = make_job(
            provider="reed",
            tier=3,
            provider_job_id=item.get("jobId"),
            title=item.get("jobTitle"),
            company=item.get("employerName"),
            location=item.get("locationName"),
            country="GB",
            description_html=item.get("jobDescription"),
            salary=salary_text(item.get("minimumSalary"), item.get("maximumSalary"), item.get("currency") or "GBP"),
            published_at=item.get("date"),
            apply_url=item.get("jobUrl"),
            source_url=item.get("jobUrl"),
            source_name="Reed",
        )
        if job:
            jobs.append(job)
    return jobs
