"""Daily scheduled scans — runs SAST (OpenGrep) and secret (TruffleHog) scans
for every project that has either opted in explicitly or inherits the global
`global_scheduled_scan_enabled` setting.

Scheduling is managed by APScheduler's BackgroundScheduler (runs in a daemon
thread alongside the FastAPI/uvicorn process).  The scan time defaults to
02:00 UTC and can be overridden via the `SCHEDULED_SCAN_HOUR` and
`SCHEDULED_SCAN_MINUTE` environment variables.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import uuid

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("vulnmonk.scheduler")

_scheduler: BackgroundScheduler | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_clone_url(project, db) -> str:
    """Return a clone URL with credentials embedded when possible."""
    from . import crud
    from .github_app import get_installation_token

    clone_url = project.github_url
    if not project.integration_id:
        return clone_url

    integration = crud.get_github_integration(db, project.integration_id)
    if not integration:
        return clone_url

    if integration.installation_id:
        try:
            token = get_installation_token(integration.installation_id)
            if clone_url.startswith("https://github.com/"):
                clone_url = clone_url.replace(
                    "https://github.com/",
                    f"https://x-access-token:{token}@github.com/",
                )
        except Exception as exc:
            logger.warning(
                "Scheduled scan: failed to get installation token for project %d: %s",
                project.id,
                exc,
            )
    elif integration.access_token:
        if clone_url.startswith("https://github.com/"):
            clone_url = clone_url.replace(
                "https://github.com/",
                f"https://{integration.access_token}@github.com/",
            )
    return clone_url


def _merge_exclude_rules(project_rules: str, db) -> str:
    from . import crud

    global_cfg = crud.get_global_config(db, "global_exclude_rules")
    if not (global_cfg and global_cfg.value):
        return project_rules
    proj = [r.strip() for r in project_rules.split(",") if r.strip()]
    glob = [r.strip() for r in global_cfg.value.split(",") if r.strip()]
    return ",".join(set(proj + glob))


def _merge_include_yaml(project_yaml: str, db) -> str:
    from . import crud

    global_cfg = crud.get_global_config(db, "global_include_rules_yaml")
    if not (global_cfg and global_cfg.value):
        return project_yaml
    try:
        proj_files = json.loads(project_yaml) if project_yaml else []
        if not isinstance(proj_files, list):
            proj_files = []
    except (json.JSONDecodeError, ValueError):
        proj_files = []
    try:
        glob_files = json.loads(global_cfg.value)
        if not isinstance(glob_files, list):
            glob_files = []
    except (json.JSONDecodeError, ValueError):
        glob_files = []
    return json.dumps(glob_files + proj_files)


def _merge_th_detectors(project_detectors: str, db) -> str:
    from . import crud

    global_cfg = crud.get_global_config(db, "global_trufflehog_exclude_detectors")
    if not (global_cfg and global_cfg.value):
        return project_detectors
    proj = [d.strip() for d in project_detectors.split(",") if d.strip()]
    glob = [d.strip() for d in global_cfg.value.split(",") if d.strip()]
    return ",".join(set(proj + glob))


# ---------------------------------------------------------------------------
# Per-project scan worker (runs in its own thread per project)
# ---------------------------------------------------------------------------

def _scan_project(project_id: int) -> None:
    """Clone, SAST-scan, and secret-scan a single project."""
    from . import crud, schemas
    from .database import SessionLocal
    from .routes.projects import (
        PROJECTS_ROOT,
        generate_trufflehog_unique_key,
        generate_unique_key,
        run_opengrep_scan,
        run_trufflehog_scan,
        scanning_projects,
        trufflehog_scanning_projects,
    )

    db = SessionLocal()
    temp_path: str | None = None
    try:
        project = crud.get_project(db, project_id)
        if not project:
            return

        logger.info(
            "Scheduled scan: starting project %d (%s)", project.id, project.github_url
        )

        clone_url = _build_clone_url(project, db)
        raw_name = project.github_url.rstrip("/").split("/")[-1].replace(".git", "")
        safe_name = re.sub(r"[^A-Za-z0-9\-]", "-", raw_name)
        uid = str(uuid.uuid4())[:8]
        temp_path = os.path.join(PROJECTS_ROOT, f"temp-sched-{safe_name}-{uid}")

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, temp_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except Exception as exc:
            logger.error(
                "Scheduled scan: clone failed for project %d: %s", project_id, exc
            )
            return

        # ── SAST scan ────────────────────────────────────────────────────────
        if project_id not in scanning_projects:
            scanning_projects.add(project_id)
            try:
                exclude_rules = _merge_exclude_rules(project.exclude_rules or "", db)
                include_yaml = _merge_include_yaml(project.include_rules_yaml or "", db)

                scan_result = run_opengrep_scan(temp_path, exclude_rules, include_yaml)

                if isinstance(scan_result, dict) and "error" not in scan_result:
                    results = scan_result.get("results", [])
                    if isinstance(results, list):
                        for finding in results:
                            finding["unique_key"] = generate_unique_key(finding)
                            finding["status"] = "open"

                    fp_keys = {
                        fp.unique_key
                        for fp in crud.get_false_positives(db, project_id)
                    }
                    raw_count = sum(
                        1
                        for f in (
                            scan_result.get("results", [])
                            if isinstance(scan_result, dict)
                            else []
                        )
                        if generate_unique_key(f) not in fp_keys
                    )
                    scan_obj = schemas.ScanResultCreate(result_json=scan_result)
                    crud.create_scan_result(
                        db=db,
                        scan=scan_obj,
                        project_id=project_id,
                        findings_count=raw_count,
                    )
                    logger.info(
                        "Scheduled SAST scan done for project %d — %d findings",
                        project_id,
                        raw_count,
                    )
                else:
                    logger.error(
                        "Scheduled SAST scan error for project %d: %s",
                        project_id,
                        scan_result.get("error", "unknown"),
                    )
            finally:
                scanning_projects.discard(project_id)

        # ── TruffleHog scan ──────────────────────────────────────────────────
        if project_id not in trufflehog_scanning_projects:
            trufflehog_scanning_projects.add(project_id)
            try:
                exclude_detectors = _merge_th_detectors(
                    project.trufflehog_exclude_detectors or "", db
                )
                th_result = run_trufflehog_scan(temp_path, exclude_detectors)

                if isinstance(th_result, dict) and "error" not in th_result:
                    findings = th_result.get("findings", [])
                    for finding in findings:
                        finding["unique_key"] = generate_trufflehog_unique_key(finding)
                        finding["status"] = "open"

                    fp_keys = {
                        fp.unique_key
                        for fp in crud.get_trufflehog_false_positives(db, project_id)
                    }
                    raw_count = sum(
                        1
                        for f in findings
                        if generate_trufflehog_unique_key(f) not in fp_keys
                    )
                    result_to_store = {
                        "findings": findings,
                        "summary": th_result.get("summary"),
                    }
                    scan_obj = schemas.TrufflehogScanResultCreate(
                        result_json=result_to_store
                    )
                    crud.create_trufflehog_scan_result(
                        db=db,
                        scan=scan_obj,
                        project_id=project_id,
                        findings_count=raw_count,
                    )
                    logger.info(
                        "Scheduled TruffleHog scan done for project %d — %d findings",
                        project_id,
                        raw_count,
                    )
                else:
                    logger.error(
                        "Scheduled TruffleHog scan error for project %d: %s",
                        project_id,
                        th_result.get("error", "unknown"),
                    )
            finally:
                trufflehog_scanning_projects.discard(project_id)

    finally:
        db.close()
        if temp_path and os.path.exists(temp_path):
            shutil.rmtree(temp_path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Scheduler entry point
# ---------------------------------------------------------------------------

def _run_scheduled_scans() -> None:
    """Top-level job called by APScheduler. Dispatches per-project threads."""
    from . import crud
    from .database import SessionLocal

    db = SessionLocal()
    try:
        projects = crud.get_projects_for_scheduled_scan(db)
        logger.info("Scheduled scan: %d project(s) eligible", len(projects))
        project_ids = [p.id for p in projects]
    finally:
        db.close()

    for pid in project_ids:
        t = threading.Thread(
            target=_scan_project,
            args=(pid,),
            daemon=True,
            name=f"scheduled-scan-{pid}",
        )
        t.start()


def start_scheduler() -> BackgroundScheduler:
    """Initialize and start the APScheduler background scheduler."""
    global _scheduler

    scan_hour = int(os.getenv("SCHEDULED_SCAN_HOUR", "6"))
    scan_minute = int(os.getenv("SCHEDULED_SCAN_MINUTE", "0"))

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_scheduled_scans,
        trigger=CronTrigger(hour=scan_hour, minute=scan_minute, timezone="UTC"),
        id="daily_scan",
        name="Daily SAST + TruffleHog Scans",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — daily scans at %02d:%02d UTC", scan_hour, scan_minute
    )
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_next_run_time() -> str | None:
    """Return ISO-formatted next run time, or None if scheduler is not running."""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        return None
    job = _scheduler.get_job("daily_scan")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
