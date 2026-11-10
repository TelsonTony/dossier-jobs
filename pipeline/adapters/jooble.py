"""Jooble API: POST JSON to https://jooble.org/api/<key>. Secret: JOOBLE_API_KEY.
Jooble needs keywords, so it uses config "tier3_keywords" and "jooble_locations". [Verify]
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse, MissingKey
from ..normalize import make_job
from . import FetchContext


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    key = ctx.keys.get("JOOBLE_API_KEY")
    if not key:
        raise MissingKey()
    jobs: list[dict[str, Any]] = []
    for keywords in ctx.config.get("tier3_keywords") or ["software"]:
        for location in ctx.config.get("jooble_locations") or [""]:
            for page in range(1, ctx.page_cap + 1):
                body = {"keywords": keywords or "", "location": location, "page": str(page)}
                data = http.post(f"https://jooble.org/api/{key}", json_body=body, budget=ctx.budget)
                batch = parse(data)
                jobs.extend(batch)
                if len(batch) < 20:
                    break
    return jobs


def parse(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise InvalidResponse("Expected an object with a 'jobs' list")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        job = make_job(
            provider="jooble",
            tier=3,
            provider_job_id=item.get("id"),
            title=item.get("title"),
            company=item.get("company") or "Unknown company",
            location=item.get("location"),
            description_html=item.get("snippet"),
            salary=item.get("salary") or None,
            published_at=item.get("updated"),
            apply_url=item.get("link"),
            source_url=item.get("link"),
            source_name="Jooble",
        )
        if job:
            jobs.append(job)
    return jobs
