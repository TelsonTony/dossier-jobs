"""We Work Remotely RSS feed. Item titles look like "Company: Job title"."""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Any

from .. import http
from ..http import InvalidResponse
from ..normalize import make_job
from . import FetchContext

URL = "https://weworkremotely.com/remote-jobs.rss"


def fetch(ctx: FetchContext) -> list[dict[str, Any]]:
    text = http.get(URL, budget=ctx.budget, expect="text")
    return parse(text)


def parse(text: str) -> list[dict[str, Any]]:
    if "<!DOCTYPE" in text[:500] or "<!ENTITY" in text:
        raise InvalidResponse("Refusing XML with DTD/entities")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise InvalidResponse("Invalid RSS") from None
    jobs = []
    for item in root.iter("item"):
        raw_title = (item.findtext("title") or "").strip()
        company, _, title = raw_title.partition(":")
        if not title:
            company, title = "", raw_title
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        region = item.findtext("region") or ""
        job = make_job(
            provider="weworkremotely",
            tier=2,
            provider_job_id=hashlib.sha1(guid.encode()).hexdigest()[:16],
            title=title.strip(),
            company=company.strip() or "Unknown company",
            location=region or None,
            work_arrangement="remote",
            remote_scope=region or "",
            description_html=item.findtext("description"),
            published_at=item.findtext("pubDate"),
            apply_url=link,
            source_url=link,
            source_name="We Work Remotely",
        )
        if job:
            jobs.append(job)
    return jobs
