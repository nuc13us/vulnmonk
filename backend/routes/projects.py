import copy
import json
import os
import subprocess
import tempfile
import uuid
import yaml

from fastapi import APIRouter, Body, Depends, HTTPException
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
    """Generate unique key for a finding: path@line@rule-id"""
    path = finding.get("path", "unknown")
    line = (
        finding.get("start", {}).get("line", 0)
        if isinstance(finding.get("start"), dict)
        else finding.get("line", 0)
    )
    rule_id = finding.get("check_id", "unknown")
    return f"{path}@{line}@{rule_id}"


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
        unique_key = finding.get("unique_key") or generate_unique_key(finding)
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
    project.exclude_rules = ",".join(rules)
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
    return {
        "projects": [schemas.Project.from_orm(p) for p in projects],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
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
    repo_name = project.github_url.rstrip("/").split("/")[-1].replace(".git", "")
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
        db_scan = crud.create_scan_result(db=db, scan=scan, project_id=project_id)

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
            import shutil
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
    false_positives = crud.get_false_positives(db, project_id)
    fp_keys = {fp.unique_key for fp in false_positives}

    summaries = []
    for scan in scans:
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
    return {"success": True, "false_positive_id": fp.id, "unique_key": unique_key}


@router.get("/projects/{project_id}/false-positives/")
def get_false_positives_list(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    fps = crud.get_false_positives(db, project_id)
    return [{"id": fp.id, "unique_key": fp.unique_key, "marked_at": fp.marked_at} for fp in fps]


@router.delete("/projects/{project_id}/false-positives/{unique_key}")
def unmark_false_positive(
    project_id: int,
    unique_key: str,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    crud.delete_false_positive(db, project_id, unique_key)
    return {"success": True}


# ==================== GLOBAL CONFIGURATION ENDPOINTS ====================

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

    if key == "global_include_rules_yaml" and value and value.strip():
        if not validate_yaml_content(value):
            raise HTTPException(status_code=400, detail="Invalid YAML content. Please provide valid YAML format.")

    config = crud.update_global_config(db, key, value)
    return {"key": config.key, "value": config.value}


@router.get("/configurations/global")
def get_all_global_configs(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    global_exclude = crud.get_global_config(db, "global_exclude_rules")
    global_include = crud.get_global_config(db, "global_include_rules_yaml")
    return {
        "global_exclude_rules": global_exclude.value if global_exclude else "",
        "global_include_rules_yaml": global_include.value if global_include else "",
    }
