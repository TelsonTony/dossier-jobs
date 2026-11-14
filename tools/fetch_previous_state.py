"""Downloads the previous run's state from the published site (used by the GitLab pipeline, where
there is no gh-pages branch to check out).

    python tools/fetch_previous_state.py "$CI_PAGES_URL" previous

Never fails the run: if the state can't be fetched (first run, site not public yet, network),
the pipeline starts fresh and publish.py picks a version above any earlier one.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import requests

MAX_BYTES = 200 * 1024 * 1024


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 0
    base, out = sys.argv[1].strip(), Path(sys.argv[2])
    target = out / "state" / "state.json.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not base.startswith("https://"):
        print("No https site address; starting fresh")
        return 0
    url = base.rstrip("/") + "/state/state.json.gz"
    try:
        r = requests.get(url, timeout=(10, 60), stream=True, allow_redirects=False)
        if r.status_code != 200:
            print(f"Previous state not available (HTTP {r.status_code}); starting fresh")
            return 0
        data = bytearray()
        for chunk in r.iter_content(256 * 1024):
            data += chunk
            if len(data) > MAX_BYTES:
                print("Previous state too large; starting fresh")
                return 0
        state = json.loads(gzip.decompress(bytes(data)))
        if not isinstance(state, dict):
            raise ValueError("unexpected state format")
        target.write_bytes(bytes(data))
        print(f"Previous state loaded: version {state.get('version')}, {len(state.get('jobs') or {})} jobs")
    except Exception as exc:  # noqa: BLE001 — never block the run
        print(f"Previous state not loaded ({type(exc).__name__}); starting fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
