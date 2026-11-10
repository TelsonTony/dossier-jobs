"""Skills extraction from job text using data/skills.json.

The same dictionary and the same matching rule are used by the app
(dossier-app/assets/skills.json), so pipeline skills and phone matching agree:
  * whole-word match;
  * names or aliases of 3 characters or fewer, or entries with "cs": true,
    match case-sensitively (so "Go" does not match "go to market").
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

SKILLS_PATH = Path(__file__).resolve().parent.parent / "data" / "skills.json"


@lru_cache(maxsize=1)
def _matchers() -> tuple[re.Pattern[str], dict[str, str], re.Pattern[str], dict[str, str], list[str]]:
    """Two combined patterns (case-insensitive and case-sensitive) so each text is scanned once."""
    data = json.loads(SKILLS_PATH.read_text(encoding="utf-8"))
    ci: dict[str, str] = {}
    cs: dict[str, str] = {}
    order: list[str] = []
    for entry in data["skills"]:
        name = entry["name"]
        order.append(name)
        for term in [name, *entry.get("aliases", [])]:
            if entry.get("cs", False) or len(term) <= 3:
                cs.setdefault(term, name)
            else:
                ci.setdefault(term.lower(), name)

    def build(terms: list[str], flags: int) -> re.Pattern[str]:
        alt = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
        return re.compile(r"(?<![\w+#.])(?:" + alt + r")(?![\w+#]|\.\w)", flags)

    return build(list(ci), re.I), ci, build(list(cs), 0), cs, order


def extract_skills(*texts: str | None, limit: int = 25) -> list[str]:
    blob = "\n".join(t for t in texts if t)
    if not blob:
        return []
    ci_pat, ci, cs_pat, cs, order = _matchers()
    found = {ci[m.lower()] for m in ci_pat.findall(blob) if m.lower() in ci}
    found |= {cs[m] for m in cs_pat.findall(blob) if m in cs}
    # Dictionary order keeps output stable between runs.
    return [n for n in order if n in found][:limit]
