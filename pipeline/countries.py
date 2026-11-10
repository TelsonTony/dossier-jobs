"""Country normalisation: free-text locations -> ISO 3166-1 alpha-2 codes.

Only what a location string clearly states is used. Anything unclear stays unknown,
because a filter must never claim a match the data cannot support.
"""
from __future__ import annotations

import re

COUNTRY_NAMES: dict[str, str] = {
    # Asia-Pacific
    "india": "IN", "singapore": "SG", "australia": "AU", "new zealand": "NZ", "japan": "JP",
    "south korea": "KR", "korea": "KR", "china": "CN", "hong kong": "HK", "taiwan": "TW",
    "philippines": "PH", "indonesia": "ID", "malaysia": "MY", "vietnam": "VN", "thailand": "TH",
    "pakistan": "PK", "bangladesh": "BD", "sri lanka": "LK", "nepal": "NP",
    # Middle East and GCC
    "united arab emirates": "AE", "uae": "AE", "saudi arabia": "SA", "ksa": "SA", "qatar": "QA",
    "kuwait": "KW", "bahrain": "BH", "oman": "OM", "israel": "IL", "turkey": "TR", "türkiye": "TR",
    "jordan": "JO",
    # Europe
    "united kingdom": "GB", "uk": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "northern ireland": "GB", "great britain": "GB", "ireland": "IE", "germany": "DE",
    "deutschland": "DE", "france": "FR", "spain": "ES", "portugal": "PT", "italy": "IT",
    "netherlands": "NL", "the netherlands": "NL", "belgium": "BE", "luxembourg": "LU",
    "switzerland": "CH", "austria": "AT", "sweden": "SE", "norway": "NO", "denmark": "DK",
    "finland": "FI", "iceland": "IS", "poland": "PL", "czech republic": "CZ", "czechia": "CZ",
    "slovakia": "SK", "hungary": "HU", "romania": "RO", "bulgaria": "BG", "greece": "GR",
    "croatia": "HR", "serbia": "RS", "slovenia": "SI", "estonia": "EE", "latvia": "LV",
    "lithuania": "LT", "ukraine": "UA", "cyprus": "CY", "malta": "MT",
    # Americas
    "united states": "US", "united states of america": "US", "usa": "US", "us": "US",
    "canada": "CA", "mexico": "MX", "brazil": "BR", "argentina": "AR", "chile": "CL",
    "colombia": "CO", "peru": "PE", "uruguay": "UY", "costa rica": "CR",
    # Africa
    "south africa": "ZA", "nigeria": "NG", "kenya": "KE", "egypt": "EG", "morocco": "MA",
    "ghana": "GH", "rwanda": "RW", "tunisia": "TN",
}

CITIES: dict[str, str] = {
    "bengaluru": "IN", "bangalore": "IN", "mumbai": "IN", "pune": "IN", "hyderabad": "IN",
    "chennai": "IN", "delhi": "IN", "new delhi": "IN", "gurgaon": "IN", "gurugram": "IN",
    "noida": "IN", "kochi": "IN", "trivandrum": "IN", "thiruvananthapuram": "IN", "kolkata": "IN",
    "ahmedabad": "IN", "london": "GB", "manchester": "GB", "edinburgh": "GB", "cambridge, uk": "GB",
    "bristol": "GB", "leeds": "GB", "glasgow": "GB", "belfast": "GB", "birmingham, uk": "GB",
    "dublin": "IE", "cork": "IE", "berlin": "DE", "munich": "DE", "münchen": "DE",
    "hamburg": "DE", "frankfurt": "DE", "cologne": "DE", "köln": "DE", "stuttgart": "DE",
    "paris": "FR", "lyon": "FR", "madrid": "ES", "barcelona": "ES", "lisbon": "PT", "porto": "PT",
    "milan": "IT", "rome": "IT", "amsterdam": "NL", "rotterdam": "NL", "brussels": "BE",
    "zurich": "CH", "zürich": "CH", "geneva": "CH", "vienna": "AT", "stockholm": "SE",
    "oslo": "NO", "copenhagen": "DK", "helsinki": "FI", "warsaw": "PL", "krakow": "PL",
    "kraków": "PL", "prague": "CZ", "budapest": "HU", "bucharest": "RO", "athens": "GR",
    "tallinn": "EE", "kyiv": "UA", "dubai": "AE", "abu dhabi": "AE", "riyadh": "SA",
    "doha": "QA", "tel aviv": "IL", "istanbul": "TR", "tokyo": "JP", "seoul": "KR",
    "sydney": "AU", "melbourne": "AU", "brisbane": "AU", "auckland": "NZ", "toronto": "CA",
    "vancouver": "CA", "montreal": "CA", "ottawa": "CA", "mexico city": "MX", "são paulo": "BR",
    "sao paulo": "BR", "buenos aires": "AR", "bogotá": "CO", "bogota": "CO", "santiago": "CL",
    "cape town": "ZA", "johannesburg": "ZA", "lagos": "NG", "nairobi": "KE", "cairo": "EG",
    "new york": "US", "nyc": "US", "san francisco": "US", "seattle": "US", "austin": "US",
    "boston": "US", "chicago": "US", "los angeles": "US", "denver": "US", "atlanta": "US",
    "miami": "US", "washington, dc": "US", "washington dc": "US", "palo alto": "US",
    "mountain view": "US", "menlo park": "US", "sunnyvale": "US", "san jose": "US",
    "san mateo": "US", "oakland": "US", "portland": "US", "salt lake city": "US",
    "philadelphia": "US", "pittsburgh": "US", "dallas": "US", "houston": "US", "phoenix": "US",
    "san diego": "US", "foster city": "US", "redwood city": "US", "lehi": "US",
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
}

