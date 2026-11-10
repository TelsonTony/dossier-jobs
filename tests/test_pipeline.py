"""Offline tests: saved sample responses, no live calls (Build plan, Testing)."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path

import pytest
from nacl.signing import SigningKey

from pipeline import http, main as pipeline_main
from pipeline.adapters import Company, ashby, greenhouse, lever, remoteok, weworkremotely, workable
from pipeline.companies import load_companies
from pipeline.countries import country_from_location, countries_in_text
from pipeline.dedupe import dedupe, normalize_url
from pipeline.expire import apply_expiry
from pipeline.normalize import experience_hint, make_job, strip_html, to_iso
from pipeline.sign import sign_manifest, verify_manifest
from pipeline.skills import extract_skills
from pipeline.sponsor import mentioned_in_jd

CO = Company("Stripe", "greenhouse", "stripe")


def job(**kw):
    base = dict(provider="greenhouse", tier=1, provider_job_id="1", title="QA Engineer", company="Acme",
                location="London, UK", apply_url="https://example.com/jobs/1")
    base.update(kw)
    return make_job(**base)


# ---- adapters -------------------------------------------------------------------------

def test_greenhouse_parse():
    data = {"jobs": [{"id": 42, "title": "Senior Backend Engineer", "updated_at": "2026-10-01T10:00:00-04:00",
                      "location": {"name": "Remote - US"}, "absolute_url": "https://job-boards.greenhouse.io/stripe/jobs/42",
                      "content": "&lt;p&gt;We use Java and Kafka.&lt;/p&gt;"}]}
    jobs = greenhouse.parse(data, CO)
    assert len(jobs) == 1
    j = jobs[0]
    assert j["job_key"] == "greenhouse:stripe-42"
    assert j["company"] == "Stripe"
    assert j["work_arrangement"] == "remote"
    assert j["remote_eligible_countries"] == ["US"]
    assert j["experience_hint"] == "senior"
    assert "Java" in j["skills"] and "Kafka" in j["skills"]
    assert "<p>" not in j["description"]
    assert j["published_at"] == "2026-10-01T14:00:00Z"


def test_greenhouse_bad_shape():
    with pytest.raises(http.InvalidResponse):
        greenhouse.parse({"oops": 1}, CO)


def test_lever_parse():
    data = [{"id": "abc", "text": "QA Automation Engineer", "categories": {"location": "Berlin"},
             "createdAt": 1790000000000, "hostedUrl": "https://jobs.lever.co/x/abc",
             "applyUrl": "https://jobs.lever.co/x/abc/apply", "descriptionPlain": "Appium and Selenium",
             "lists": [{"text": "Requirements", "content": "<li>Postman</li>"}], "workplaceType": "hybrid"}]
    j = lever.parse(data, Company("X", "lever", "x"))[0]
    assert j["country"] == "DE" and j["work_arrangement"] == "hybrid"
    assert {"Appium", "Selenium", "Postman"} <= set(j["skills"])


def test_ashby_parse():
    data = {"jobs": [{"id": "u1", "title": "Data Analyst", "location": "Bengaluru", "isRemote": False,
                      "workplaceType": "OnSite", "publishedAt": "2026-11-01T00:00:00.000+00:00",
                      "jobUrl": "https://jobs.ashbyhq.com/r/u1", "descriptionPlain": "SQL and Tableau",
                      "compensation": {"compensationTierSummary": "₹20L – ₹30L"}}]}
    j = ashby.parse(data, Company("Ramp", "ashby", "ramp"))[0]
    assert j["country"] == "IN" and j["salary"] == "₹20L – ₹30L"
    assert j["work_arrangement"] == "onsite"


def test_workable_parse():
    data = {"name": "Hugging Face", "jobs": [{"title": "ML Engineer", "shortcode": "ABC", "telecommuting": True,
                                              "country": "France", "city": "Paris", "url": "https://apply.workable.com/huggingface/j/ABC",
                                              "published_on": "2026-10-20", "description": "<p>PyTorch</p>"}]}
    j = workable.parse(data, Company("HF", "workable", "huggingface"))[0]
    assert j["work_arrangement"] == "remote" and j["company"] == "Hugging Face"
    assert "PyTorch" in j["skills"]


def test_remoteok_skips_legal_notice():
    data = [{"legal": "notice"}, {"id": "9", "position": "Dev", "company": "Co", "epoch": 1790000000,
                                  "location": "Worldwide", "url": "https://remoteok.com/remote-jobs/9"}]
    jobs = remoteok.parse(data)
    assert len(jobs) == 1 and jobs[0]["remote_eligible_countries"] == ["WORLDWIDE"]
    assert jobs[0]["source_url"].startswith("https://remoteok.com")


def test_wwr_rejects_entities():
    with pytest.raises(http.InvalidResponse):
        weworkremotely.parse('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><rss/>')


def test_wwr_parse():
    rss = """<rss><channel><item><title>Acme: Senior Rust Developer</title><link>https://weworkremotely.com/x</link>
    <pubDate>Mon, 02 Nov 2026 10:00:00 +0000</pubDate><region>Anywhere in the World</region>
    <description>&lt;p&gt;Rust&lt;/p&gt;</description></item></channel></rss>"""
    j = weworkremotely.parse(rss)[0]
    assert j["company"] == "Acme" and j["title"] == "Senior Rust Developer"
    assert j["remote_eligible_countries"] == ["WORLDWIDE"]


# ---- normalisation --------------------------------------------------------------------

def test_html_is_stripped_safely():
    out = strip_html("<script>alert(1)</script><p>Hello <b>there</b></p><ul><li>One</li></ul>")
    assert "alert" not in out and "<" not in out and "• One" in out


def test_http_links_upgraded_and_bad_links_dropped():
    assert job(apply_url="http://x.com/a")["apply_url"] == "https://x.com/a"
    assert job(apply_url="javascript:alert(1)", source_url=None)["apply_url"] is None


def test_dates():
    assert to_iso("13/10/2026") == "2026-10-13T00:00:00Z"
    assert to_iso(None) is None and to_iso("garbage") is None
    assert to_iso("2999-01-01") is None


def test_countries():
    assert country_from_location("Austin, TX") == "US"
    assert country_from_location("London, UK") == "GB"
    assert country_from_location("London or Berlin") is None  # ambiguous stays unknown
    assert countries_in_text("Remote (EU only)")[:1] and "DE" in countries_in_text("Remote (EU only)")
    assert countries_in_text("Worldwide") == ["WORLDWIDE"]


def test_skills_case_rules():
    assert "Go" not in extract_skills("We go to market fast")
    assert "Go" in extract_skills("Backend in Go and Python")
    assert "C++" in extract_skills("Modern C++ experience")


def test_experience_hint():
    assert experience_hint("Junior QA") == "entry"
    assert experience_hint("Staff Engineer") == "senior"
    assert experience_hint("Engineer", "3+ years of experience") == "mid"
    assert experience_hint("Engineer") == "unknown"


def test_sponsor_phrases():
    assert mentioned_in_jd("Visa sponsorship is available for this role.")
    assert not mentioned_in_jd("We are unable to sponsor visas. Visa sponsorship is available elsewhere.")
    assert not mentioned_in_jd("No sponsorship.")


# ---- dedupe and expiry ----------------------------------------------------------------

def test_dedupe_by_url_prefers_ats():
    a = job(provider="adzuna", tier=3, provider_job_id="z", apply_url="https://example.com/jobs/1?utm_source=adzuna")
    b = job(provider="greenhouse", tier=1, provider_job_id="g", apply_url="https://example.com/jobs/1")
    out, merged = dedupe([a, b])
    assert merged == 1 and len(out) == 1 and out[0]["provider"] == "greenhouse"
    assert a["duplicate_of"] == b["job_key"]


def test_dedupe_by_fingerprint():
    a = job(provider="reed", tier=3, provider_job_id="r", company="Acme Ltd", apply_url="https://reed.co.uk/1")
    b = job(provider="lever", tier=1, provider_job_id="l", company="Acme", apply_url="https://jobs.lever.co/acme/1")
    out, merged = dedupe([a, b])
    assert merged == 1 and out[0]["provider"] == "lever"


def test_normalize_url():
    assert normalize_url("https://www.X.com/a/apply?gh_src=1&id=2") == "https://x.com/a?id=2"


def test_expiry_two_misses_then_closed():
    j = job()
    prev = {j["job_key"]: dict(j)}
    src = {"greenhouse"}  # no board on this job -> source is the provider id
    jobs, closed = apply_expiry([], prev, src, "2026-11-10T00:00:00Z")
    assert closed == 0 and jobs[0]["missed_runs"] == 1 and not jobs[0]["closed"]
    jobs, closed = apply_expiry([], {jobs[0]["job_key"]: jobs[0]}, src, "2026-11-10T06:00:00Z")
    assert closed == 1 and jobs[0]["closed"]


def test_expiry_failed_source_keeps_last_good():
    j = job()
    jobs, closed = apply_expiry([], {j["job_key"]: dict(j)}, set(), "2026-11-10T00:00:00Z")
    assert closed == 0 and jobs[0].get("missed_runs", 0) == 0 and not jobs[0]["closed"]


# ---- signing --------------------------------------------------------------------------

def test_sign_and_verify_and_tamper():
    key = SigningKey.generate()
    pub = base64.b64encode(bytes(key.verify_key)).decode()
    data = b'{"version":1}'
    sig = sign_manifest(data, key, "k1")
    assert verify_manifest(data, sig, {"k1": pub})
    assert not verify_manifest(b'{"version":2}', sig, {"k1": pub})
    assert not verify_manifest(data, sig, {"k2": pub})


# ---- workbook -------------------------------------------------------------------------

def test_workbook_loads_51_companies():
    companies, warnings = load_companies()
    assert len(companies) == 51 and not warnings
    counts = {}
    for c in companies:
        counts[c.ats_type] = counts.get(c.ats_type, 0) + 1
    assert counts == {"greenhouse": 15, "lever": 17, "ashby": 17, "workable": 2}
    assert greenhouse.build_url("stripe") == "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true"


# ---- end to end (adapters stubbed, no network) ----------------------------------------

def test_end_to_end_publishes_signed_files(tmp_path: Path, monkeypatch):
    key = SigningKey.generate()
    monkeypatch.setenv("DOSSIER_SIGNING_KEY", base64.b64encode(bytes(key)).decode())

    def fake_company(company, ctx):
        if company.slug == "netflix":
            raise http.BoardNotFound("HTTP 404")
        return [job(provider=company.ats_type, provider_job_id=f"{company.slug}-1", company=company.company_name,
                    board=company.slug, apply_url=f"https://example.com/{company.slug}/1")]

    def fake_api(ctx):
        raise http.MissingKey()

    monkeypatch.setattr(pipeline_main, "ats_adapters", lambda: {t: fake_company for t in
                                                                ("greenhouse", "lever", "ashby", "workable",
                                                                 "smartrecruiters", "custom")})
    monkeypatch.setattr(pipeline_main, "api_adapters", lambda: {"adzuna": fake_api})
    monkeypatch.setattr(pipeline_main, "refresh_uk_register", lambda state, log: None)
    site = tmp_path / "site"
    assert pipeline_main.main(["--site", str(site)]) == 0

    manifest = (site / "manifest.json").read_bytes()
    pub = base64.b64encode(bytes(key.verify_key)).decode()
    assert verify_manifest(manifest, (site / "manifest.sig").read_bytes(), {"k1": pub})
    m = json.loads(manifest)
    index_bytes = (site / "jobs_index.json.gz").read_bytes()
    assert hashlib.sha256(index_bytes).hexdigest() == m["index"]["sha256"]
    index = json.loads(gzip.decompress(index_bytes))
    assert m["open_count"] == 50 and "description" not in index["jobs"][0]
    first = index["jobs"][0]
    assert hashlib.sha256((site / first["desc"]).read_bytes()).hexdigest() == first["desc_sha256"]
    statuses = {s["id"]: s for s in m["sources"]}
    assert statuses["lever/netflix"]["status"] == "Board not found" and statuses["lever/netflix"]["needs_review"]
    assert statuses["adzuna"]["status"] == "Missing key"
    # No personal data and no keys in published files
    blob = b"".join(p.read_bytes() for p in site.rglob("*") if p.is_file())
    assert base64.b64encode(bytes(key)) not in blob

    # Second run with nothing changed keeps the same version (phone downloads nothing).
    v1 = m["version"]
    import time
    time.sleep(1.1)  # make sure run_at differs
    assert pipeline_main.main(["--site", str(site)]) == 0
    assert json.loads((site / "manifest.json").read_bytes())["version"] == v1


def test_refuses_to_run_unsigned(tmp_path, monkeypatch):
    monkeypatch.delenv("DOSSIER_SIGNING_KEY", raising=False)
    assert pipeline_main.main(["--site", str(tmp_path / "s")]) == 2
