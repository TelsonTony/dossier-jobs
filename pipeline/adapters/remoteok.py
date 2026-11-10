"""RemoteOK API. The first array item is a legal notice and is skipped.
Attribution and a link back to RemoteOK are required: source_url points at the RemoteOK listing.
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job, salary_text
from . import FetchContext

URL = "https://remoteok.com/api"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    data = http.get(URL, budget=ctx.budget, retries=1)
    return parse(data)


def parse(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise InvalidResponse("Expected a list")
    jobs = []
    for item in data:
        if not isinstance(item, dict) or "legal" in item or not item.get("id"):
            continue
        listing = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id')}"
        job = make_job(
            provider="remoteok",
            tier=2,
            provider_job_id=item.get("id"),
            title=item.get("position"),
            company=item.get("company"),
            location=item.get("location") or None,
            work_arrangement="remote",
            remote_scope=item.get("location") or "",
            description_html=item.get("description"),
            salary=salary_text(item.get("salary_min"), item.get("salary_max"), "USD", "year"),
            published_at=item.get("epoch") or item.get("date"),
            apply_url=item.get("apply_url") or listing,
            source_url=listing,
            source_name="RemoteOK",
        )
        if job:
            jobs.append(job)
    return jobs
