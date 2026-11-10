"""Remotive remote jobs API. Remote only. Keep requests very low: one call per run [Verify limit].
Remotive asks for attribution and a link back to the listing; source_url carries it.
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job
from . import FetchContext

URL = "https://remotive.com/api/remote-jobs"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    limit = int(ctx.config.get("remotive_limit", 500))
    data = http.get(URL, params={"limit": limit}, budget=ctx.budget, retries=0)
    return parse(data)


def parse(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise InvalidResponse("Expected an object with a 'jobs' list")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        job = make_job(
            provider="remotive",
            tier=2,
            provider_job_id=item.get("id"),
            title=item.get("title"),
            company=item.get("company_name"),
            location=item.get("candidate_required_location"),
            work_arrangement="remote",
            remote_scope=item.get("candidate_required_location"),
            description_html=item.get("description"),
            salary=item.get("salary") or None,
            published_at=item.get("publication_date"),
            apply_url=item.get("url"),
            source_url=item.get("url"),
            source_name="Remotive",
            extra_skills=[],
        )
        if job:
            jobs.append(job)
    return jobs
