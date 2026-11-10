"""Writes the published files (Architecture v7.1 Section 5.5) plus signatures and state.

site/
  manifest.json         version, run time, counts, per-source health, provider registry, index hash
  manifest.sig          Ed25519 signature over the exact bytes of manifest.json
  jobs_index.json.gz    every field except the description; each job has desc + desc_sha256
  desc/<id>.json.gz     one job's full description
  health_report.md      the same health data, for people
  state/state.json.gz   pipeline memory between runs (public job data only)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .sign import sha256_hex, sign_manifest

SCHEMA = 1
INDEX_FIELDS = ("job_key", "provider", "provider_job_id", "tier", "source_name", "board", "title", "company",
                "location", "country", "work_arrangement", "remote_eligible_countries", "experience_hint",
                "salary", "published_at", "retrieved_at", "last_seen_at", "apply_url", "source_url", "skills",
                "visa_sponsor_signal", "closed", "closed_at")


def gz(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


def dumps(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def desc_id(job_key: str) -> str:
    return hashlib.sha256(job_key.encode("utf-8")).hexdigest()[:24]


def read_state(previous_dir: Path) -> dict[str, Any]:
    path = previous_dir / "state" / "state.json.gz"
    if not path.exists():
        return {}
    try:
        return json.loads(gzip.decompress(path.read_bytes()))
    except (OSError, ValueError):
        return {}


def write_site(
    site: Path,
    jobs: list[dict[str, Any]],
    merged: dict[str, str],
    health: list[dict[str, Any]],
    providers: list[dict[str, Any]],
    state: dict[str, Any],
    run_at: str,
    stats: dict[str, Any],
    signing_key: Any | None,
    key_id: str,
) -> dict[str, Any]:
    tmp = site.with_name(site.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "desc").mkdir(parents=True)
    (tmp / "state").mkdir()

    jobs = sorted(jobs, key=lambda j: j["job_key"])
    index_jobs = []
    for job in jobs:
        did = desc_id(job["job_key"])
        blob = gz(dumps({"job_key": job["job_key"], "description": job.get("description") or ""}))
        (tmp / "desc" / f"{did}.json.gz").write_bytes(blob)
        entry = {k: job.get(k) for k in INDEX_FIELDS}
        entry["desc"] = f"desc/{did}.json.gz"
        entry["desc_sha256"] = sha256_hex(blob)
        index_jobs.append(entry)

    # last_seen_at changes every run; leave it out so an unchanged job list keeps its version
    # and phones download nothing (acceptance criterion 21).
    stable = [{k: v for k, v in j.items() if k != "last_seen_at"} for j in index_jobs]
    content_hash = sha256_hex(dumps({"jobs": stable, "merged": merged}))
    version = int(state.get("version") or 0)
    if content_hash != state.get("index_hash"):
        version += 1
    state["version"] = version
    state["index_hash"] = content_hash

    index_bytes = gz(dumps({"schema": SCHEMA, "version": version, "generated_at": run_at,
                            "jobs": index_jobs, "merged": merged}))
    (tmp / "jobs_index.json.gz").write_bytes(index_bytes)

    manifest = {
        "schema": SCHEMA,
        "version": version,
        "run_at": run_at,
        "job_count": len(index_jobs),
        "open_count": sum(1 for j in index_jobs if not j.get("closed")),
        "index": {"path": "jobs_index.json.gz", "sha256": sha256_hex(index_bytes), "bytes": len(index_bytes)},
        "stats": stats,
        "sources": health,
        "providers": providers,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")
    (tmp / "manifest.json").write_bytes(manifest_bytes)
    if signing_key is not None:
        (tmp / "manifest.sig").write_bytes(sign_manifest(manifest_bytes, signing_key, key_id))

    state["jobs"] = {j["job_key"]: j for j in jobs}
    (tmp / "state" / "state.json.gz").write_bytes(gz(dumps(state)))
    (tmp / "health_report.md").write_text(health_markdown(manifest), encoding="utf-8")
    (tmp / ".nojekyll").write_text("", encoding="utf-8")
    (tmp / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Dossier job data</title>"
        "<p>Public job listings published by the Dossier pipeline. See "
        "<a href='health_report.md'>health_report.md</a>.</p>", encoding="utf-8")

    # Replace the site folder contents but keep a .git folder if the site is a checkout.
    site.mkdir(parents=True, exist_ok=True)
    for child in site.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in tmp.iterdir():
        shutil.move(str(child), str(site / child.name))
    shutil.rmtree(tmp)
    return manifest


def health_markdown(manifest: dict[str, Any]) -> str:
    lines = [f"# Dossier pipeline health — run {manifest['run_at']}", "",
             f"Version {manifest['version']} · {manifest['open_count']} open jobs "
             f"({manifest['job_count']} in index)", "",
             "| Source | Tier | Status | Jobs | Note |", "|---|---|---|---|---|"]
    for s in sorted(manifest["sources"], key=lambda x: (x.get("tier", 9), x.get("kind", ""), x.get("name", ""))):
        lines.append(f"| {s.get('name')} | {s.get('tier')} | {s.get('status')} | {s.get('job_count', 0)} | "
                     f"{(s.get('message') or '').replace('|', '/')} |")
    review = [s for s in manifest["sources"] if s.get("needs_review")]
    if review:
        lines += ["", "## Company rows to re-check", ""]
        lines += [f"- {s['name']} ({s['id']}): {s.get('status')} — {s.get('message') or ''}" for s in review]
    return "\n".join(lines) + "\n"
