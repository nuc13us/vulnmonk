from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime

def get_project(db: Session, project_id: int):
    return db.query(models.Project).filter(models.Project.id == project_id).first()


def get_project_by_github_url(db: Session, github_url: str):
    return db.query(models.Project).filter(models.Project.github_url == github_url).first()

def get_projects(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Project).offset(skip).limit(limit).all()

def create_project(db: Session, project: schemas.ProjectCreate, local_path: str = None):
    db_project = models.Project(
        github_url=project.github_url,
        local_path=local_path,
        integration_id=project.integration_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def create_scan_result(db: Session, scan: schemas.ScanResultCreate, project_id: int,
                       findings_count: int = None):
    data = scan.dict()
    data["project_id"] = project_id
    if not data.get("scan_date"):
        from datetime import datetime
        data["scan_date"] = datetime.utcnow()
    if findings_count is not None:
        data["findings_count"] = findings_count
    db_scan = models.ScanResult(**data)
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    
    # Clean up old scans - keep only the 20 most recent per project
    cleanup_old_scans(db, project_id, keep_count=20)
    
    return db_scan

def cleanup_old_scans(db: Session, project_id: int, keep_count: int = 20):
    """Delete old scans, keeping only the most recent keep_count scans"""
    # Get all scans for the project ordered by date
    all_scans = db.query(models.ScanResult).filter(
        models.ScanResult.project_id == project_id
    ).order_by(models.ScanResult.scan_date.desc()).all()
    
    # If we have more than keep_count, delete the oldest ones
    if len(all_scans) > keep_count:
        scans_to_delete = all_scans[keep_count:]
        for scan in scans_to_delete:
            db.delete(scan)
        db.commit()
        print(f"[DEBUG] Cleaned up {len(scans_to_delete)} old scans for project {project_id}")

def get_scan_results(db: Session, project_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.ScanResult).filter(
        models.ScanResult.project_id == project_id
    ).order_by(models.ScanResult.scan_date.desc()).offset(skip).limit(limit).all()


def update_scan_findings_count(db: Session, project_id: int, delta: int):
    """Increment or decrement findings_count on the most recent scan for a project."""
    scan = db.query(models.ScanResult).filter(
        models.ScanResult.project_id == project_id
    ).order_by(models.ScanResult.scan_date.desc()).first()
    if scan and scan.findings_count is not None:
        scan.findings_count = max(0, scan.findings_count + delta)
        db.commit()

def create_false_positive(db: Session, project_id: int, unique_key: str):
    """Mark a finding as false positive for a project"""
    # Check if already exists
    existing = db.query(models.FalsePositive).filter(
        models.FalsePositive.project_id == project_id,
        models.FalsePositive.unique_key == unique_key
    ).first()
    
    if existing:
        return existing
    
    db_fp = models.FalsePositive(project_id=project_id, unique_key=unique_key)
    db.add(db_fp)
    db.commit()
    db.refresh(db_fp)
    return db_fp

def get_false_positives(db: Session, project_id: int):
    """Get all false positives for a project"""
    return db.query(models.FalsePositive).filter(
        models.FalsePositive.project_id == project_id
    ).all()

def delete_false_positive(db: Session, project_id: int, unique_key: str):
    """Remove a false positive marking"""
    db.query(models.FalsePositive).filter(
        models.FalsePositive.project_id == project_id,
        models.FalsePositive.unique_key == unique_key
    ).delete()
    db.commit()
    return True

# User CRUD operations
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate, hashed_password: str):
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_password(db: Session, user: models.User, hashed_password: str):
    user.hashed_password = hashed_password
    db.commit()
    db.refresh(user)
    return user

def update_user_role(db: Session, user: models.User, role: str):
    user.role = role
    db.commit()
    db.refresh(user)
    return user

def update_user_status(db: Session, user: models.User, is_active: bool):
    user.is_active = 1 if is_active else 0
    db.commit()
    db.refresh(user)
    return user

# Global Configuration CRUD operations
def get_global_config(db: Session, key: str):
    """Get a global configuration value by key"""
    return db.query(models.GlobalConfiguration).filter(
        models.GlobalConfiguration.key == key
    ).first()

def update_global_config(db: Session, key: str, value: str):
    """Create or update a global configuration"""
    config = get_global_config(db, key)
    if config:
        config.value = value
        config.updated_at = datetime.utcnow()
    else:
        config = models.GlobalConfiguration(key=key, value=value)
        db.add(config)
    db.commit()
    db.refresh(config)
    return config

def get_all_global_configs(db: Session):
    """Get all global configurations"""
    return db.query(models.GlobalConfiguration).all()

# GitHub Integration CRUD operations
def get_github_integration(db: Session, integration_id: int):
    """Get a GitHub integration by ID"""
    return db.query(models.GitHubIntegration).filter(
        models.GitHubIntegration.id == integration_id
    ).first()

def get_github_integrations(db: Session, skip: int = 0, limit: int = 100):
    """Get all GitHub integrations"""
    return db.query(models.GitHubIntegration).offset(skip).limit(limit).all()

