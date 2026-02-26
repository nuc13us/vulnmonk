from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime

def get_project(db: Session, project_id: int):
    return db.query(models.Project).filter(models.Project.id == project_id).first()


def get_project_by_github_url(db: Session, github_url: str):
    return db.query(models.Project).filter(models.Project.github_url == github_url).first()

def get_project_by_local_path(db: Session, local_path: str):
    return db.query(models.Project).filter(models.Project.local_path == local_path).first()

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

def create_scan_result(db: Session, scan: schemas.ScanResultCreate, project_id: int):
    data = scan.dict()
    data["project_id"] = project_id
    if not data.get("scan_date"):
        from datetime import datetime
        data["scan_date"] = datetime.utcnow()
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
        access_token=integration.access_token
    )
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    return db_integration

def delete_github_integration(db: Session, integration_id: int):
    """Delete a GitHub integration"""
    integration = get_github_integration(db, integration_id)
    if integration:
        db.delete(integration)
        db.commit()
        return True
    return False
