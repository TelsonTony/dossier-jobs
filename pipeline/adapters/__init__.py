"""Adapters. Each provider has its own module with its own request building,
pagination and parsing (Architecture v7.1 Section 5). Nothing here is shared except
the FetchContext passed in and the transport helper in pipeline.http.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..http import Budget


@dataclass
class Company:
    company_name: str
    ats_type: str
    slug: str
    enabled: bool = True
    endpoint: str | None = None
    notes: str = ""
    verification: str = ""
    row: int = 0


@dataclass
class FetchContext:
    config: dict[str, Any]
    keys: dict[str, str] = field(default_factory=dict)
    budget: Budget | None = None
    page_cap: int = 5
    log: Callable[[str], None] = print


def ats_adapters() -> dict[str, Callable[[Company, FetchContext], list[dict[str, Any]]]]:
    from . import ashby, custom, greenhouse, lever, smartrecruiters, workable

    return {
        "greenhouse": greenhouse.fetch_company,
        "lever": lever.fetch_company,
        "ashby": ashby.fetch_company,
        "workable": workable.fetch_company,
        "smartrecruiters": smartrecruiters.fetch_company,
        "custom": custom.fetch_company,
    }


def api_adapters() -> dict[str, Callable[[FetchContext], list[dict[str, Any]]]]:
    from . import (adzuna, arbeitnow, careerjet, findwork, jobicy, jooble, reed, remoteok,
                   remotive, themuse, usajobs, weworkremotely)

    return {
        "arbeitnow": arbeitnow.fetch,
        "remotive": remotive.fetch,
        "remoteok": remoteok.fetch,
        "jobicy": jobicy.fetch,
        "weworkremotely": weworkremotely.fetch,
        "themuse": themuse.fetch,
        "adzuna": adzuna.fetch,
        "jooble": jooble.fetch,
        "careerjet": careerjet.fetch,
        "reed": reed.fetch,
        "usajobs": usajobs.fetch,
        "findwork": findwork.fetch,
    }
