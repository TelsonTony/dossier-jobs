"""Expiry (Architecture v7.1 Section 5.4).

* A job not returned by its source for 2 consecutive *successful* fetches is marked Closed.
* If a source fails this run, its jobs from the last good run are kept unchanged.
* Closed jobs stay in the index for `closed_retention_days` so the app can mark tracked jobs
  Closed; the app never deletes tracked jobs. The 45-day "hide old jobs" rule is applied
  in the app, using published_at.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

MISSES_TO_CLOSE = 2


def source_of(job: dict[str, Any]) -> str:
    """Health key a job belongs to: the company board for ATS jobs, the provider for APIs."""
    if job.get("tier") == 1 and job.get("board"):
        return f"{job['provider']}/{job['board']}"
    return job["provider"]


def apply_expiry(
    fresh: list[dict[str, Any]],
    previous: dict[str, dict[str, Any]],
    succeeded_sources: set[str],
    run_time: str,
    closed_retention_days: int = 14,
) -> tuple[list[dict[str, Any]], int]:
    """Merge this run's jobs with the previous state. Returns (jobs, newly closed count)."""
    out: dict[str, dict[str, Any]] = {}
    for job in fresh:
        prev = previous.get(job["job_key"])
        if prev:
            job["retrieved_at"] = prev.get("retrieved_at") or job["retrieved_at"]
            if not job.get("published_at") and prev.get("published_at"):
                job["published_at"] = prev["published_at"]
        job["missed_runs"] = 0
        job["closed"] = False
        job["closed_at"] = None
        job["last_seen_at"] = run_time
        out[job["job_key"]] = job

    newly_closed = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=closed_retention_days)
    for key, old in previous.items():
        if key in out:
            continue
        job = dict(old)
        if source_of(job) in succeeded_sources:
            if not job.get("closed"):
                job["missed_runs"] = int(job.get("missed_runs") or 0) + 1
                if job["missed_runs"] >= MISSES_TO_CLOSE:
                    job["closed"] = True
                    job["closed_at"] = run_time
                    newly_closed += 1
        # else: source failed or was paused — keep the last good data unchanged
        if job.get("closed") and job.get("closed_at"):
            try:
                closed_at = datetime.fromisoformat(job["closed_at"].replace("Z", "+00:00"))
                if closed_at < cutoff:
                    continue  # retention over: drop from the published index
            except ValueError:
                pass
        out[key] = job
    return list(out.values()), newly_closed
