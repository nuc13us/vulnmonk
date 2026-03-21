"""
GitHub App authentication helpers.

Handles:
- App JWT generation (signed with the App's RSA private key)
- Installation access token exchange (short-lived, auto-rotated)
- Webhook signature verification (single App-level secret)
"""

import hashlib
import hmac as _hmac
import os
import time

import requests
from jose import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# ── Env vars set when you create your GitHub App ──────────────────────────────
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")

# Private key: value may be a file path (e.g. backend/vulnmonk.private-key.pem)
# or a raw PEM string (with literal \n line separators).
_raw_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "")

def _load_private_key():
    """Return a cryptography RSAPrivateKey object, or None if not configured."""
    if not _raw_key:
        return None
    # If the value looks like a file path, read the PEM from disk.
    candidate = _raw_key.strip()
    if not candidate.startswith("-----"):
        # Treat as a file path; resolve relative paths from the repo root
        # (one directory above this file).
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pem_path = candidate if os.path.isabs(candidate) else os.path.join(base, candidate)
        try:
            with open(pem_path, "rb") as f:
                pem_bytes = f.read()
        except OSError as e:
            raise RuntimeError(f"Could not read GITHUB_APP_PRIVATE_KEY file '{pem_path}': {e}")
    else:
        # Inline PEM — normalise literal \n escapes
        pem_bytes = candidate.replace("\\n", "\n").encode()
    try:
        return load_pem_private_key(pem_bytes, password=None)
    except Exception as e:
        raise RuntimeError(f"Failed to parse GitHub App private key: {e}")

GITHUB_APP_PRIVATE_KEY = _load_private_key()

GITHUB_APP_WEBHOOK_SECRET = os.getenv("GITHUB_APP_WEBHOOK_SECRET", "")
GITHUB_APP_SLUG = os.getenv("GITHUB_APP_SLUG", "")  # e.g. "vulnmonk"


def is_configured() -> bool:
    """Return True if the minimum App credentials are present."""
    return bool(GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY)


def get_app_jwt() -> str:
    """
    Mint a short-lived JWT (10 min) signed with the App's RSA private key.
    Used to authenticate as the GitHub App itself.
    """
    if not GITHUB_APP_PRIVATE_KEY:
        raise ValueError(
            "GITHUB_APP_PRIVATE_KEY is not set or could not be loaded. "
            "Check that the value in .env is a valid PEM private key."
        )
    now = int(time.time())
    payload = {
        "iat": now - 60,   # 1 min in the past to absorb clock skew
        "exp": now + 600,  # 10-minute window
        "iss": GITHUB_APP_ID,
    }
    return jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm="RS256")


def get_installation_token(installation_id: int) -> str:
    """
    Exchange an App JWT for an installation access token (valid 1 hour).
    Call this on every operation — tokens are cheap to mint and avoid
    the need to cache rotating secrets.
    """
    app_jwt = get_app_jwt()
    resp = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def verify_webhook_signature(body: bytes, sig_header: str) -> bool:
    """
    Verify the X-Hub-Signature-256 header sent by GitHub.
    Returns True if the signature is valid (or if no secret is configured,
    which allows unsigned local dev).
    """
    secret = GITHUB_APP_WEBHOOK_SECRET
    if not secret:
        return True  # dev / no-secret mode
    expected = "sha256=" + _hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return _hmac.compare_digest(expected, sig_header or "")


def get_install_url() -> str:
    """URL that opens the GitHub App installation page for a new org/account."""
    return f"https://github.com/apps/{GITHUB_APP_SLUG}/installations/new"
