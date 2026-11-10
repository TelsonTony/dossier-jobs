"""Arbeitnow job board API (Europe/UK/remote). Only `page` filters server-side [Verify]."""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job
from . import FetchContext

URL = "https://www.arbeitnow.com/api/job-board-api"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for page in range(1, ctx.page_cap + 1):
        data = http.get(URL, params={"page": page}, budget=ctx.budget, polite_delay=1.0)
        batch = parse(data)
        jobs.extend(batch)
        if not batch or not ((data.get("links") or {}).get("next")):
            break
    return jobs


def parse(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise InvalidResponse("Expected an object with a 'data' list")
    jobs = []
    for item in data["data"]:
        if not isinstance(item, dict):
            continue
        job = make_job(
            provider="arbeitnow",
            tier=2,
            provider_job_id=item.get("slug"),
            title=item.get("title"),
            company=item.get("company_name"),
            location=item.get("location"),
            work_arrangement="remote" if item.get("remote") is True else None,
            description_html=item.get("description"),
            published_at=item.get("created_at"),
            apply_url=item.get("url"),
            source_url=item.get("url"),
            source_name="Arbeitnow",
        )
        if job:
            jobs.append(job)
    return jobs