EUROPE = ["GB", "IE", "DE", "FR", "ES", "PT", "IT", "NL", "BE", "LU", "CH", "AT", "SE", "NO",
          "DK", "FI", "IS", "PL", "CZ", "SK", "HU", "RO", "BG", "GR", "HR", "RS", "SI", "EE",
          "LV", "LT", "UA", "CY", "MT"]
EU = [c for c in EUROPE if c not in ("GB", "CH", "NO", "IS", "UA", "RS")]

REGIONS: dict[str, list[str]] = {
    "worldwide": ["WORLDWIDE"], "anywhere": ["WORLDWIDE"], "global": ["WORLDWIDE"],
    "remote - global": ["WORLDWIDE"], "international": ["WORLDWIDE"],
    "europe": EUROPE, "emea": EUROPE + ["AE", "SA", "QA", "IL", "ZA", "EG", "NG", "KE"],
    "eu": EU, "european union": EU, "dach": ["DE", "AT", "CH"],
    "nordics": ["SE", "NO", "DK", "FI", "IS"], "benelux": ["BE", "NL", "LU"],
    "north america": ["US", "CA"], "americas": ["US", "CA", "MX", "BR", "AR", "CL", "CO", "PE", "UY", "CR"],
    "latam": ["MX", "BR", "AR", "CL", "CO", "PE", "UY", "CR"], "latin america": ["MX", "BR", "AR", "CL", "CO", "PE", "UY", "CR"],
    "apac": ["IN", "SG", "AU", "NZ", "JP", "KR", "CN", "HK", "TW", "PH", "ID", "MY", "VN", "TH"],
    "asia": ["IN", "SG", "JP", "KR", "CN", "HK", "TW", "PH", "ID", "MY", "VN", "TH"],
    "gcc": ["AE", "SA", "QA", "KW", "BH", "OM"], "middle east": ["AE", "SA", "QA", "KW", "BH", "OM", "IL", "JO"],
    "africa": ["ZA", "NG", "KE", "EG", "MA", "GH", "RW", "TN"],
}

ISO_CODES = set(COUNTRY_NAMES.values())

_word_cache: dict[str, re.Pattern[str]] = {}


def _has(text: str, phrase: str) -> bool:
    pat = _word_cache.get(phrase)
    if pat is None:
        pat = re.compile(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", re.I)
        _word_cache[phrase] = pat
    return bool(pat.search(text))


def country_from_location(location: str | None) -> str | None:
    """Return one ISO code if the location clearly names one country, else None."""
    if not location:
        return None
    text = location.strip()
    low = text.lower()
    found: set[str] = set()
    for name, code in COUNTRY_NAMES.items():
        if len(name) <= 3:
            # Short tokens (UK, US, USA, UAE) must appear as whole upper-case words.
            if re.search(r"(?<![A-Za-z])" + re.escape(name.upper()) + r"(?![A-Za-z])", text):
                found.add(code)
        elif _has(low, name):
            found.add(code)
    for city, code in CITIES.items():
        if _has(low, city):
            found.add(code)
    # "Austin, TX" style US locations
    m = re.search(r",\s*([A-Z]{2})(?:\b|$)", text)
    if m and m.group(1) in US_STATES and not found - {"US"}:
        found.add("US")
    if len(found) == 1:
        return found.pop()
    return None


def countries_in_text(text: str | None) -> list[str]:
    """All countries and regions named in a remote-eligibility string."""
    if not text:
        return []
    low = text.lower()
    out: list[str] = []
    for region, codes in REGIONS.items():
        if _has(low, region):
            out.extend(codes)
    for name, code in COUNTRY_NAMES.items():
        if len(name) <= 3:
            if re.search(r"(?<![A-Za-z])" + re.escape(name.upper()) + r"(?![A-Za-z])", text):
                out.append(code)
        elif _has(low, name):
            out.append(code)
    for city, code in CITIES.items():
        if _has(low, city):
            out.append(code)
    seen: list[str] = []
    for c in out:
        if c not in seen:
            seen.append(c)
    if "WORLDWIDE" in seen:
        return ["WORLDWIDE"]
    return seen
