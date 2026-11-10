# dossier-jobs

The scheduled job pipeline for the Dossier app (Architecture v7.1 §3–6, build plan Phase 1).
It runs on GitHub Actions every 6 hours, fetches **all** open jobs from the ATS company list and
public job APIs, and publishes signed files on GitHub Pages. It never sees anyone's resume;
each phone filters the jobs locally.

> Setup steps are in [`../USER_MANUAL.md`](../USER_MANUAL.md), Part 1. This README is the reference.

## What it publishes (gh-pages branch → GitHub Pages)

| File | Contents | Phone downloads it |
|---|---|---|
| `manifest.json` | version, run time, counts, per-source health, provider registry, SHA-256 of the index | every sync |
| `manifest.sig` | Ed25519 signature over the exact bytes of `manifest.json` | every sync |
| `jobs_index.json.gz` | every job field except the description; each job carries `desc` + `desc_sha256` | only when the version changes |
| `desc/<id>.json.gz` | one job's description | only when that job is opened |
| `health_report.md` | the health table for people | — |
| `state/state.json.gz` | pipeline memory between runs (public job data only) | — |

Chain of trust: `manifest.sig` → `manifest.json` → hash of `jobs_index.json.gz` → hash of each description file.
The app holds the public key and rejects anything that fails.

## Layout

```
.github/workflows/fetch-jobs.yml   schedule + manual run, signs, pushes gh-pages
.github/workflows/tests.yml        unit tests + pip-audit on every push / PR (no secrets)
data/Dossier_ATS_Company_List.xlsx company list (Companies sheet is read by the job)
data/skills.json                   skills dictionary (same file ships in the app)
data/sponsors_us.txt               optional US sponsor employer names
pipeline/                          adapters, normalize, dedupe, expire, sponsor, sign, publish
tools/                             signing key, workbook builder, source tester, site verifier
tests/                             offline tests with saved sample responses
```

## Commands

```bash
pip install -r requirements-dev.txt
python -m pytest -q                                     # offline tests
python tools/generate_signing_key.py                    # once; see the manual
python tools/test_sources.py --try-other-ats            # one test call per company row
DOSSIER_SIGNING_KEY=... python -m pipeline.main --site site       # full local run
python -m pipeline.main --site site --only tier1 --allow-unsigned   # quick local test
python tools/verify_site.py --public-key <PUB> --url https://<user>.github.io/dossier-jobs/
```

## Sources

* **Tier 1** — Greenhouse, Lever (EU host fallback), Ashby, Workable, SmartRecruiters, custom JSON:
  every enabled row of the Companies sheet. The URL is built in code from `ats_type` + `slug`.
* **Tier 2** — Arbeitnow, Remotive, RemoteOK, Jobicy, We Work Remotely, The Muse (disabled by
  default: it answered HTTP 403 to automated requests in testing, Nov 2026).
* **Tier 3** — Adzuna, Jooble, Careerjet, Reed, USAJOBS, Findwork. Skipped as "Missing key"
  until the matching Actions secret exists.

Failures never stop the run (v7.1 §6): 401/403 → Invalid key, 404 → Board not found, 429 →
cooldown, 5xx/timeouts → bounded retry, bad JSON → Could not read response. Jobs from a failed
source are kept from the last good run.

## Rules implemented

* Dedupe: same apply URL (tracking parameters removed), else company + title + location; the
  Tier 1 record wins. Merged keys are published so tracked jobs follow the kept record.
* Expiry: missing from 2 consecutive successful fetches → Closed; closed jobs stay 14 days so
  the app can mark tracked jobs Closed. The app hides jobs older than 45 days.
* Sponsor signal: UK Register of Licensed Sponsors (refreshed monthly), `data/sponsors_us.txt`,
  and phrase scanning where negative phrases win. Never claims a role is sponsored.
* The version only changes when the job list changes, so unchanged runs cost phones nothing.
