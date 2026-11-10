"""Low-level HTTP helper with the failover rules from Architecture v7.1 Section 6.

Adapters build their own requests and parse their own responses; this module only
turns transport outcomes into typed errors so every adapter reports status the same way.
Keys are never logged: URLs are redacted before they appear in any message.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import requests

USER_AGENT = "DossierJobsPipeline/1.0 (+https://github.com/; public job listings fetcher)"
DEFAULT_TIMEOUT = (10, 45)  # connect, read seconds
MAX_BYTES = 60 * 1024 * 1024  # refuse responses above 60 MB


class SourceError(Exception):
    """Base class. `status` is the label shown in the health report."""

    status = "Provider error"

    def __init__(self, message: str = "", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class MissingKey(SourceError):
    status = "Missing key"


class InvalidKey(SourceError):
    status = "Invalid key"


class BoardNotFound(SourceError):
    status = "Board not found"


class RateLimited(SourceError):
    status = "Rate limited"


class QuotaExhausted(SourceError):
    status = "Quota exhausted"


class TemporarilyUnavailable(SourceError):
    status = "Temporarily unavailable"


class ProviderError(SourceError):
    status = "Provider error"


class InvalidResponse(SourceError):
    status = "Could not read response"


class NotCovered(SourceError):
    status = "Not covered"


_SECRET_PARAMS = re.compile(r"(app_key|app_id|api_key|apikey|key|token|affid)=([^&]+)", re.I)


def redact(url: str) -> str:
    url = _SECRET_PARAMS.sub(lambda m: f"{m.group(1)}=***", url)
    # Jooble puts the key in the path: /api/<key>
    return re.sub(r"(jooble\.org/api/)[^/?]+", r"\1***", url)


@dataclass
class Budget:
    """Per-provider request counter so a run never exceeds the registry's daily quota."""

    limit: int | None
    used: int = 0

    def take(self) -> None:
        if self.limit is not None and self.used >= self.limit:
            raise QuotaExhausted("Run budget reached")
        self.used += 1


_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, */*;q=0.5"})


def request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    auth: tuple[str, str] | None = None,
    retries: int = 2,
    polite_delay: float = 0.4,
    budget: Budget | None = None,
    expect: str = "json",
) -> Any:
    """Perform a request and return parsed JSON (or text when expect='text').

    Retries only on timeouts, network errors and 5xx. Never retries 401/403/404/429.
    """
    attempt = 0
    while True:
        if budget:
            budget.take()
        attempt += 1
        try:
            resp = _session.request(
                method,
                url,
                params=params,
                headers=headers,
                json=json_body,
                auth=auth,
                timeout=DEFAULT_TIMEOUT,
                stream=True,
            )
            content = _read_limited(resp)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt <= retries:
                time.sleep(1.5 * attempt)
                continue
            raise TemporarilyUnavailable(f"{type(exc).__name__} for {redact(url)}") from None
        finally:
            time.sleep(polite_delay)

        code = resp.status_code
        if code in (401, 403):
            raise InvalidKey(f"HTTP {code}")
        if code == 404:
            raise BoardNotFound("HTTP 404")
        if code == 429:
            raise RateLimited("HTTP 429", retry_after=_retry_after(resp))
        if 500 <= code < 600:
            if attempt <= retries:
                time.sleep(2.0 * attempt)
                continue
            raise ProviderError(f"HTTP {code}")
        if code >= 400:
            raise ProviderError(f"HTTP {code}")

        if expect == "text":
            return content.decode(resp.encoding or "utf-8", errors="replace")
        try:
            import json

            return json.loads(content.decode("utf-8", errors="replace"))
        except ValueError:
            raise InvalidResponse("Response was not valid JSON") from None


def get(url: str, **kw: Any) -> Any:
    return request("GET", url, **kw)


def post(url: str, **kw: Any) -> Any:
    return request("POST", url, **kw)


def _read_limited(resp: requests.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in resp.iter_content(64 * 1024):
        total += len(chunk)
        if total > MAX_BYTES:
            resp.close()
            raise InvalidResponse("Response larger than the size limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _retry_after(resp: requests.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
