"""Careerjet API. Key in basic auth; requires user_ip and user_agent. Secret: CAREERJET_API_KEY.
[Verify] the current endpoint and parameters in your Careerjet publisher account before enabling;
the endpoint can be overridden with config "careerjet_endpoint".
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import USER_AGENT, InvalidResponse, MissingKey
from ..normalize import make_job
from . import FetchContext

DEFAULT_ENDPOINT = "https://search.api.careerjet.net/v4/query"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    key = ctx.keys.get("CAREERJET_API_KEY")
    if not key:
        raise MissingKey()
    endpoint = ctx.config.get("careerjet_endpoint") or DEFAULT_ENDPOINT
    jobs: list[dict[str, Any]] = []
    for locale in ctx.config.get("careerjet_locales") or ["en_GB"]:
        for keywords in ctx.config.get("tier3_keywords") or [""]:
            for page in range(1, ctx.page_cap + 1):
                params = {"locale_code": locale, "keywords": keywords, "page": page, "pagesize": 50,
                          "user_ip": "1.1.1.1", "user_agent": USER_AGENT, "sort": "date"}
                data = http.get(endpoint, params=params, auth=(key, ""), budget=ctx.budget)
                batch = parse(data)
                jobs.extend(batch)
                if len(batch) < 50:
                    break
    return jobs


def parse(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise InvalidResponse("Expected an object with a 'jobs' list")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        job = make_job(
            provider="careerjet",
            tier=3,
            provider_job_id=item.get("id") or url,
            title=item.get("title"),
            company=item.get("company") or "Unknown company",
            location=item.get("locations"),
            description_html=item.get("description"),
            salary=item.get("salary") or None,
            published_at=item.get("date"),
            apply_url=url,
            source_url=url,
            source_name="Careerjet",
        )
        if job:
            jobs.append(job)
    return jobs
