"""Deduplication (Architecture v7.1 Section 5.3).

1. Exact match on apply_url after removing tracking parameters -> same job.
2. Otherwise normalised company + title + location -> same job.
3. When merging, prefer the Tier 1 (ATS) record, since it comes from the employer.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = re.compile(r"^(utm_.*|gh_src|gh_jid_src|source|src|ref|referrer|lever-source.*|lever-origin|"
                      r"trk|trackingid|fbclid|gclid|mc_.*|_hs.*|campaign|medium|clickid|iis|iisn)$", re.I)
COMPANY_SUFFIX = re.compile(r"\b(inc|inc\.|llc|ltd|ltd\.|limited|plc|gmbh|ag|sa|sas|bv|b\.v\.|corp|"
                            r"corporation|co|company|technologies|technology|labs|group|holdings)\b\.?", re.I)


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING.match(k)]
    path = parts.path.rstrip("/")
    for suffix in ("/apply", "/application"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower().removeprefix("www."), path,
                       urlencode(sorted(query)), ""))


def _norm(text: str | None) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def normalize_company(name: str | None) -> str:
    return _norm(COMPANY_SUFFIX.sub(" ", name or ""))


def fingerprint(job: dict[str, Any]) -> str:
    return "|".join([normalize_company(job.get("company")), _norm(job.get("title")), _norm(job.get("location"))])


def _better(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Pick the record to keep: lower tier wins, then the one with a published date, then longer text."""
    ka = (a.get("tier", 9), 0 if a.get("published_at") else 1, -len(a.get("description") or ""))
    kb = (b.get("tier", 9), 0 if b.get("published_at") else 1, -len(b.get("description") or ""))
    return a if ka <= kb else b


def dedupe(jobs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Returns (unique jobs, number of duplicates merged)."""
    by_key: dict[str, dict[str, Any]] = {}
    for j in jobs:  # same provider job twice in one run
        prev = by_key.get(j["job_key"])
        by_key[j["job_key"]] = j if prev is None else _better(prev, j)
    keepers: dict[str, dict[str, Any]] = {}
    url_index: dict[str, str] = {}
    fp_index: dict[str, str] = {}
    merged = 0
    for job in by_key.values():
        url = normalize_url(job.get("apply_url"))
        fp = fingerprint(job)
        match_key = (url_index.get(url) if url else None) or fp_index.get(fp)
        if match_key and match_key in keepers:
            current = keepers[match_key]
            winner = _better(current, job)
            loser = job if winner is current else current
            loser["duplicate_of"] = winner["job_key"]
            merged += 1
            if winner is not current:
                del keepers[match_key]
                keepers[winner["job_key"]] = winner
                for idx in (url_index, fp_index):
                    for k, v in list(idx.items()):
                        if v == match_key:
                            idx[k] = winner["job_key"]
            target = winner["job_key"]
        else:
            keepers[job["job_key"]] = job
            target = job["job_key"]
        if url:
            url_index.setdefault(url, target)
        fp_index.setdefault(fp, target)
    return list(keepers.values()), merged