def create_github_integration(db: Session, integration: schemas.GitHubIntegrationCreate):
    """Create a new GitHub integration"""
    db_integration = models.GitHubIntegration(
        org_name=integration.org_name,
        access_token=integration.access_token or "",
        installation_id=integration.installation_id,
        account_type=integration.account_type or "User",
    )
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    return db_integration


def get_github_integration_by_installation_id(db: Session, installation_id: int):
    """Get a GitHub integration by GitHub App installation_id."""
    return db.query(models.GitHubIntegration).filter(
        models.GitHubIntegration.installation_id == installation_id
    ).first()


# ==================== TRUFFLEHOG CRUD ====================

def create_trufflehog_scan_result(db: Session, scan: schemas.TrufflehogScanResultCreate,
                                   project_id: int, findings_count: int = None):
    data = scan.dict()
    data["project_id"] = project_id
    if not data.get("scan_date"):
        data["scan_date"] = datetime.utcnow()
    if findings_count is not None:
        data["findings_count"] = findings_count
    db_scan = models.TrufflehogScanResult(**data)
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    cleanup_old_trufflehog_scans(db, project_id, keep_count=20)
    return db_scan


def cleanup_old_trufflehog_scans(db: Session, project_id: int, keep_count: int = 20):
    all_scans = db.query(models.TrufflehogScanResult).filter(
        models.TrufflehogScanResult.project_id == project_id
    ).order_by(models.TrufflehogScanResult.scan_date.desc()).all()
    if len(all_scans) > keep_count:
        scans_to_delete = all_scans[keep_count:]
        for scan in scans_to_delete:
            db.delete(scan)
        db.commit()


def get_trufflehog_scan_results(db: Session, project_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.TrufflehogScanResult).filter(
        models.TrufflehogScanResult.project_id == project_id
    ).order_by(models.TrufflehogScanResult.scan_date.desc()).offset(skip).limit(limit).all()


def update_trufflehog_scan_findings_count(db: Session, project_id: int, delta: int):
    scan = db.query(models.TrufflehogScanResult).filter(
        models.TrufflehogScanResult.project_id == project_id
    ).order_by(models.TrufflehogScanResult.scan_date.desc()).first()
    if scan and scan.findings_count is not None:
        scan.findings_count = max(0, scan.findings_count + delta)
        db.commit()


def create_trufflehog_false_positive(db: Session, project_id: int, unique_key: str):
    existing = db.query(models.TrufflehogFalsePositive).filter(
        models.TrufflehogFalsePositive.project_id == project_id,
        models.TrufflehogFalsePositive.unique_key == unique_key
    ).first()
    if existing:
        return existing
    db_fp = models.TrufflehogFalsePositive(project_id=project_id, unique_key=unique_key)
    db.add(db_fp)
    db.commit()
    db.refresh(db_fp)
    return db_fp


def get_trufflehog_false_positives(db: Session, project_id: int):
    return db.query(models.TrufflehogFalsePositive).filter(
        models.TrufflehogFalsePositive.project_id == project_id
    ).all()


def delete_trufflehog_false_positive(db: Session, project_id: int, unique_key: str):
    db.query(models.TrufflehogFalsePositive).filter(
        models.TrufflehogFalsePositive.project_id == project_id,
        models.TrufflehogFalsePositive.unique_key == unique_key
    ).delete()
    db.commit()
    return True


