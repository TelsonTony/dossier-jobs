"""The Muse public jobs API. Only source with an experience-level field. An optional key
(secret THEMUSE_API_KEY) may raise limits [Verify]. Attribution and link-back required.
"""
from __future__ import annotations

from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job
from . import FetchContext

URL = "https://www.themuse.com/api/public/jobs"
LEVELS = {"internship": "entry", "entry level": "entry", "mid level": "mid", "senior level": "senior",
          "management": "senior"}


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    key = ctx.keys.get("THEMUSE_API_KEY")
    for page in range(1, ctx.page_cap + 1):
        params: dict[str, Any] = {"page": page}
        if key:
            params["api_key"] = key
        data = http.get(URL, params=params, budget=ctx.budget)
        batch = parse(data)
        jobs.extend(batch)
        if not batch or page >= int(data.get("page_count") or 0):
            break
    return jobs


def parse(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise InvalidResponse("Expected an object with a 'results' list")
    jobs = []
    for item in data["results"]:
        if not isinstance(item, dict):
            continue
        locs = [str((x or {}).get("name")) for x in item.get("locations") or [] if isinstance(x, dict)]
        location = "; ".join(locs) or None
        landing = (item.get("refs") or {}).get("landing_page")
        job = make_job(
            provider="themuse",
            tier=2,
            provider_job_id=item.get("id"),
            title=item.get("name"),
            company=(item.get("company") or {}).get("name"),
            location=location,
            remote_scope=location,
            description_html=item.get("contents"),
            published_at=item.get("publication_date"),
            apply_url=landing,
            source_url=landing,
            source_name="The Muse",
        )
        if job:
            for lv in item.get("levels") or []:
                mapped = LEVELS.get(str((lv or {}).get("name", "")).lower())
                if mapped:
                    job["experience_hint"] = mapped
                    break
            jobs.append(job)
    return jobs
