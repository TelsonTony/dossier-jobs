"""Lever postings API. Response is a list. EU boards live on api.eu.lever.co, so a 404 on the
global host is retried once on the EU host before the board is reported as not found.
Docs: https://github.com/lever/postings-api
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import BoardNotFound, InvalidResponse
from ..normalize import make_job
from . import Company, FetchContext

HOSTS = ["https://api.lever.co", "https://api.eu.lever.co"]


def build_url(slug: str, eu: bool = False) -> str:
    return f"{HOSTS[1 if eu else 0]}/v0/postings/{slug}?mode=json"


def fetch_company(company: Company, ctx: FetchContext) -> list[dict[str, Any]]:
    hosts = HOSTS[::-1] if "eu.lever" in (company.notes or "") else HOSTS
    last: Exception | None = None
    for host in hosts:
        try:
            data = http.get(f"{host}/v0/postings/{company.slug}", params={"mode": "json"}, budget=ctx.budget)
            return parse(data, company)
        except BoardNotFound as exc:
            last = exc
    raise last or BoardNotFound()


def parse(data: Any, company: Company) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise InvalidResponse("Expected a list of postings")
    jobs = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cats = item.get("categories") or {}
        parts = [item.get("descriptionPlain") or ""]
        for block in item.get("lists") or []:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
                parts.append(str(block.get("content") or ""))
        parts.append(item.get("additionalPlain") or "")
        description_html = "\n".join(p for p in parts if p)
        sal = item.get("salaryRange") or {}
        salary = None
        if isinstance(sal, dict) and (sal.get("min") or sal.get("max")):
            from ..normalize import salary_text

            salary = salary_text(sal.get("min"), sal.get("max"), sal.get("currency"), sal.get("interval"))
        job = make_job(
            provider="lever",
            tier=1,
            provider_job_id=f"{company.slug}-{item.get('id')}",
            title=item.get("text"),
            company=company.company_name,
            location=cats.get("location") or ", ".join(cats.get("allLocations") or []) or None,
            country=item.get("country"),
            work_arrangement=_arrangement(item.get("workplaceType")),
            description_html=description_html,
            salary=salary,
            published_at=item.get("createdAt"),
            apply_url=item.get("applyUrl") or item.get("hostedUrl"),
            source_url=item.get("hostedUrl"),
            source_name="Lever",
            board=company.slug,
        )
        if job:
            jobs.append(job)
    return jobs


def _arrangement(value: Any) -> str | None:
    v = str(value or "").lower()
    return {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite", "on-site": "onsite"}.get(v)
