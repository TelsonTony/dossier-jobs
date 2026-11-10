"""Custom JSON endpoint for a company (found via browser DevTools). Unofficial; may change
without notice. The workbook row needs an `endpoint` column with an https URL.

Accepted shapes: a list of jobs, or an object with a list under jobs / results / data /
postings / content. Common field names are tried for each value.
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse, ProviderError
from ..normalize import make_job
from . import Company, FetchContext


def fetch_company(company: Company, ctx: FetchContext) -> list[dict[str, Any]]:
    if not company.endpoint or not company.endpoint.startswith("https://"):
        raise ProviderError("custom row needs an https endpoint column")
    data = http.get(company.endpoint, budget=ctx.budget)
    return parse(data, company)


def _pick(d: dict[str, Any], *names: str) -> Any:
    for n in names:
        if n in d and d[n] not in (None, ""):
            v = d[n]
            if isinstance(v, dict):
                v = v.get("name") or v.get("text") or v.get("label")
            return v
    return None


def parse(data: Any, company: Company) -> list[dict[str, Any]]:
    items = data
    if isinstance(data, dict):
        for k in ("jobs", "results", "data", "postings", "content", "positions"):
            if isinstance(data.get(k), list):
                items = data[k]
                break
    if not isinstance(items, list):
        raise InvalidResponse("No job list found in custom response")
    jobs = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = _pick(item, "url", "absolute_url", "applyUrl", "apply_url", "link", "hostedUrl")
        job = make_job(
            provider="custom",
            tier=1,
            provider_job_id=f"{company.slug}-{_pick(item, 'id', 'jobId', 'reqId', 'slug') or url}",
            title=_pick(item, "title", "name", "text", "jobTitle"),
            company=company.company_name,
            location=_pick(item, "location", "locationName", "city"),
            description_html=_pick(item, "description", "content", "descriptionHtml", "body"),
            published_at=_pick(item, "published_at", "publishedAt", "postedDate", "created_at", "date"),
            apply_url=url,
            source_url=url,
            source_name=f"{company.company_name} careers",
            board=company.slug,
        )
        if job:
            jobs.append(job)
    return jobs
