"""Checks whether a public key (DOSSIER_PUBKEY_K1) matches the job data that is live right now.

    python tools/check_pubkey.py <PUBLIC_KEY> [JOBS_URL]

JOBS_URL defaults to https://telsontony.github.io/dossier-jobs/
It downloads manifest.json + manifest.sig and verifies the signature with the given key,
exactly as the app does. Use the PUBLIC key only; never pass the private DOSSIER_SIGNING_KEY.
"""
from __future__ import annotations

import base64
import binascii
import json
import sys
import urllib.request

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

DEFAULT_URL = "https://telsontony.github.io/dossier-jobs/"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "dossier-key-check"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    key = sys.argv[1].strip()
    base = sys.argv[2].strip() if len(sys.argv) > 2 else DEFAULT_URL
    if not base.endswith("/"):
        base += "/"

    if len(key) != 44:
        print(f"FAIL: the key is {len(key)} characters; a public key is always 44.")
        return 1
    try:
        raw = base64.b64decode(key, validate=True)
    except binascii.Error:
        print("FAIL: the key is not valid base64. Copy it again exactly.")
        return 1
    if len(raw) != 32:
        print("FAIL: the key does not decode to 32 bytes.")
        return 1

    try:
        manifest = fetch(base + "manifest.json")
        sig = json.loads(fetch(base + "manifest.sig"))
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: could not download job data from {base} ({e}).")
        return 1

    try:
        VerifyKey(raw).verify(manifest, base64.b64decode(sig["sig"]))
    except BadSignatureError:
        print("FAIL: this key does NOT match the live job data. An APK built with it would show no jobs.")
        print("      Copy the key from the latest Fetch jobs run log (Run pipeline step).")
        return 1

    run_at = json.loads(manifest).get("run_at", "?")
    print(f"OK: key matches the live job data (key id '{sig.get('key_id')}', data from {run_at}).")
    print("    Use it as DOSSIER_PUBKEY_K1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
