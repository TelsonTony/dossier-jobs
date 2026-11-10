"""Generates the Ed25519 signing key pair for the job files. Run it ONCE, on your own computer.

    python tools/generate_signing_key.py

It prints:
  * PRIVATE seed -> paste into the GitHub Actions secret DOSSIER_SIGNING_KEY, then delete it
    from your screen/clipboard. Never commit it.
  * PUBLIC key   -> goes into the app build (--dart-define=DOSSIER_PUBKEY_K1=...).

Key rotation: generate a second pair, ship its public key in the app as K2 first, then switch
the secret and set DOSSIER_SIGNING_KEY_ID=k2.
"""
from __future__ import annotations

import base64

from nacl.signing import SigningKey

key = SigningKey.generate()
seed = base64.b64encode(bytes(key)).decode()
pub = base64.b64encode(bytes(key.verify_key)).decode()
print("=" * 72)
print("PRIVATE seed  (GitHub secret DOSSIER_SIGNING_KEY — keep secret, never commit):")
print(seed)
print()
print("PUBLIC key    (app build: --dart-define=DOSSIER_PUBKEY_K1=...):")
print(pub)
print("=" * 72)
