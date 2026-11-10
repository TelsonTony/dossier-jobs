"""Ed25519 signing of the manifest.

Chain of trust:
  manifest.sig  --signs-->  manifest.json (exact bytes)
  manifest.json --sha256--> jobs_index.json.gz
  jobs_index    --sha256--> every desc/<id>.json.gz   (field "desc_sha256" on each job)

The private key is a 32-byte seed, base64-encoded, stored only in the GitHub Actions secret
DOSSIER_SIGNING_KEY. The public key is compiled into the app.
"""
from __future__ import annotations

import base64
import hashlib
import json

from nacl.signing import SigningKey, VerifyKey


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_signing_key(seed_b64: str) -> SigningKey:
    seed = base64.b64decode(seed_b64.strip())
    if len(seed) != 32:
        raise ValueError("DOSSIER_SIGNING_KEY must be a base64-encoded 32-byte seed")
    return SigningKey(seed)


def public_key_b64(key: SigningKey) -> str:
    return base64.b64encode(bytes(key.verify_key)).decode()


def sign_manifest(manifest_bytes: bytes, key: SigningKey, key_id: str) -> bytes:
    sig = key.sign(manifest_bytes).signature
    return json.dumps({"alg": "ed25519", "key_id": key_id, "sig": base64.b64encode(sig).decode()},
                      separators=(",", ":")).encode()


def verify_manifest(manifest_bytes: bytes, sig_file: bytes, public_keys: dict[str, str]) -> bool:
    try:
        meta = json.loads(sig_file)
        pub = public_keys.get(meta.get("key_id"))
        if not pub or meta.get("alg") != "ed25519":
            return False
        VerifyKey(base64.b64decode(pub)).verify(manifest_bytes, base64.b64decode(meta["sig"]))
        return True
    except Exception:  # noqa: BLE001 — any failure means "not verified"
        return False
