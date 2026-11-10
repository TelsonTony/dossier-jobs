"""Workable widget API. details=true adds descriptions. [Verify] field names on first run."""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job
from . import Company, FetchContext

URL = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


def build_url(slug: str) -> str:
    return URL.format(slug=slug)


def fetch_company(company: Company, ctx: FetchContext) -> list[dict[str, Any]]:
    data = http.get(URL.format(slug=company.slug), params={"details": "true"}, budget=ctx.budget)
    return parse(data, company)


def parse(data: Any, company: Company) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise InvalidResponse("Expected an object with a 'jobs' list")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        locs = item.get("locations") or []
        first = locs[0] if locs and isinstance(locs[0], dict) else {}
        location = ", ".join(
            str(x) for x in [item.get("city") or first.get("city"), item.get("state") or first.get("region"),
                             item.get("country") or first.get("country")] if x
        ) or None
        arrangement = None
        if item.get("telecommuting") is True or item.get("remote") is True:
            arrangement = "remote"
        workplace = str(item.get("workplace") or "").lower()
        if workplace in ("remote", "hybrid", "on_site", "onsite"):
            arrangement = "onsite" if "site" in workplace else workplace
        url = item.get("url") or item.get("shortlink")
        job = make_job(
            provider="workable",
            tier=1,
            provider_job_id=f"{company.slug}-{item.get('shortcode') or item.get('code') or item.get('id')}",
            title=item.get("title"),
            company=data.get("name") or company.company_name,
            location=location,
            country=first.get("countryCode"),
            work_arrangement=arrangement,
            description_html=item.get("description"),
            published_at=item.get("published_on") or item.get("created_at"),
            apply_url=item.get("application_url") or url,
            source_url=url,
            source_name="Workable",
            board=company.slug,
        )
        if job:
            jobs.append(job)
    return jobs
