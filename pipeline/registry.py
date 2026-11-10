"""Provider registry (Architecture v7.1 Section 4.4).

`countries_supported` drives the app's country coverage badges:
  * a list of ISO codes  -> the provider covers those countries;
  * "remote_only"        -> remote jobs only;
  * "from_jobs"          -> coverage is counted from the countries of the jobs actually fetched
                            (used for ATS boards, which are global).
"""
from __future__ import annotations

from typing import Any

from .countries import EUROPE

REGISTRY: list[dict[str, Any]] = [
    # Tier 1 — company ATS boards
    {"provider_id": "greenhouse", "name": "Greenhouse", "tier": 1, "auth_type": "none",
     "countries_supported": "from_jobs", "has_published_date": True, "attribution_required": False},
    {"provider_id": "lever", "name": "Lever", "tier": 1, "auth_type": "none",
     "countries_supported": "from_jobs", "has_published_date": True, "attribution_required": False},
    {"provider_id": "ashby", "name": "Ashby", "tier": 1, "auth_type": "none",
     "countries_supported": "from_jobs", "has_published_date": True, "attribution_required": False},
    {"provider_id": "workable", "name": "Workable", "tier": 1, "auth_type": "none",
     "countries_supported": "from_jobs", "has_published_date": True, "attribution_required": False},
    {"provider_id": "smartrecruiters", "name": "SmartRecruiters", "tier": 1, "auth_type": "none",
     "countries_supported": "from_jobs", "has_published_date": True, "attribution_required": False},
    {"provider_id": "custom", "name": "Custom careers pages", "tier": 1, "auth_type": "none",
     "countries_supported": "from_jobs", "has_published_date": False, "attribution_required": False},
    # Tier 2 — no-key public APIs
    {"provider_id": "arbeitnow", "name": "Arbeitnow", "tier": 2, "auth_type": "none",
     "countries_supported": EUROPE, "has_published_date": True, "attribution_required": False,
     "daily_quota": 40},
    {"provider_id": "remotive", "name": "Remotive", "tier": 2, "auth_type": "none",
     "countries_supported": "remote_only", "has_published_date": True, "attribution_required": True,
     "attribution_text": "Jobs from Remotive", "daily_quota": 4},
    {"provider_id": "remoteok", "name": "RemoteOK", "tier": 2, "auth_type": "none",
     "countries_supported": "remote_only", "has_published_date": True, "attribution_required": True,
     "attribution_text": "Jobs from Remote OK", "daily_quota": 4},
    {"provider_id": "jobicy", "name": "Jobicy", "tier": 2, "auth_type": "none",
     "countries_supported": "remote_only", "has_published_date": True, "attribution_required": True,
     "attribution_text": "Jobs from Jobicy", "daily_quota": 8},
    {"provider_id": "weworkremotely", "name": "We Work Remotely", "tier": 2, "auth_type": "none",
     "countries_supported": "remote_only", "has_published_date": True, "attribution_required": True,
     "attribution_text": "Jobs from We Work Remotely", "daily_quota": 8},
    {"provider_id": "themuse", "name": "The Muse", "tier": 2, "auth_type": "none",
     "countries_supported": ["US", "CA", "GB"], "has_published_date": True, "attribution_required": True,
     "attribution_text": "Jobs from The Muse", "daily_quota": 60},
    # Tier 3 — free-key APIs (keys from GitHub Actions secrets)
    {"provider_id": "adzuna", "name": "Adzuna", "tier": 3, "auth_type": "multi_key",
     "secrets": ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"], "countries_supported": "config:adzuna_countries",
     "has_published_date": True, "attribution_required": True, "attribution_text": "Jobs by Adzuna",
     "daily_quota": 200},
    {"provider_id": "jooble", "name": "Jooble", "tier": 3, "auth_type": "api_key", "secrets": ["JOOBLE_API_KEY"],
     "countries_supported": "from_jobs", "has_published_date": True, "attribution_required": True,
     "attribution_text": "Jobs from Jooble", "daily_quota": 100},
    {"provider_id": "careerjet", "name": "Careerjet", "tier": 3, "auth_type": "api_key",
     "secrets": ["CAREERJET_API_KEY"], "countries_supported": "from_jobs", "has_published_date": True,
     "attribution_required": True, "attribution_text": "Jobs by Careerjet", "daily_quota": 100},
    {"provider_id": "reed", "name": "Reed", "tier": 3, "auth_type": "api_key", "secrets": ["REED_API_KEY"],
     "countries_supported": ["GB"], "has_published_date": True, "attribution_required": True,
     "attribution_text": "Jobs from Reed.co.uk", "daily_quota": 100},
    {"provider_id": "usajobs", "name": "USAJOBS", "tier": 3, "auth_type": "multi_key",
     "secrets": ["USAJOBS_API_KEY", "USAJOBS_EMAIL"], "countries_supported": ["US"],
     "has_published_date": True, "attribution_required": False, "daily_quota": 50},
    {"provider_id": "findwork", "name": "Findwork", "tier": 3, "auth_type": "api_key",
     "secrets": ["FINDWORK_API_KEY"], "countries_supported": "from_jobs", "has_published_date": True,
     "attribution_required": True, "attribution_text": "Jobs from Findwork", "daily_quota": 60},
]

DEFAULTS = {"supports_keyword_filter": False, "supports_work_type_filter": False,
            "supports_date_filter": False, "supports_country_filter": False,
            "rate_limit": None, "daily_quota": None, "attribution_text": None, "enabled": True}


def registry(config: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    disabled = set(config.get("disabled_providers") or [])
    for entry in REGISTRY:
        e = {**DEFAULTS, **entry}
        cs = e["countries_supported"]
        if isinstance(cs, str) and cs.startswith("config:"):
            e["countries_supported"] = [c.upper().replace("UK", "GB") for c in config.get(cs[7:], [])]
        e["enabled"] = e["provider_id"] not in disabled
        out.append(e)
    return out


def public_view(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Registry entries as published in the manifest (no secret names)."""
    keep = ("provider_id", "name", "tier", "auth_type", "countries_supported", "has_published_date",
            "attribution_required", "attribution_text", "enabled")
    return [{k: e.get(k) for k in keep} for e in entries]
