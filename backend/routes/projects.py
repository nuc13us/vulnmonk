import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import uuid
import yaml

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from .. import crud, models, schemas, auth
from ..database import get_db

# Project root is 3 levels up from backend/routes/projects.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECTS_ROOT = os.path.join(PROJECT_ROOT, "projects")
os.makedirs(PROJECTS_ROOT, exist_ok=True)

router = APIRouter()

# In-memory set of project IDs currently being scanned
scanning_projects: set[int] = set()
trufflehog_scanning_projects: set[int] = set()


# ==================== HELPERS ====================

def validate_yaml_content(yaml_content: str) -> bool:
    """Validate if content is valid YAML or a JSON array of YAML file objects."""
    if not yaml_content or not yaml_content.strip():
        return True

    try:
        yaml_files = json.loads(yaml_content)
        if isinstance(yaml_files, list):
            for yaml_file in yaml_files:
                if isinstance(yaml_file, dict) and "content" in yaml_file:
                    yaml.safe_load(yaml_file["content"])
                else:
                    return False
            return True
    except (json.JSONDecodeError, ValueError):
        pass
    except yaml.YAMLError:
        return False

    try:
        yaml.safe_load(yaml_content)
        return True
    except yaml.YAMLError:
        return False


def generate_unique_key(finding):
    """Generate unique key for a finding: path@rule_id@content_hash.

    Uses a hash of the matched code snippet instead of the line number so that
    the key remains stable even when new code is inserted above the finding
    (which would otherwise shift line numbers and break existing FP records).
    """
    path    = finding.get("path", "unknown")
    rule_id = finding.get("check_id", "unknown")

    extra   = finding.get("extra", {})
    lines   = extra.get("lines", "") if isinstance(extra, dict) else ""

    # Normalise whitespace so minor formatting/indentation changes don't bust
    # the key, but actual code changes (fixing the vuln) will produce a new key.
    normalized = re.sub(r'\s+', ' ', lines.strip())

    content_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]

    return f"{path}@{rule_id}@{content_hash}"


def process_scan_findings(scan_result, project_id, db):
    """Add unique_key and status to findings, filter out false positives."""
    if not scan_result or not isinstance(scan_result, dict):
        return scan_result

    scan_result = copy.deepcopy(scan_result)
    results = scan_result.get("results", [])
    if not isinstance(results, list):
        return scan_result

    false_positives = crud.get_false_positives(db, project_id)
    fp_keys = {fp.unique_key for fp in false_positives}

    processed_results = []
    filtered_fps = []

    for finding in results:
        # Always recompute the key from the finding's content rather than trusting
        # any cached value in result_json.  Cached keys may be in an older format
        # (e.g. path@line@rule_id) which would never match FP records that were
        # stored after the key scheme changed to path@rule_id@content_hash.
        unique_key = generate_unique_key(finding)
        finding["unique_key"] = unique_key
        if unique_key in fp_keys:
            finding["status"] = "false_positive"
            filtered_fps.append(finding)
        else:
            finding["status"] = "open"
            processed_results.append(finding)

    scan_result["results"] = processed_results
    scan_result["false_positives"] = filtered_fps
    return scan_result


def run_opengrep_scan(local_path, exclude_rules_str, include_rules_yaml=None):
    """Run opengrep scan and return parsed JSON result or {"error": ...}."""
    config_file_paths = []
    try:
        cmd = ["opengrep", "scan", "--config", "auto"]

        if exclude_rules_str:
            for rule in exclude_rules_str.split(","):
                rule = rule.strip()
                if rule:
                    cmd += ["--exclude-rule", rule]

        if include_rules_yaml and include_rules_yaml.strip():
            try:
                yaml_files = json.loads(include_rules_yaml)
                if isinstance(yaml_files, list) and yaml_files:
                    for yaml_file in yaml_files:
                        if isinstance(yaml_file, dict) and "content" in yaml_file:
                            with tempfile.NamedTemporaryFile(
                                mode="w", suffix=".yaml", delete=False, dir=local_path
                            ) as f:
                                f.write(yaml_file["content"])
                                config_file_paths.append(f.name)
                                cmd += ["--config", f.name]
            except (json.JSONDecodeError, ValueError):
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False, dir=local_path
                ) as f:
                    f.write(include_rules_yaml)
                    config_file_paths.append(f.name)
                    cmd += ["--config", f.name]

        cmd += [".", "--json"]
        print(f"Running command: {' '.join(cmd)} in {local_path}")
        result = subprocess.run(cmd, cwd=local_path, capture_output=True, text=True, check=True)

        for path in config_file_paths:
            if os.path.exists(path):
                os.remove(path)

        return json.loads(result.stdout)
    except Exception as e:
        for path in config_file_paths:
            if os.path.exists(path):
                os.remove(path)
        return {"error": str(e)}


