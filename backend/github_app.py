"""
GitHub App authentication helpers.

Handles:
- App JWT generation (signed with the App's RSA private key)
- Installation access token exchange (short-lived, auto-rotated)
- Webhook signature verification using the configured app secret

GitHub App credentials are sourced exclusively from the database / UI, never from .env.
"""

import hashlib
import hmac as _hmac
import time

import requests
from jose import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key

_config: dict = {
    "app_id": "",
    "private_key": None,
    "webhook_secret": "",
    "slug": "",
}


def _parse_pem(pem_text: str):
    """Parse RSAPrivateKey from a PEM string. Returns None if empty."""
    if not pem_text:
        return None
    pem_bytes = pem_text.strip().replace("\\n", "\n").encode()
    try:
        return load_pem_private_key(pem_bytes, password=None)
    except Exception as e:
        raise RuntimeError(f"Failed to parse GitHub App private key: {e}")


def _runtime_config_from_values(app_id: str = "", slug: str = "", private_key_pem: str = "", webhook_secret: str = "") -> dict:
    return {
        "app_id": app_id,
        "slug": slug,
        "private_key": _parse_pem(private_key_pem) if private_key_pem else None,
        "webhook_secret": webhook_secret,
    }


def reload_config(
    app_id: str = "",
    slug: str = "",
    private_key_pem: str = "",
    webhook_secret: str = "",
) -> None:
    """Override runtime config with values loaded from the database/UI."""
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


def get_app_jwt(app_id: str | None = None, private_key=None) -> str:
    """Mint a short-lived JWT (10 min) signed with the App's RSA private key."""
    pk = private_key if private_key is not None else _config["private_key"]
    iss = app_id if app_id is not None else _config["app_id"]
    if not pk:
        raise ValueError("GitHub App private key is not configured. Save it on the Integrations page.")
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": iss,
    }
    return jwt.encode(payload, pk, algorithm="RS256")


def get_installation_token(installation_id: int, app_config: dict | None = None) -> str:
    """Exchange an App JWT for an installation access token (valid 1 hour)."""
    cfg = app_config or _config
    app_jwt = get_app_jwt(app_id=cfg.get("app_id"), private_key=cfg.get("private_key"))
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


def verify_webhook_signature(body: bytes, sig_header: str, webhook_secret: str | None = None) -> bool:
    """Verify the X-Hub-Signature-256 header sent by GitHub."""
    secret = webhook_secret if webhook_secret is not None else _config["webhook_secret"]
    if not secret:
        return True
    expected = "sha256=" + _hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return _hmac.compare_digest(expected, sig_header or "")


def get_install_url(target_type: str = "", app_config: dict | None = None) -> str:
    """URL that opens the GitHub App installation page for a new org/account."""
    cfg = app_config or _config
    slug = cfg.get("slug") or _config.get("slug")
    if not slug:
        raise ValueError("GitHub App slug is not configured. Save it on the Integrations page.")
    base = f"https://github.com/apps/{slug}/installations/new"
    if target_type:
        return f"{base}?target_type={target_type}"
    return base
