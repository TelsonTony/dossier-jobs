"""Findwork.dev API (developer roles). Header: Authorization: Token KEY. Secret: FINDWORK_API_KEY."""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse, MissingKey
from ..normalize import make_job
from . import FetchContext

URL = "https://findwork.dev/api/jobs/"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    key = ctx.keys.get("FINDWORK_API_KEY")
    if not key:
        raise MissingKey()
    headers = {"Authorization": f"Token {key}"}
    jobs: list[dict[str, Any]] = []
    for page in range(1, ctx.page_cap + 1):
        data = http.get(URL, params={"page": page, "sort_by": "date"}, headers=headers, budget=ctx.budget)
        batch = parse(data)
        jobs.extend(batch)
        if not data.get("next"):
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
            provider="findwork",
            tier=3,
            provider_job_id=item.get("id"),
            title=item.get("role"),
            company=item.get("company_name"),
            location=item.get("location"),
            work_arrangement="remote" if item.get("remote") is True else None,
            description_html=item.get("text"),
            published_at=item.get("date_posted"),
            apply_url=item.get("url"),
            source_url=item.get("url"),
            source_name="Findwork",
            extra_skills=[],
        )
        if job:
            jobs.append(job)
    return jobs
