"""Greenhouse job board API. All jobs in one call; content=true includes descriptions.
Docs: https://developers.greenhouse.io/job-board.html
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job
from . import Company, FetchContext

URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def build_url(slug: str) -> str:
    return URL.format(slug=slug) + "?content=true"


def fetch_company(company: Company, ctx: FetchContext) -> list[dict[str, Any]]:
    data = http.get(URL.format(slug=company.slug), params={"content": "true"}, budget=ctx.budget)
    return parse(data, company)


def parse(data: Any, company: Company) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise InvalidResponse("Expected an object with a 'jobs' list")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        location = (item.get("location") or {}).get("name")
        workplace = None
        for meta in item.get("metadata") or []:
            if isinstance(meta, dict) and "workplace" in str(meta.get("name", "")).lower():
                workplace = str(meta.get("value") or "")
        job = make_job(
            provider="greenhouse",
            tier=1,
            provider_job_id=f"{company.slug}-{item.get('id')}",
            title=item.get("title"),
            company=item.get("company_name") or company.company_name,
            location=location,
            work_arrangement=_arrangement(workplace),
            description_html=item.get("content"),
            published_at=item.get("first_published") or item.get("updated_at"),
            apply_url=item.get("absolute_url"),
            source_url=item.get("absolute_url"),
            source_name="Greenhouse",
            board=company.slug,
        )
        if job:
            jobs.append(job)
    return jobs


def _arrangement(value: str | None) -> str | None:
    if not value:
        return None
    v = value.lower()
    if "hybrid" in v:
        return "hybrid"
    if "remote" in v:
        return "remote"
    if "office" in v or "site" in v:
        return "onsite"
    return None
