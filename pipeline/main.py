"""Dossier job pipeline (Architecture v7.1 Section 5.2).

    python -m pipeline.main --site site

Steps: load company list + providers -> fetch (all jobs, no role filter) -> normalise ->
deduplicate -> expire -> sponsor check -> optional country pre-filter -> write files ->
sign. Publishing (pushing the site folder to the gh-pages branch) is done by the workflow.
The pipeline never sees anyone's resume.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import http
from .adapters import Company, FetchContext, api_adapters, ats_adapters
from .companies import WORKBOOK, load_companies
from .dedupe import dedupe
from .expire import apply_expiry, source_of
from .normalize import now_iso
from .publish import read_state, write_site
from .registry import public_view, registry
from .sign import load_signing_key, public_key_b64
from .sponsor import apply_signals, refresh_uk_register

CONFIG = Path(__file__).resolve().parent / "config.json"
SECRET_NAMES = ["ADZUNA_APP_ID", "ADZUNA_APP_KEY", "JOOBLE_API_KEY", "CAREERJET_API_KEY", "REED_API_KEY",
                "USAJOBS_API_KEY", "USAJOBS_EMAIL", "FINDWORK_API_KEY", "THEMUSE_API_KEY"]


def log(msg: str) -> None:
    print(msg, flush=True)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _health(id_: str, name: str, tier: int, kind: str, status: str, count: int = 0, message: str = "",
            **extra: Any) -> dict[str, Any]:
    return {"id": id_, "name": name, "tier": tier, "kind": kind, "status": status, "job_count": count,
            "message": message, **extra}


def run_company(company: Company, ctx: FetchContext) -> tuple[Company, list[dict[str, Any]], Exception | None]:
    try:
        jobs = ats_adapters()[company.ats_type](company, ctx)
        return company, jobs, None
    except http.SourceError as exc:
        return company, [], exc
    except Exception as exc:  # noqa: BLE001 — a bug in one adapter must not stop the run
        return company, [], http.InvalidResponse(f"{type(exc).__name__}: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and publish Dossier job data")
    parser.add_argument("--site", default="site", help="output folder (the gh-pages checkout)")
    parser.add_argument("--previous", default=None, help="folder holding the previous run (default: --site)")
    parser.add_argument("--workbook", default=str(WORKBOOK))
    parser.add_argument("--only", default="", help="comma list: tier1, tier2, tier3 or provider ids (testing)")
    parser.add_argument("--allow-unsigned", action="store_true", help="local testing only; the app rejects unsigned data")
    args = parser.parse_args(argv)

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    site = Path(args.site)
    previous_dir = Path(args.previous) if args.previous else site
    state = read_state(previous_dir)
    previous_jobs: dict[str, dict[str, Any]] = state.get("jobs") or {}
    cooldowns: dict[str, str] = state.get("cooldowns") or {}
    zero_runs: dict[str, int] = state.get("zero_runs") or {}
    last_success: dict[str, str] = state.get("last_success") or {}
    run_at = now_iso()
    now = datetime.now(timezone.utc)
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    seed = os.environ.get("DOSSIER_SIGNING_KEY", "").strip()
    key_id = os.environ.get("DOSSIER_SIGNING_KEY_ID", "k1").strip() or "k1"
    signing_key = None
    if seed:
        signing_key = load_signing_key(seed)
        log(f"Signing with key '{key_id}' (public {public_key_b64(signing_key)})")
    elif not args.allow_unsigned:
        log("ERROR: DOSSIER_SIGNING_KEY is not set. Add it as a GitHub Actions secret "
            "(see USER_MANUAL.md). Use --allow-unsigned only for local tests.")
        return 2

    keys = {name: os.environ.get(name, "").strip() for name in SECRET_NAMES}
    keys = {k: v for k, v in keys.items() if v}
    runs_per_day = max(1, int(config.get("runs_per_day", 4)))
    reg = registry(config)
    reg_by_id = {e["provider_id"]: e for e in reg}

    health: list[dict[str, Any]] = []
    fresh: list[dict[str, Any]] = []
    succeeded: set[str] = set()
    paused: set[str] = set()  # paused companies: their jobs leave the index

    def wanted(provider_id: str, tier: int) -> bool:
        return not only or provider_id in only or f"tier{tier}" in only

    # ---- Tier 1: company ATS boards -------------------------------------------------------
    companies, warnings = load_companies(Path(args.workbook))
    for w in warnings:
        log(f"Workbook: {w}")
    to_fetch: list[Company] = []
    for c in companies:
        hid = f"{c.ats_type}/{c.slug}"
        if c.ats_type == "unsupported":
            health.append(_health(hid, c.company_name, 1, "company", "Not covered", message="Unsupported ATS; skipped"))
        elif not c.enabled:
            health.append(_health(hid, c.company_name, 1, "company", "Paused", message="enabled = FALSE"))
            paused.add(hid)
        elif not reg_by_id.get(c.ats_type, {}).get("enabled", True) or not wanted(c.ats_type, 1):
            continue
        else:
            to_fetch.append(c)
    log(f"Fetching {len(to_fetch)} company boards")
    ctx1 = FetchContext(config=config, keys={}, page_cap=int(config.get("page_cap", 5)), log=log)
    with ThreadPoolExecutor(max_workers=int(config.get("parallel_boards", 6))) as pool:
        futures = [pool.submit(run_company, c, ctx1) for c in to_fetch]
        for fut in as_completed(futures):
            c, jobs, err = fut.result()
            hid = f"{c.ats_type}/{c.slug}"
            if err is None:
                succeeded.add(hid)
                last_success[hid] = run_at
                fresh.extend(jobs)
                zero_runs[hid] = 0 if jobs else zero_runs.get(hid, 0) + 1
                status = "Succeeded" if jobs else "No results"
                msg = f"No jobs for {zero_runs[hid]} runs; company may have stopped posting here" \
                    if zero_runs[hid] >= 3 else ""
                health.append(_health(hid, c.company_name, 1, "company", status, len(jobs), msg,
                                      ats=c.ats_type, needs_review=zero_runs[hid] >= 3,
                                      last_success_at=run_at))
            else:
                review = isinstance(err, http.BoardNotFound)
                msg = "Slug is wrong or the company moved ATS; re-check the row" if review else str(err)
                health.append(_health(hid, c.company_name, 1, "company", err.status, 0, msg, ats=c.ats_type,
                                      needs_review=review, last_success_at=last_success.get(hid)))
            log(f"  {hid}: {health[-1]['status']} ({health[-1]['job_count']})")

    # Per-ATS summary rows for the Sources screen
    for ats in ("greenhouse", "lever", "ashby", "workable", "smartrecruiters", "custom"):
        rows = [h for h in health if h.get("kind") == "company" and h.get("ats") == ats]
        if not rows:
            continue
        ok = sum(1 for h in rows if h["status"] in ("Succeeded", "No results"))
        bad = [h for h in rows if h["status"] not in ("Succeeded", "No results", "Paused", "Not covered")]
        total = sum(h["job_count"] for h in rows)
        status = ("Succeeded" if total else "No results") if ok else (bad[0]["status"] if bad else "Paused")
        msg = f"{len(bad)} board(s) need attention" if bad else ""
        health.append(_health(ats, reg_by_id[ats]["name"], 1, "provider", status,
                              total, msg, boards=len(rows)))

    # ---- Tier 2 and 3: APIs ---------------------------------------------------------------
    for provider_id, fetch in api_adapters().items():
        entry = reg_by_id[provider_id]
        tier = entry["tier"]
        if not wanted(provider_id, tier):
            continue
        if not entry["enabled"]:
            health.append(_health(provider_id, entry["name"], tier, "provider", "Paused", message="Disabled in config"))
            continue
        cd = _parse_time(cooldowns.get(provider_id))
        if cd and cd > now:
            health.append(_health(provider_id, entry["name"], tier, "provider", "Rate limited",
                                  message=f"Cooldown until {cooldowns[provider_id]}. Showing jobs from the last good run.",
                                  cooldown_until=cooldowns[provider_id], last_success_at=last_success.get(provider_id)))
            continue
        quota = entry.get("daily_quota")
        budget = http.Budget(limit=max(1, quota // runs_per_day) if quota else None)
        ctx = FetchContext(config=config, keys=keys, budget=budget,
                           page_cap=int(config.get("api_page_cap", {}).get(provider_id, config.get("page_cap", 5))),
                           log=log)
        try:
            jobs = fetch(ctx)
            fresh.extend(jobs)
            succeeded.add(provider_id)
            last_success[provider_id] = run_at
            cooldowns.pop(provider_id, None)
            health.append(_health(provider_id, entry["name"], tier, "provider",
                                  "Succeeded" if jobs else "No results", len(jobs),
                                  request_count=budget.used, last_success_at=run_at))
        except http.SourceError as exc:
            msg = str(exc)
            if isinstance(exc, http.RateLimited):
                until = now + timedelta(seconds=exc.retry_after or 6 * 3600)
                cooldowns[provider_id] = until.replace(microsecond=0).isoformat().replace("+00:00", "Z")
                msg = "Cooldown set. Showing jobs from the last good run."
            elif isinstance(exc, http.QuotaExhausted):
                tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
                cooldowns[provider_id] = tomorrow.isoformat().replace("+00:00", "Z")
                msg = "Paused until the quota resets. Showing jobs from the last good run."
            elif isinstance(exc, http.MissingKey):
                msg = "Add the key as a GitHub Actions secret: " + ", ".join(entry.get("secrets") or [])
            elif isinstance(exc, http.InvalidKey):
                msg = "The provider rejected the key; replace the secret"
            health.append(_health(provider_id, entry["name"], tier, "provider", exc.status, 0, msg,
                                  request_count=budget.used, last_success_at=last_success.get(provider_id)))
        except Exception as exc:  # noqa: BLE001
            health.append(_health(provider_id, entry["name"], tier, "provider", "Could not read response", 0,
                                  f"{type(exc).__name__}", last_success_at=last_success.get(provider_id)))
        log(f"  {provider_id}: {health[-1]['status']} ({health[-1]['job_count']})")

    # ---- Normalise is done inside adapters; now dedupe, expire, sponsor -------------------
    fetched_total = len(fresh)
    unique, merged_count = dedupe(fresh)
    merged = {j["job_key"]: j["duplicate_of"] for j in fresh if j.get("duplicate_of")}
    prev_open = {k: v for k, v in previous_jobs.items() if k not in merged and source_of(v) not in paused}
    jobs, newly_closed = apply_expiry(unique, prev_open, succeeded, run_at,
                                      int(config.get("closed_retention_days", 14)))
    # Kept jobs from failed sources may now duplicate fresh ones; dedupe open jobs once more.
    open_jobs = [j for j in jobs if not j.get("closed")]
    closed_jobs = [j for j in jobs if j.get("closed")]
    open_jobs, extra_merged = dedupe(open_jobs)
    jobs = open_jobs + closed_jobs

    # Optional safe pre-filter: drop countries never targeted. Never role or resume filtering.
    targets = {c.upper() for c in config.get("target_countries") or []}
    if targets:
        def keep(j: dict[str, Any]) -> bool:
            if j.get("country") is None or j.get("country") in targets:
                return True
            eligible = set(j.get("remote_eligible_countries") or [])
            return bool(eligible & (targets | {"WORLDWIDE"}))
        jobs = [j for j in jobs if keep(j)]

    max_age = int(config.get("max_age_days", 120))
    cutoff = now - timedelta(days=max_age)
    jobs = [j for j in jobs if not (_parse_time(j.get("published_at")) and _parse_time(j["published_at"]) < cutoff)]

    if config.get("sponsor_check", True):
        refresh_uk_register(state, log)
        flagged = apply_signals(jobs, state)
    else:
        flagged = 0

    for j in jobs:
        j.pop("duplicate_of", None)

    state.update({"cooldowns": cooldowns, "zero_runs": zero_runs, "last_success": last_success,
                  "last_run_at": run_at})
    stats = {"fetched": fetched_total, "duplicates_merged": merged_count + extra_merged,
             "newly_closed": newly_closed, "sponsor_signals": flagged,
             "sources_succeeded": len(succeeded), "companies": len(companies)}
    manifest = write_site(site, jobs, merged, health, public_view(reg), state, run_at, stats, signing_key, key_id)
    log(f"Published version {manifest['version']}: {manifest['open_count']} open jobs, "
        f"index {manifest['index']['bytes'] / 1024:.0f} KB")
    if not succeeded:
        log("WARNING: no source succeeded this run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