# ==================== PROJECT ENDPOINTS ====================

@router.put("/projects/{project_id}/exclude_rules/", response_model=schemas.Project)
def update_exclude_rules(
    project_id: int,
    rules: list = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    _EXCLUDE_RULE_RE = re.compile(r'^[a-z.\-]+$')
    invalid = [r for r in rules if r and not _EXCLUDE_RULE_RE.match(r.strip())]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid exclude rules: {invalid}. Rules may only contain lowercase letters (a-z), '.', and '-'."
        )

    project.exclude_rules = ",".join(r.strip() for r in rules if r.strip())
    db.commit()
    db.refresh(project)
    return project


@router.put("/projects/{project_id}/include_rules/", response_model=schemas.Project)
def update_include_rules(
    project_id: int,
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    yaml_content = payload.get("yaml_content", "")
    if yaml_content and yaml_content.strip():
        if not validate_yaml_content(yaml_content):
            raise HTTPException(status_code=400, detail="Invalid YAML content. Please provide valid YAML format.")

    project.include_rules_yaml = yaml_content
    project.apply_global_include = payload.get("apply_global_include", True)
    db.commit()
    db.refresh(project)
    return project


@router.put("/projects/{project_id}/global_preferences/", response_model=schemas.Project)
def update_global_preferences(
    project_id: int,
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if "apply_global_exclude" in payload:
        project.apply_global_exclude = 1 if payload["apply_global_exclude"] else 0
    if "apply_global_include" in payload:
        project.apply_global_include = 1 if payload["apply_global_include"] else 0

    db.commit()
    db.refresh(project)
    return project


@router.post("/projects/github/", response_model=schemas.Project)
def add_github_project(
    payload: dict,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    github_url = payload.get("github_url")
    if not github_url:
        raise HTTPException(status_code=400, detail="github_url required")

    db_project = crud.get_project_by_github_url(db, github_url=github_url)
    if db_project:
        return db_project

    project = schemas.ProjectCreate(github_url=github_url)
    return crud.create_project(db=db, project=project, local_path=None)


@router.get("/projects/")
def read_projects(
    page: int = 1,
    per_page: int = 100,
    search: str = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get projects with pagination and optional search."""
    query = db.query(models.Project)

    if search and search.strip():
        search_term = f"%{search.strip()}%"
        query = query.filter(
            (models.Project.github_url.ilike(search_term))
            | (models.Project.local_path.ilike(search_term))
        )

    total = query.count()
    skip = (page - 1) * per_page
    projects = query.offset(skip).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    # Fetch the latest scan summary for each project in one query instead of N lazy-loads
    project_ids = [p.id for p in projects]
    latest_scans = {}
    latest_th_scans = {}
    if project_ids:
        # Subquery: max scan_date per project (opengrep)
        sub = (
            db.query(
                models.ScanResult.project_id,
                func.max(models.ScanResult.id).label("max_id"),
            )
            .filter(models.ScanResult.project_id.in_(project_ids))
            .group_by(models.ScanResult.project_id)
            .subquery()
        )
        rows = (
            db.query(models.ScanResult)
            .join(sub, models.ScanResult.id == sub.c.max_id)
            .all()
        )
        for row in rows:
            latest_scans[row.project_id] = {
                "id": row.id,
                "scan_date": row.scan_date.isoformat() if row.scan_date else None,
                "findings_count": row.findings_count,
            }

        # Subquery: max trufflehog scan per project
        th_sub = (
            db.query(
                models.TrufflehogScanResult.project_id,
                func.max(models.TrufflehogScanResult.id).label("max_id"),
            )
            .filter(models.TrufflehogScanResult.project_id.in_(project_ids))
            .group_by(models.TrufflehogScanResult.project_id)
            .subquery()
        )
        th_rows = (
            db.query(models.TrufflehogScanResult)
            .join(th_sub, models.TrufflehogScanResult.id == th_sub.c.max_id)
            .all()
        )
        for row in th_rows:
            latest_th_scans[row.project_id] = {
                "id": row.id,
                "scan_date": row.scan_date.isoformat() if row.scan_date else None,
                "findings_count": row.findings_count,
            }

    project_list = []
    for p in projects:
        item = schemas.Project.from_orm(p).dict()
        item["latest_scan"] = latest_scans.get(p.id)
        item["latest_trufflehog_scan"] = latest_th_scans.get(p.id)
        project_list.append(item)

    # Compute total vulnerabilities across ALL projects (not just current page)
    latest_sub = (
        db.query(
            models.ScanResult.project_id,
            func.max(models.ScanResult.id).label("max_id"),
        )
        .group_by(models.ScanResult.project_id)
        .subquery()
    )
    total_vulns_row = (
        db.query(func.coalesce(func.sum(models.ScanResult.findings_count), 0))
        .join(latest_sub, models.ScanResult.id == latest_sub.c.max_id)
        .scalar()
    )

    # Compute total trufflehog secrets across ALL projects
    th_latest_sub = (
        db.query(
            models.TrufflehogScanResult.project_id,
            func.max(models.TrufflehogScanResult.id).label("max_id"),
        )
        .group_by(models.TrufflehogScanResult.project_id)
        .subquery()
    )
    total_secrets_row = (
        db.query(func.coalesce(func.sum(models.TrufflehogScanResult.findings_count), 0))
        .join(th_latest_sub, models.TrufflehogScanResult.id == th_latest_sub.c.max_id)
        .scalar()
    )

    return {
        "projects": project_list,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "total_vulnerabilities": total_vulns_row or 0,
        "total_secrets": total_secrets_row or 0,
    }


@router.get("/projects/{project_id}")
def read_project(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single project by ID."""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return schemas.Project.from_orm(project)


@router.get("/projects/{project_id}/scan/status")
def get_scan_status(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"scanning": project_id in scanning_projects}


@router.post("/projects/{project_id}/scan/")
def trigger_scan(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project_id in scanning_projects:
        raise HTTPException(status_code=409, detail="Scan already in progress for this project")

    scanning_projects.add(project_id)
    # Derive repo name from stored URL — never from user input at scan time
    raw_repo_name = project.github_url.rstrip("/").split("/")[-1].replace(".git", "")
    # Sanitize: keep only alphanumeric and hyphens so the directory name is always safe
    repo_name = re.sub(r'[^A-Za-z0-9\-]', '-', raw_repo_name)
    unique_id = str(uuid.uuid4())[:8]
    temp_path = os.path.join(PROJECTS_ROOT, f"temp-{repo_name}-{unique_id}")

    try:
        clone_url = project.github_url

        if project.integration_id:
            integration = crud.get_github_integration(db, project.integration_id)
            if integration and integration.access_token:
                if clone_url.startswith("https://github.com/"):
                    clone_url = clone_url.replace(
                        "https://github.com/",
                        f"https://{integration.access_token}@github.com/"
                    )

        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, temp_path],
            check=True, capture_output=True, text=True
        )

        # Merge global + project-specific exclude rules
        exclude_rules = project.exclude_rules or ""
        include_rules_yaml = project.include_rules_yaml or ""

        global_exclude_config = crud.get_global_config(db, "global_exclude_rules")
        if global_exclude_config and global_exclude_config.value:
            project_rules = [r.strip() for r in exclude_rules.split(",") if r.strip()]
            global_rules = [r.strip() for r in global_exclude_config.value.split(",") if r.strip()]
            exclude_rules = ",".join(set(project_rules + global_rules))

        global_include_config = crud.get_global_config(db, "global_include_rules_yaml")
        if global_include_config and global_include_config.value:
            try:
                project_yaml_files = []
                if include_rules_yaml:
                    try:
                        project_yaml_files = json.loads(include_rules_yaml)
                        if not isinstance(project_yaml_files, list):
                            project_yaml_files = []
                    except (json.JSONDecodeError, ValueError):
                        project_yaml_files = []

                global_yaml_files = []
                try:
                    global_yaml_files = json.loads(global_include_config.value)
                    if not isinstance(global_yaml_files, list):
                        global_yaml_files = []
                except (json.JSONDecodeError, ValueError):
                    global_yaml_files = []

                include_rules_yaml = json.dumps(global_yaml_files + project_yaml_files)
            except Exception:
                pass

        scan_result = run_opengrep_scan(temp_path, exclude_rules, include_rules_yaml)

        if isinstance(scan_result, dict) and "error" in scan_result:
            raise HTTPException(status_code=500, detail=f"OpenGrep scan failed: {scan_result['error']}")

        if scan_result and isinstance(scan_result, dict):
            results = scan_result.get("results", [])
            if isinstance(results, list):
                for finding in results:
                    finding["unique_key"] = generate_unique_key(finding)
                    finding["status"] = "open"

        scan = schemas.ScanResultCreate(result_json=scan_result)
        # Compute open findings_count at save time (total minus already-marked FPs)
        fp_keys = {fp.unique_key for fp in crud.get_false_positives(db, project_id)}
        raw_count = sum(
            1 for f in (scan_result.get("results", []) if isinstance(scan_result, dict) else [])
            if generate_unique_key(f) not in fp_keys
        )
        db_scan = crud.create_scan_result(db=db, scan=scan, project_id=project_id,
                                          findings_count=raw_count)

        processed_result = process_scan_findings(scan_result, project_id, db)
        return {
            "id": db_scan.id,
            "project_id": db_scan.project_id,
            "scan_date": db_scan.scan_date.isoformat() if db_scan.scan_date else None,
            "result_json": processed_result,
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Git clone failed: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
    finally:
        scanning_projects.discard(project_id)
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path, ignore_errors=True)


# ==================== SCAN HISTORY ENDPOINTS ====================

@router.get("/projects/{project_id}/scans/")
def read_scan_summaries(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    scans = crud.get_scan_results(db, project_id=project_id, skip=skip, limit=limit)

    summaries = []
    for scan in scans:
        if scan.findings_count is not None:
            # Fast path: stored count is up to date
            count = scan.findings_count
        else:
            # Fallback for old rows not yet backfilled
            false_positives = crud.get_false_positives(db, project_id)
            fp_keys = {fp.unique_key for fp in false_positives}
            count = 0
            if scan.result_json and isinstance(scan.result_json, dict):
                results = scan.result_json.get("results", [])
                if isinstance(results, list):
                    for finding in results:
                        if generate_unique_key(finding) not in fp_keys:
                            count += 1
        summaries.append({
            "id": scan.id,
            "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
            "findings_count": count,
        })
    return summaries


@router.get("/scans/{scan_id}/")
def get_scan_result(
    scan_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    scan = db.query(models.ScanResult).filter(models.ScanResult.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan.result_json:
        processed_result = process_scan_findings(scan.result_json, scan.project_id, db)
        return {
            "id": scan.id,
            "project_id": scan.project_id,
            "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
            "result_json": processed_result,
        }

    return {
        "id": scan.id,
        "project_id": scan.project_id,
        "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
        "result_json": scan.result_json,
    }


# ==================== FALSE POSITIVE ENDPOINTS ====================

@router.post("/projects/{project_id}/false-positives/")
def mark_false_positive(
    project_id: int,
    payload: dict,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    unique_key = payload.get("unique_key")
    if not unique_key:
        raise HTTPException(status_code=400, detail="unique_key required")

    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    fp = crud.create_false_positive(db, project_id, unique_key)
    crud.update_scan_findings_count(db, project_id, delta=-1)
    return {"success": True, "false_positive_id": fp.id, "unique_key": unique_key}


@router.get("/projects/{project_id}/false-positives/")
def get_false_positives_list(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    fps = crud.get_false_positives(db, project_id)
    return [{"id": fp.id, "unique_key": fp.unique_key, "marked_at": fp.marked_at} for fp in fps]


@router.delete("/projects/{project_id}/false-positives")
def unmark_false_positive(
    project_id: int,
    unique_key: str,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    crud.delete_false_positive(db, project_id, unique_key)
    crud.update_scan_findings_count(db, project_id, delta=+1)
    return {"success": True}


# ==================== SCHEDULED SCAN ENDPOINTS ====================

@router.get("/projects/{project_id}/scheduled-scan")
def get_scheduled_scan_config(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Return the scheduled scan setting for a project.

    scheduled_scan_enabled: null = inherit global, 1 = always on, 0 = always off.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": project_id,
        "scheduled_scan_enabled": project.scheduled_scan_enabled,
    }


@router.put("/projects/{project_id}/scheduled-scan")
def update_scheduled_scan_config(
    project_id: int,
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Update the scheduled scan setting for a project.

    Send { "enabled": true } to opt-in, { "enabled": false } to opt-out,
    or { "enabled": null } to inherit the global setting.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    enabled = payload.get("enabled")  # True | False | None
    updated = crud.update_project_scheduled_scan(db, project_id, enabled)
    return {
        "project_id": project_id,
        "scheduled_scan_enabled": updated.scheduled_scan_enabled,
    }


@router.get("/scheduled-scan/status")
def get_scheduler_status(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Return global scheduler status and next run time."""
    from ..scheduler import get_next_run_time

    global_cfg = crud.get_global_config(db, "global_scheduled_scan_enabled")
    global_enabled = global_cfg and global_cfg.value == "1"
    next_run = get_next_run_time()
    return {
        "global_scheduled_scan_enabled": bool(global_enabled),
        "next_run_time": next_run,
    }


# ==================== GLOBAL CONFIGURATION ENDPOINTS ====================

# NOTE: these specific routes MUST be declared before the wildcard /{key} handlers below.

@router.get("/configurations/global/pr-checks")
def get_global_pr_check_config(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_global_pr_config(db)


@router.put("/configurations/global/pr-checks")
def save_global_pr_check_config(
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db),
):
    enabled = bool(payload.get("enabled", False))
    severity = payload.get("block_on_severity", "none")
    secret = payload.get("webhook_secret", "")
    th_block_on = payload.get("th_block_on", "none")

    if severity not in ("none", "INFO", "WARNING", "ERROR"):
        raise HTTPException(status_code=400,
                            detail="block_on_severity must be none, INFO, WARNING, or ERROR")

    if th_block_on not in ("none", "verified", "all"):
        raise HTTPException(status_code=400,
                            detail="th_block_on must be none, verified, or all")

    if enabled and not secret:
        secret = secrets.token_hex(32)

    return crud.save_global_pr_config(db, enabled, severity, secret, th_block_on)


@router.get("/configurations/global/{key}")
def get_global_config(
    key: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    config = crud.get_global_config(db, key)
    if not config:
        return {"key": key, "value": ""}
    return {"key": config.key, "value": config.value}


@router.put("/configurations/global/{key}")
def update_global_config(
    key: str,
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    value = payload.get("value", "")

    if key == "global_exclude_rules" and value and value.strip():
        _EXCLUDE_RULE_RE = re.compile(r'^[a-z.\-]+$')
        invalid = [
            r for r in value.split(",")
            if r.strip() and not _EXCLUDE_RULE_RE.match(r.strip())
        ]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid exclude rules: {invalid}. Rules may only contain lowercase letters (a-z), '.', and '-'."
            )

    if key == "global_include_rules_yaml" and value and value.strip():
        if not validate_yaml_content(value):
            raise HTTPException(status_code=400, detail="Invalid YAML content. Please provide valid YAML format.")

    if key == "global_trufflehog_exclude_detectors" and value and value.strip():
        _DETECTOR_RE = re.compile(r'^[A-Za-z0-9_]+$')
        invalid = [
            d for d in value.split(",")
            if d.strip() and not _DETECTOR_RE.match(d.strip())
        ]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid detector names: {invalid}. Names may only contain letters, numbers, and underscores."
            )

    config = crud.update_global_config(db, key, value)
    return {"key": config.key, "value": config.value}


@router.get("/configurations/global")
def get_all_global_configs(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    global_exclude = crud.get_global_config(db, "global_exclude_rules")
    global_include = crud.get_global_config(db, "global_include_rules_yaml")
    global_th_exclude = crud.get_global_config(db, "global_trufflehog_exclude_detectors")
    global_sched = crud.get_global_config(db, "global_scheduled_scan_enabled")
    return {
        "global_exclude_rules": global_exclude.value if global_exclude else "",
        "global_include_rules_yaml": global_include.value if global_include else "",
        "global_trufflehog_exclude_detectors": global_th_exclude.value if global_th_exclude else "",
        "global_scheduled_scan_enabled": (global_sched.value == "1") if global_sched else False,
    }


# ==================== TRUFFLEHOG HELPERS ====================

def generate_trufflehog_unique_key(finding):
    """Generate unique key for a trufflehog finding: path@raw@detector."""
    git_data = finding.get("SourceMetadata", {}).get("Data", {}).get("Git", {})
    path = git_data.get("file", "unknown")
    raw = finding.get("Raw", "")
    detector = finding.get("DetectorName", "unknown")

    normalized_raw = re.sub(r'\s+', ' ', raw.strip())
    raw_hash = hashlib.sha256(normalized_raw.encode()).hexdigest()[:16]

    return f"{path}@{raw_hash}@{detector}"


def process_trufflehog_findings(findings_list, project_id, db):
    """Separate findings into open vs false-positive."""
    false_positives = crud.get_trufflehog_false_positives(db, project_id)
    fp_keys = {fp.unique_key for fp in false_positives}

    open_results = []
    fp_results = []

    for finding in findings_list:
        unique_key = generate_trufflehog_unique_key(finding)
        finding["unique_key"] = unique_key
        if unique_key in fp_keys:
            finding["status"] = "false_positive"
            fp_results.append(finding)
        else:
            finding["status"] = "open"
            open_results.append(finding)

    return {"results": open_results, "false_positives": fp_results}


def run_trufflehog_scan(repo_path, exclude_detectors_str=""):
    """Run trufflehog scan and return parsed JSON findings list or {"error": ...}."""
    try:
        cmd = ["trufflehog", "git", f"file://{repo_path}", "--json"]

        if exclude_detectors_str and exclude_detectors_str.strip():
            cmd.append(f"--exclude-detectors={exclude_detectors_str.strip()}")

        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        # trufflehog outputs one JSON per line
        findings = []
        summary = None
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # Skip log lines (level/logger fields) and summary line
                if "SourceMetadata" in obj:
                    findings.append(obj)
                elif "finished scanning" in obj.get("msg", ""):
                    summary = obj
            except json.JSONDecodeError:
                continue

        return {"findings": findings, "summary": summary}
    except subprocess.TimeoutExpired:
        return {"error": "TruffleHog scan timed out after 10 minutes"}
    except Exception as e:
        return {"error": str(e)}


# ==================== TRUFFLEHOG ENDPOINTS ====================

@router.put("/projects/{project_id}/trufflehog/exclude_detectors/")
def update_trufflehog_exclude_detectors(
    project_id: int,
    detectors: list = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    _DETECTOR_RE = re.compile(r'^[A-Za-z0-9_]+$')
    invalid = [d for d in detectors if d and not _DETECTOR_RE.match(d.strip())]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid detector names: {invalid}. Names may only contain letters, numbers, and underscores."
        )

    project.trufflehog_exclude_detectors = ",".join(d.strip() for d in detectors if d.strip())
    db.commit()
    db.refresh(project)
    return schemas.Project.from_orm(project)


@router.get("/projects/{project_id}/trufflehog/scan/status")
def get_trufflehog_scan_status(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"scanning": project_id in trufflehog_scanning_projects}


@router.post("/projects/{project_id}/trufflehog/scan/")
def trigger_trufflehog_scan(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project_id in trufflehog_scanning_projects:
        raise HTTPException(status_code=409, detail="TruffleHog scan already in progress for this project")

    trufflehog_scanning_projects.add(project_id)
    raw_repo_name = project.github_url.rstrip("/").split("/")[-1].replace(".git", "")
    repo_name = re.sub(r'[^A-Za-z0-9\-]', '-', raw_repo_name)
    unique_id = str(uuid.uuid4())[:8]
    temp_path = os.path.join(PROJECTS_ROOT, f"temp-th-{repo_name}-{unique_id}")

    try:
        clone_url = project.github_url

        if project.integration_id:
            integration = crud.get_github_integration(db, project.integration_id)
            if integration and integration.access_token:
                if clone_url.startswith("https://github.com/"):
                    clone_url = clone_url.replace(
                        "https://github.com/",
                        f"https://{integration.access_token}@github.com/"
                    )

        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, temp_path],
            check=True, capture_output=True, text=True
        )

        # Merge global + project-specific exclude detectors
        exclude_detectors = project.trufflehog_exclude_detectors or ""
        global_th_config = crud.get_global_config(db, "global_trufflehog_exclude_detectors")
        if global_th_config and global_th_config.value:
            project_detectors = [d.strip() for d in exclude_detectors.split(",") if d.strip()]
            global_detectors = [d.strip() for d in global_th_config.value.split(",") if d.strip()]
            exclude_detectors = ",".join(set(project_detectors + global_detectors))

        scan_result = run_trufflehog_scan(temp_path, exclude_detectors)

        if isinstance(scan_result, dict) and "error" in scan_result:
            raise HTTPException(status_code=500, detail=f"TruffleHog scan failed: {scan_result['error']}")

        findings = scan_result.get("findings", [])

        # Add unique keys
        for finding in findings:
            finding["unique_key"] = generate_trufflehog_unique_key(finding)
            finding["status"] = "open"

        # Compute open findings_count (total minus already-marked FPs)
        fp_keys = {fp.unique_key for fp in crud.get_trufflehog_false_positives(db, project_id)}
        raw_count = sum(1 for f in findings if generate_trufflehog_unique_key(f) not in fp_keys)

        result_to_store = {"findings": findings, "summary": scan_result.get("summary")}
        scan = schemas.TrufflehogScanResultCreate(result_json=result_to_store)
        db_scan = crud.create_trufflehog_scan_result(db=db, scan=scan, project_id=project_id,
                                                      findings_count=raw_count)

        processed = process_trufflehog_findings(findings, project_id, db)
        return {
            "id": db_scan.id,
            "project_id": db_scan.project_id,
            "scan_date": db_scan.scan_date.isoformat() if db_scan.scan_date else None,
            "result_json": {**processed, "summary": scan_result.get("summary")},
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Git clone failed: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TruffleHog scan failed: {str(e)}")
    finally:
        trufflehog_scanning_projects.discard(project_id)
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path, ignore_errors=True)


@router.get("/projects/{project_id}/trufflehog/scans/")
def read_trufflehog_scan_summaries(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    scans = crud.get_trufflehog_scan_results(db, project_id=project_id, skip=skip, limit=limit)
    summaries = []
    for scan in scans:
        if scan.findings_count is not None:
            count = scan.findings_count
        else:
            fp_keys = {fp.unique_key for fp in crud.get_trufflehog_false_positives(db, project_id)}
            count = 0
            if scan.result_json and isinstance(scan.result_json, dict):
                findings = scan.result_json.get("findings", [])
                if isinstance(findings, list):
                    for f in findings:
                        if generate_trufflehog_unique_key(f) not in fp_keys:
                            count += 1
        summaries.append({
            "id": scan.id,
            "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
            "findings_count": count,
        })
    return summaries


@router.get("/trufflehog/scans/{scan_id}/")
def get_trufflehog_scan_result(
    scan_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    scan = db.query(models.TrufflehogScanResult).filter(
        models.TrufflehogScanResult.id == scan_id
    ).first()
    if not scan:
        raise HTTPException(status_code=404, detail="TruffleHog scan not found")

    if scan.result_json:
        findings = scan.result_json.get("findings", [])
        processed = process_trufflehog_findings(findings, scan.project_id, db)
        return {
            "id": scan.id,
            "project_id": scan.project_id,
            "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
            "result_json": {**processed, "summary": scan.result_json.get("summary")},
        }

    return {
        "id": scan.id,
        "project_id": scan.project_id,
        "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
        "result_json": scan.result_json,
    }


@router.post("/projects/{project_id}/trufflehog/false-positives/")
def mark_trufflehog_false_positive(
    project_id: int,
    payload: dict,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    unique_key = payload.get("unique_key")
    if not unique_key:
        raise HTTPException(status_code=400, detail="unique_key required")

    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    fp = crud.create_trufflehog_false_positive(db, project_id, unique_key)
    crud.update_trufflehog_scan_findings_count(db, project_id, delta=-1)
    return {"success": True, "false_positive_id": fp.id, "unique_key": unique_key}


@router.get("/projects/{project_id}/trufflehog/false-positives/")
def get_trufflehog_false_positives_list(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    fps = crud.get_trufflehog_false_positives(db, project_id)
    return [{"id": fp.id, "unique_key": fp.unique_key, "marked_at": fp.marked_at} for fp in fps]


@router.delete("/projects/{project_id}/trufflehog/false-positives")
def unmark_trufflehog_false_positive(
    project_id: int,
    unique_key: str,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    crud.delete_trufflehog_false_positive(db, project_id, unique_key)
    crud.update_trufflehog_scan_findings_count(db, project_id, delta=+1)
    return {"success": True}
