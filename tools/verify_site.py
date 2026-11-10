"""Checks a published site the same way the app does: signature, index hash, description hashes.

    python tools/verify_site.py --public-key <base64> [--url https://<user>.github.io/dossier-jobs/]
    python tools/verify_site.py --public-key <base64> --dir site
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.sign import verify_manifest  # noqa: E402


def fetch(base: str | None, folder: Path | None, rel: str) -> bytes:
    if folder:
        return (folder / rel).read_bytes()
    import requests

    r = requests.get(base.rstrip("/") + "/" + rel, timeout=30)
    r.raise_for_status()
    return r.content


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--public-key", required=True)
    ap.add_argument("--key-id", default="k1")
    ap.add_argument("--url")
    ap.add_argument("--dir")
    ap.add_argument("--sample", type=int, default=25, help="description files to check")
    a = ap.parse_args()
    folder = Path(a.dir) if a.dir else None
    if not folder and not a.url:
        ap.error("give --url or --dir")
    manifest = fetch(a.url, folder, "manifest.json")
    sig = fetch(a.url, folder, "manifest.sig")
    if not verify_manifest(manifest, sig, {a.key_id: a.public_key}):
        print("FAIL: manifest signature does not verify with this public key")
        return 1
    m = json.loads(manifest)
    index = fetch(a.url, folder, m["index"]["path"])
    if hashlib.sha256(index).hexdigest() != m["index"]["sha256"]:
        print("FAIL: jobs_index hash does not match the manifest")
        return 1
    jobs = json.loads(gzip.decompress(index))["jobs"]
    bad = 0
    for job in random.sample(jobs, min(a.sample, len(jobs))):
        blob = fetch(a.url, folder, job["desc"])
        if hashlib.sha256(blob).hexdigest() != job["desc_sha256"]:
            bad += 1
    if bad:
        print(f"FAIL: {bad} description files do not match their hash")
        return 1
    print(f"OK: version {m['version']}, {m['open_count']} open jobs, index {len(index) / 1024:.0f} KB, "
          f"signature and hashes verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
