"""Slack notification helper for VulnMonk."""

import logging

import requests

logger = logging.getLogger("vulnmonk.slack")


def send_slack_message(webhook_url: str, text: str) -> bool:
    """POST a plain-text message to a Slack incoming webhook. Returns True on success."""
    if not webhook_url or not webhook_url.strip():
        return False
    try:
        resp = requests.post(
            webhook_url.strip(),
            json={"text": text},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning(
                "Slack notification failed (HTTP %d): %s", resp.status_code, resp.text
            )
            return False
        return True
    except Exception as exc:
        logger.warning("Slack notification error: %s", exc)
        return False


def get_slack_config(db) -> dict:
    """Return {webhook_url, enabled} from GlobalConfiguration."""
    from . import crud

    webhook = crud.get_global_config(db, "slack_webhook_url")
    enabled = crud.get_global_config(db, "slack_enabled")
    return {
        "webhook_url": webhook.value if webhook else "",
        "enabled": (enabled.value == "1") if enabled else False,
    }


def should_notify(project, db) -> tuple[bool, str]:
    """Return (should_send, webhook_url) for a given project.

    Resolution (mirrors scheduled_scan_enabled pattern):
    - project.slack_notify_enabled == 0   → never notify
    - project.slack_notify_enabled == 1   → always notify (if webhook set)
    - project.slack_notify_enabled is None → inherit global enabled
    """
    cfg = get_slack_config(db)
    webhook_url = cfg["webhook_url"]
    if not webhook_url:
        return False, ""

    val = project.slack_notify_enabled
    if val == 0:
        return False, ""
    elif val == 1:
        return True, webhook_url
    else:
        # None = inherit global setting
        return cfg["enabled"], webhook_url
