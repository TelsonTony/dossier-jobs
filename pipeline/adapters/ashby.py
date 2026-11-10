"""Ashby public job posting API. Slug may be case-sensitive; large boards are several MB.
Docs: https://developers.ashbyhq.com/docs/public-job-posting-api
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job
from . import Company, FetchContext

URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def build_url(slug: str) -> str:
    return URL.format(slug=slug) + "?includeCompensation=true"


def fetch_company(company: Company, ctx: FetchContext) -> list[dict[str, Any]]:
    data = http.get(URL.format(slug=company.slug), params={"includeCompensation": "true"}, budget=ctx.budget)
    return parse(data, company)


def parse(data: Any, company: Company) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise InvalidResponse("Expected an object with a 'jobs' list")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict) or item.get("isListed") is False:
            continue
        locations = [item.get("location")] + [
            (s or {}).get("location") for s in (item.get("secondaryLocations") or []) if isinstance(s, dict)
        ]
        location = ", ".join(str(x) for x in locations if x) or None
        address = ((item.get("address") or {}).get("postalAddress") or {})
        workplace = str(item.get("workplaceType") or "").lower()
        arrangement = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}.get(workplace)
        if not arrangement and item.get("isRemote") is True:
            arrangement = "remote"
        comp = item.get("compensation") or {}
        salary = comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary")
        job = make_job(
            provider="ashby",
            tier=1,
            provider_job_id=f"{company.slug}-{item.get('id')}",
            title=item.get("title"),
            company=company.company_name,
            location=location,
            country=address.get("addressCountry"),
            work_arrangement=arrangement,
            description_text=item.get("descriptionPlain"),
            description_html=item.get("descriptionHtml"),
            salary=salary,
            published_at=item.get("publishedAt"),
            apply_url=item.get("applyUrl") or item.get("jobUrl"),
            source_url=item.get("jobUrl"),
            source_name="Ashby",
            board=company.slug,
        )
        if job:
            jobs.append(job)
    return jobs
