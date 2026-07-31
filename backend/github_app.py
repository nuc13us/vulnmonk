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

# ── Runtime config dict — populated from env at module load then optionally
#    overridden from the database (see reload_config / reload_config_from_db).
_config: dict = {
    "app_id": "",
    "private_key": None,  # cryptography RSAPrivateKey object or None
    "webhook_secret": "",
    "slug": "",
}


def _parse_pem(pem_text: str):
    """Parse RSAPrivateKey from a PEM string.  Returns None if empty."""
    if not pem_text:
        return None
    pem_bytes = pem_text.strip().replace("\\n", "\n").encode()
    try:
        return load_pem_private_key(pem_bytes, password=None)
    except Exception as e:
        raise RuntimeError(f"Failed to parse GitHub App private key: {e}")


def _load_private_key_from_env():
    """Return a cryptography RSAPrivateKey from GITHUB_APP_PRIVATE_KEY env var.

    The value may be a file path (e.g. backend/vulnmonk.private-key.pem)
    or a raw/inline PEM string.
    """
    raw = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate.startswith("-----"):
        # Treat as a file path; resolve relative paths from the repo root.
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pem_path = candidate if os.path.isabs(candidate) else os.path.join(base, candidate)
        try:
            with open(pem_path, "rb") as f:
                pem_bytes = f.read()
        except OSError as e:
            raise RuntimeError(f"Could not read GITHUB_APP_PRIVATE_KEY file '{pem_path}': {e}")
        try:
            return load_pem_private_key(pem_bytes, password=None)
        except Exception as e:
            raise RuntimeError(f"Failed to parse GitHub App private key from file: {e}")
    return _parse_pem(candidate)


# ── Initialise from environment variables ────────────────────────────────────
_config["app_id"] = os.getenv("GITHUB_APP_ID", "")
_config["private_key"] = _load_private_key_from_env()
_config["webhook_secret"] = os.getenv("GITHUB_APP_WEBHOOK_SECRET", "")
_config["slug"] = os.getenv("GITHUB_APP_SLUG", "")


def reload_config(
    app_id: str = "",
    slug: str = "",
    private_key_pem: str = "",
    webhook_secret: str = "",
) -> None:
    """Override runtime config with values (typically loaded from the database).

    Only fields with a non-empty value are updated so that env-var defaults
    remain in place for any field not yet configured via the UI.
    """
    if app_id:
        _config["app_id"] = app_id
    if slug:
        _config["slug"] = slug
    if webhook_secret:
        _config["webhook_secret"] = webhook_secret
    if private_key_pem:
        _config["private_key"] = _parse_pem(private_key_pem)


def is_configured() -> bool:
    """Return True if the minimum App credentials are present."""
    return bool(_config["app_id"] and _config["private_key"])


def get_slug() -> str:
    """Return the configured App slug."""
    return _config["slug"]


def get_app_jwt() -> str:
    """
    Mint a short-lived JWT (10 min) signed with the App's RSA private key.
    Used to authenticate as the GitHub App itself.
    """
    pk = _config["private_key"]
    if not pk:
        raise ValueError(
            "GITHUB_APP_PRIVATE_KEY is not set or could not be loaded. "
            "Configure it in Settings → GitHub App Credentials or set it in .env."
        )
    now = int(time.time())
    payload = {
        "iat": now - 60,   # 1 min in the past to absorb clock skew
        "exp": now + 600,  # 10-minute window
        "iss": _config["app_id"],
    }
    return jwt.encode(payload, pk, algorithm="RS256")


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
    secret = _config["webhook_secret"]
    if not secret:
        return True  # dev / no-secret mode
    expected = "sha256=" + _hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return _hmac.compare_digest(expected, sig_header or "")


def get_install_url(target_type: str = "") -> str:
    """URL that opens the GitHub App installation page for a new org/account.

    Args:
        target_type: Optional filter — pass "Organization" to show only org
                     accounts on the GitHub picker page.
    """
    base = f"https://github.com/apps/{_config['slug']}/installations/new"
    if target_type:
        return f"{base}?target_type={target_type}"
    return base
