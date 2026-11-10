"""SmartRecruiters posting API. Paginated with limit/offset; the description needs a second
call per posting, so detail calls are capped per company (config: smartrecruiters_detail_cap).
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse, SourceError
from ..normalize import make_job
from . import Company, FetchContext

BASE = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE = 100


def build_url(slug: str) -> str:
    return BASE.format(slug=slug)


def fetch_company(company: Company, ctx: FetchContext) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    offset = 0
    for _ in range(max(1, ctx.page_cap)):
        data = http.get(BASE.format(slug=company.slug), params={"limit": PAGE, "offset": offset}, budget=ctx.budget)
        if not isinstance(data, dict) or not isinstance(data.get("content"), list):
            raise InvalidResponse("Expected an object with a 'content' list")
        items.extend(x for x in data["content"] if isinstance(x, dict))
        offset += PAGE
        if offset >= int(data.get("totalFound") or 0):
            break
    cap = int(ctx.config.get("smartrecruiters_detail_cap", 150))
    details: dict[str, str] = {}
    for item in items[:cap]:
        try:
            d = http.get(f"{BASE.format(slug=company.slug)}/{item.get('id')}", budget=ctx.budget, retries=0)
            sections = ((d or {}).get("jobAd") or {}).get("sections") or {}
            details[str(item.get("id"))] = "\n\n".join(
                str((sections.get(k) or {}).get("text") or "")
                for k in ("companyDescription", "jobDescription", "qualifications", "additionalInformation")
            )
        except SourceError:
            continue  # job still listed, description simply missing
    return parse({"content": items}, company, details)


def parse(data: dict[str, Any], company: Company, details: dict[str, str] | None = None) -> list[dict[str, Any]]:
    details = details or {}
    jobs = []
    for item in data.get("content") or []:
        loc = item.get("location") or {}
        location = ", ".join(str(x) for x in [loc.get("city"), loc.get("region"), loc.get("country")] if x) or None
        arrangement = "remote" if loc.get("remote") else ("hybrid" if loc.get("hybrid") else None)
        pid = item.get("id")
        url = f"https://jobs.smartrecruiters.com/{company.slug}/{pid}"
        job = make_job(
            provider="smartrecruiters",
            tier=1,
            provider_job_id=f"{company.slug}-{pid}",
            title=item.get("name"),
            company=(item.get("company") or {}).get("name") or company.company_name,
            location=location,
            country=loc.get("country"),
            work_arrangement=arrangement,
            description_html=details.get(str(pid), ""),
            published_at=item.get("releasedDate"),
            apply_url=url,
            source_url=url,
            source_name="SmartRecruiters",
            board=company.slug,
        )
        if job:
            jobs.append(job)
    return jobs
