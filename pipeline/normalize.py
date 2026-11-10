"""Common job schema (Architecture v7.1 Section 5.1) and normalisation helpers."""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .countries import countries_in_text, country_from_location
from .skills import extract_skills

WORK_REMOTE, WORK_HYBRID, WORK_ONSITE, WORK_UNKNOWN = "remote", "hybrid", "onsite", "unknown"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_iso(value: Any) -> str | None:
    """Accepts ISO strings, epoch seconds/ms, RFC 2822 and dd/mm/yyyy. Returns UTC ISO or None."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        text = str(value).strip()
        if re.fullmatch(r"\d{10,13}", text):
            return to_iso(int(text))
        m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", text)
        if m:
            d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=timezone.utc)
            return d.isoformat().replace("+00:00", "Z")
        if re.match(r"^[A-Za-z]{3}, ", text):
            from email.utils import parsedate_to_datetime

            d = parsedate_to_datetime(text)
        else:
            t = text.replace("Z", "+00:00")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
                t += "T00:00:00+00:00"
            d = datetime.fromisoformat(t)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        d = d.astimezone(timezone.utc).replace(microsecond=0)
        if d.year < 2000 or d > datetime.now(timezone.utc) + timedelta(days=2):
            return None  # implausible dates are treated as unknown
        return d.isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError):
        return None


_BLOCK_TAGS = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr|section|article)[^>]*>", re.I)
_TAGS = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)


def strip_html(text: str | None, max_len: int = 40000) -> str:
    """HTML -> safe plain text. The app shows descriptions as plain text only."""
    if not text:
        return ""
    t = html.unescape(str(text))
    if "&lt;" in t or "&gt;" in t:  # double-escaped (Greenhouse)
        t = html.unescape(t)
    t = _SCRIPT.sub(" ", t)
    t = re.sub(r"<li[^>]*>", "\n• ", t, flags=re.I)
    t = _BLOCK_TAGS.sub("\n", t)
    t = _TAGS.sub("", t)
    t = t.replace("\r", "")
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
    t = "\n".join(line.strip() for line in t.split("\n"))
    # Drop control characters except newline and tab.
    t = "".join(ch for ch in t if ch in "\n\t" or ord(ch) >= 32)
    return t.strip()[:max_len]


def detect_work_arrangement(*hints: str | None, explicit: str | None = None) -> str:
    if explicit:
        e = explicit.lower().replace("-", "").replace("_", "").replace(" ", "")
        if e in ("remote", "fullyremote"):
            return WORK_REMOTE
        if e == "hybrid":
            return WORK_HYBRID
        if e in ("onsite", "inoffice", "office", "inperson"):
            return WORK_ONSITE
    blob = " ".join(h for h in hints if h).lower()
    if not blob:
        return WORK_UNKNOWN
    if re.search(r"\bhybrid\b", blob):
        return WORK_HYBRID
    if re.search(r"\b(remote|work from home|wfh|anywhere)\b", blob):
        return WORK_REMOTE
    if re.search(r"\b(on-?site|in[- ]office|in person)\b", blob):
        return WORK_ONSITE
    return WORK_UNKNOWN


def experience_hint(title: str, description: str = "") -> str:
    t = title.lower()
    if re.search(r"\b(intern|internship|graduate|entry[- ]level|junior|jr\.?|apprentice|trainee|associate)\b", t):
        return "entry"
    if re.search(r"\b(senior|sr\.?|staff|principal|lead|head of|director|vp|architect|distinguished)\b", t):
        return "senior"
    if re.search(r"\b(mid[- ]level|intermediate|ii)\b", t):
        return "mid"
    m = re.search(r"(\d{1,2})\s*\+?\s*(?:-|to)?\s*(?:\d{1,2})?\s*\+?\s*years", description.lower())
    if m:
        years = int(m.group(1))
        if years <= 1:
            return "entry"
        if years <= 4:
            return "mid"
        return "senior"
    return "unknown"


def make_job(
    *,
    provider: str,
    tier: int,
    provider_job_id: Any,
    title: str | None,
    company: str | None,
    location: str | None = None,
    country: str | None = None,
    work_arrangement: str | None = None,
    remote_scope: str | None = None,
    description_html: str | None = None,
    description_text: str | None = None,
    salary: str | None = None,
    published_at: Any = None,
    apply_url: str | None = None,
    source_url: str | None = None,
    source_name: str | None = None,
    board: str | None = None,
    extra_skills: list[str] | None = None,
) -> dict[str, Any] | None:
    """Build one job in the common schema, or None if required fields are missing."""
    title = (title or "").strip()
    company = (company or "").strip()
    if not title or not company or provider_job_id in (None, ""):
        return None
    description = description_text if description_text is not None else strip_html(description_html)
    description = strip_html(description) if description and "<" in description else (description or "")
    location = (location or "").strip() or None
    arrangement = work_arrangement if work_arrangement in (WORK_REMOTE, WORK_HYBRID, WORK_ONSITE) else \
        detect_work_arrangement(location, title)
    cc = (country or "").upper() or None
    if cc and len(cc) != 2:
        cc = country_from_location(country)
    if not cc:
        cc = country_from_location(location)
    eligible: list[str] = []
    if arrangement == WORK_REMOTE:
        eligible = countries_in_text(remote_scope or location)
        if not eligible and cc:
            eligible = [cc]
    skills = extract_skills(title, description)
    for s in extra_skills or []:
        if s not in skills:
            skills.append(s)
    published = to_iso(published_at)
    stamp = now_iso()
    return {
        "job_key": f"{provider}:{provider_job_id}",
        "provider": provider,
        "provider_job_id": str(provider_job_id),
        "tier": tier,
        "source_name": source_name or provider,
        "board": board,
        "title": title[:300],
        "company": company[:200],
        "location": location[:300] if location else None,
        "country": cc,
        "work_arrangement": arrangement,
        "remote_eligible_countries": eligible,
        "description": description,
        "experience_hint": experience_hint(title, description),
        "salary": salary or None,
        "published_at": published,
        "retrieved_at": stamp,
        "last_seen_at": stamp,
        "apply_url": safe_url(apply_url) or safe_url(source_url),
        "source_url": safe_url(source_url) or safe_url(apply_url),
        "skills": skills,
        "visa_sponsor_signal": "none",
        "duplicate_of": None,
        "closed": False,
    }


def safe_url(url: str | None) -> str | None:
    """Only https links are published; anything else is dropped."""
    if not url:
        return None
    url = str(url).strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not url.startswith("https://") or any(c in url for c in " \n\r\t<>\"'"):
        return None
    return url[:2000]


def salary_text(minimum: Any, maximum: Any, currency: str | None = None, period: str | None = None) -> str | None:
    def fmt(v: Any) -> str | None:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        if f <= 0:
            return None
        return f"{f:,.0f}"

    lo, hi = fmt(minimum), fmt(maximum)
    if not lo and not hi:
        return None
    rng = f"{lo}–{hi}" if lo and hi and lo != hi else (lo or hi)
    parts = [currency or "", rng or "", f"/ {period}" if period else ""]
    return " ".join(p for p in parts if p).strip()
