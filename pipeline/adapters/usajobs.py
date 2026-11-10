"""USAJOBS search API (US federal). Headers: Authorization-Key + User-Agent (your email).
Secrets: USAJOBS_API_KEY, USAJOBS_EMAIL. Docs: https://developer.usajobs.gov/
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse, MissingKey
from ..normalize import make_job, salary_text
from . import FetchContext

URL = "https://data.usajobs.gov/api/search"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    key, email = ctx.keys.get("USAJOBS_API_KEY"), ctx.keys.get("USAJOBS_EMAIL")
    if not key or not email:
        raise MissingKey()
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}
    jobs: list[dict[str, Any]] = []
    for keyword in ctx.config.get("tier3_keywords") or [""]:
        for page in range(1, ctx.page_cap + 1):
            params: dict[str, Any] = {"ResultsPerPage": 250, "Page": page}
            if keyword:
                params["Keyword"] = keyword
            data = http.get(URL, params=params, headers=headers, budget=ctx.budget)
            batch = parse(data)
            jobs.extend(batch)
            if len(batch) < 250:
                break
    return jobs


def parse(data: Any) -> list[dict[str, Any]]:
    items = (((data or {}).get("SearchResult") or {}).get("SearchResultItems")) if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise InvalidResponse("Expected SearchResult.SearchResultItems")
    jobs = []
    for wrap in items:
        d = (wrap or {}).get("MatchedObjectDescriptor") or {}
        pay = (d.get("PositionRemuneration") or [{}])[0] or {}
        summary = (((d.get("UserArea") or {}).get("Details") or {}).get("JobSummary")) or d.get("QualificationSummary")
        apply = (d.get("ApplyURI") or [None])[0]
        location = d.get("PositionLocationDisplay")
        job = make_job(
            provider="usajobs",
            tier=3,
            provider_job_id=d.get("PositionID") or wrap.get("MatchedObjectId"),
            title=d.get("PositionTitle"),
            company=d.get("OrganizationName") or d.get("DepartmentName"),
            location=location,
            country="US",
            description_text=summary,
            salary=salary_text(pay.get("MinimumRange"), pay.get("MaximumRange"), "USD", pay.get("Description")),
            published_at=d.get("PublicationStartDate"),
            apply_url=apply or d.get("PositionURI"),
            source_url=d.get("PositionURI"),
            source_name="USAJOBS",
        )
        if job:
            jobs.append(job)
    return jobs
