"""Jobicy remote jobs API v2. Remote only."""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job, salary_text
from . import FetchContext

URL = "https://jobicy.com/api/v2/remote-jobs"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    data = http.get(URL, params={"count": 100}, budget=ctx.budget)
    return parse(data)


def parse(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise InvalidResponse("Expected an object with a 'jobs' list")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        level = str(item.get("jobLevel") or "")
        job = make_job(
            provider="jobicy",
            tier=2,
            provider_job_id=item.get("id"),
            title=item.get("jobTitle"),
            company=item.get("companyName"),
            location=item.get("jobGeo"),
            work_arrangement="remote",
            remote_scope=item.get("jobGeo"),
            description_html=item.get("jobDescription") or item.get("jobExcerpt"),
            salary=salary_text(item.get("annualSalaryMin"), item.get("annualSalaryMax"),
                               item.get("salaryCurrency"), "year"),
            published_at=item.get("pubDate"),
            apply_url=item.get("url"),
            source_url=item.get("url"),
            source_name="Jobicy",
        )
        if job:
            if level and job["experience_hint"] == "unknown":
                low = level.lower()
                job["experience_hint"] = "senior" if "senior" in low else ("entry" if ("junior" in low or "entry" in low) else ("mid" if "mid" in low else "unknown"))
            jobs.append(job)
    return jobs