def create_or_update_app_installation(
    db: Session,
    installation_id: int,
    account_login: str,
    account_type: str,
) -> models.GitHubIntegration:
    """
    Upsert a GitHubIntegration row when a GitHub App installation is
    created or reinstalled (triggered by the `installation` webhook event).
    """
    existing = get_github_integration_by_installation_id(db, installation_id)
    if existing:
        existing.org_name = account_login
        existing.account_type = account_type
        db.commit()
        db.refresh(existing)
        return existing

    row = models.GitHubIntegration(
        org_name=account_login,
        installation_id=installation_id,
        account_type=account_type,
        access_token="",  # not needed for App-based auth
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_github_integration_by_installation_id(db: Session, installation_id: int) -> bool:
    """Delete a GitHubIntegration triggered by an App uninstall webhook."""
    row = get_github_integration_by_installation_id(db, installation_id)
    if row:
        db.delete(row)
        db.commit()
        return True
    return False


def get_project_and_severity_for_pr(db: Session, repo_full_name: str):
    """
    App-based PR check resolver.  Returns (project, block_on_severity) where
    block_on_severity is "none" | "INFO" | "WARNING" | "ERROR".

    Resolution priority:
      1. Repo not tracked → (None, None)
      2. Per-project PRCheckConfig with enabled=1 → (project, per-project severity)
         (uses custom per-project settings; overrides global severity but not global on/off)
      3. Per-project PRCheckConfig with enabled=0 OR no row → defer to global:
           global disabled → (None, None)
           global enabled  → (project, global severity)
    """
    all_projects = db.query(models.Project).all()
    matched_project = None
    for p in all_projects:
        if not p.github_url:
            continue
        url = p.github_url.rstrip("/").removesuffix(".git")
        parts = [seg for seg in url.split("/") if seg and ":" not in seg]
        if len(parts) >= 2 and "/".join(parts[-2:]) == repo_full_name:
            matched_project = p
            break

    if not matched_project:
        return None, None, None

    cfg = db.query(models.PRCheckConfig).filter(
        models.PRCheckConfig.project_id == matched_project.id
    ).first()

    # Per-project enabled=1 means the project uses its own custom settings.
    # Per-project enabled=0 (or no row) means "defer to global" — fall through.
    if cfg and cfg.enabled == 1:
        return matched_project, cfg.block_on_severity or "none", cfg.th_block_on or "none"

    # No per-project config, or per-project is set to inherit global — check global setting
    g = get_global_pr_config(db)
    if not g["enabled"]:
        return None, None, None
    return matched_project, g["block_on_severity"] or "none", g["th_block_on"] or "none"

def delete_github_integration(db: Session, integration_id: int):
    """Delete a GitHub integration"""
    integration = get_github_integration(db, integration_id)
    if integration:
        db.delete(integration)
        db.commit()
        return True
    return False


# ==================== PR CHECK CONFIG CRUD ====================

def get_pr_check_config(db: Session, project_id: int):
    """Get PR check config for a project, creating a default one if absent."""
    config = db.query(models.PRCheckConfig).filter(
        models.PRCheckConfig.project_id == project_id
    ).first()
    if not config:
        config = models.PRCheckConfig(project_id=project_id, enabled=0)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def save_pr_check_config(db: Session, project_id: int, enabled: bool,
                         webhook_secret: str, block_on_severity: str,
                         th_block_on: str = "none"):
    """Create or update PR check config."""
    config = db.query(models.PRCheckConfig).filter(
        models.PRCheckConfig.project_id == project_id
    ).first()
    if config:
        config.enabled = 1 if enabled else 0
        config.webhook_secret = webhook_secret
        config.block_on_severity = block_on_severity
        config.th_block_on = th_block_on
        config.updated_at = datetime.utcnow()
    else:
        config = models.PRCheckConfig(
            project_id=project_id,
            enabled=1 if enabled else 0,
            webhook_secret=webhook_secret,
            block_on_severity=block_on_severity,
            th_block_on=th_block_on,
        )
        db.add(config)
    db.commit()
    db.refresh(config)
    return config


def get_global_pr_config(db: Session) -> dict:
    """Return global PR check settings as a plain dict."""
    def _val(key, default=""):
        row = get_global_config(db, key)
        return row.value if row else default
    return {
        "enabled": _val("global_pr_checks_enabled", "0") == "1",
        "block_on_severity": _val("global_pr_checks_severity", "none"),
        "webhook_secret": _val("global_pr_checks_secret", ""),
        "th_block_on": _val("global_pr_checks_th_block_on", "none"),
    }


def save_global_pr_config(db: Session, enabled: bool,
                          block_on_severity: str, webhook_secret: str,
                          th_block_on: str = "none") -> dict:
    """Persist global PR check settings into GlobalConfiguration rows."""
    update_global_config(db, "global_pr_checks_enabled", "1" if enabled else "0")
    update_global_config(db, "global_pr_checks_severity", block_on_severity)
    update_global_config(db, "global_pr_checks_secret", webhook_secret)
    update_global_config(db, "global_pr_checks_th_block_on", th_block_on)
    return {
        "enabled": enabled,
        "block_on_severity": block_on_severity,
        "webhook_secret": webhook_secret,
        "th_block_on": th_block_on,
    }


# ==================== PR SCAN RESULT CRUD ====================

def create_pr_scan(db: Session, project_id: int, pr_number: int, pr_title: str,
                   head_sha: str, base_branch: str, head_branch: str,
                   repo_full_name: str, changed_files: list):
    """Create a pending PR scan record."""
    record = models.PRScanResult(
        project_id=project_id,
        pr_number=pr_number,
        pr_title=pr_title,
        head_sha=head_sha,
        base_branch=base_branch,
        head_branch=head_branch,
        repo_full_name=repo_full_name,
        status="pending",
        changed_files=changed_files,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_pr_scan(db: Session, pr_scan_id: int, status: str,
                   findings_count: int = 0, result_json: dict = None):
    """Update a PR scan record after scanning completes."""
    record = db.query(models.PRScanResult).filter(
        models.PRScanResult.id == pr_scan_id
    ).first()
    if record:
        record.status = status
        record.findings_count = findings_count
        record.result_json = result_json
        db.commit()
        db.refresh(record)
    return record


def get_pr_scans(db: Session, project_id: int, limit: int = 50):
    """List PR scans for a project, newest first."""
    return db.query(models.PRScanResult).filter(
        models.PRScanResult.project_id == project_id
    ).order_by(models.PRScanResult.created_at.desc()).limit(limit).all()


def get_pr_scan(db: Session, pr_scan_id: int):
    return db.query(models.PRScanResult).filter(
        models.PRScanResult.id == pr_scan_id
    ).first()
