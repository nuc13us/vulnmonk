
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import crud, models, schemas, database, auth
from .database import get_db
from typing import List
from datetime import timedelta
import os
import subprocess
import uuid
import yaml

# Get the project root directory (parent of backend)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_ROOT = os.path.join(PROJECT_ROOT, "projects")

# Ensure projects directory exists
os.makedirs(PROJECTS_ROOT, exist_ok=True)

router = APIRouter()

# ==================== HELPER FUNCTIONS ====================

def validate_yaml_content(yaml_content: str) -> bool:
    """
    Validate if the provided content is valid YAML or a JSON array of YAML file objects.
    Returns True if valid, False otherwise.
    """
    if not yaml_content or not yaml_content.strip():
        return True  # Empty content is valid
    
    try:
        # Try to parse as JSON array first (new format)
        import json
        yaml_files = json.loads(yaml_content)
        if isinstance(yaml_files, list):
            # Validate each YAML file content in the array
            for yaml_file in yaml_files:
                if isinstance(yaml_file, dict) and 'content' in yaml_file:
                    yaml.safe_load(yaml_file['content'])
                else:
                    return False  # Invalid structure
            return True
        else:
            # Not an array, fall through to YAML validation
            pass
    except (json.JSONDecodeError, ValueError):
        # Not JSON, fall through to YAML validation
        pass
    except yaml.YAMLError:
        return False
    
    # Fall back to validating as single YAML string (backward compatibility)
    try:
        yaml.safe_load(yaml_content)
        return True
    except yaml.YAMLError as e:
        return False

# ==================== AUTH ENDPOINTS ====================

@router.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token valid for 30 days
    access_token_expires = timedelta(days=auth.ACCESS_TOKEN_EXPIRE_DAYS)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=schemas.User)
def get_current_user_info(current_user: models.User = Depends(auth.get_current_user)):
    """Get current authenticated user information."""
    return current_user

@router.post("/auth/change-password")
def change_password(
    password_data: schemas.PasswordChange,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Change password for the current user."""
    # Verify old password
    if not auth.verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    # Update to new password
    hashed_password = auth.get_password_hash(password_data.new_password)
    crud.update_user_password(db, current_user, hashed_password)
    
    return {"success": True, "message": "Password updated successfully"}

# ==================== USER MANAGEMENT ENDPOINTS (ADMIN ONLY) ====================

@router.get("/users/", response_model=List[schemas.User])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """List all users (Admin only)."""
    return crud.get_users(db, skip=skip, limit=limit)

@router.post("/users/", response_model=schemas.User)
def create_user(
    user: schemas.UserCreate,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Create a new user (Admin only)."""
    # Check if user already exists
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Validate role
    if user.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
    
    # Hash password and create user
    hashed_password = auth.get_password_hash(user.password)
    return crud.create_user(db=db, user=user, hashed_password=hashed_password)

@router.put("/users/{user_id}/role", response_model=schemas.User)
def update_user_role(
    user_id: int,
    role_data: schemas.UserUpdate,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Update user role (Admin only)."""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from changing their own role
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    
    if role_data.role:
        if role_data.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
        crud.update_user_role(db, user, role_data.role)
    
    if role_data.is_active is not None:
        crud.update_user_status(db, user, role_data.is_active)
    
    db.refresh(user)
    return user

# ==================== PROJECT ENDPOINTS ====================

# Update exclude_rules for a project (Admin only)
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
    # Store as comma-separated string
    project.exclude_rules = ",".join(rules)
    db.commit()
    db.refresh(project)
    return project

# Update include_rules_yaml for a project (Admin only)
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
    
    # Validate YAML content if provided
    if yaml_content and yaml_content.strip():
        if not validate_yaml_content(yaml_content):
            raise HTTPException(
                status_code=400, 
                detail="Invalid YAML content. Please provide valid YAML format."
            )
    
    # Store YAML content
    project.include_rules_yaml = yaml_content
    project.apply_global_include = payload.get("apply_global_include", True)
    
    db.commit()
    db.refresh(project)
    return project

# Update project's global rule preferences (Admin only)
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

# Add project by storing GitHub URL only (no cloning yet) (Admin only)
@router.post("/projects/github/", response_model=schemas.Project)
def add_github_project(
    payload: dict,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    github_url = payload.get("github_url")
    if not github_url:
        raise HTTPException(status_code=400, detail="github_url required")
    
    # Check if project already exists
    db_project = crud.get_project_by_github_url(db, github_url=github_url)
    if db_project:
        return db_project
    
    # Only store the GitHub URL, don't clone yet
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
    """Get projects with pagination and optional search"""
    query = db.query(models.Project)
    
    # Apply search filter if provided
    if search and search.strip():
        search_term = f"%{search.strip()}%"
        query = query.filter(
            (models.Project.github_url.ilike(search_term)) |
            (models.Project.local_path.ilike(search_term))
        )
    
    total = query.count()
    skip = (page - 1) * per_page
    projects = query.offset(skip).limit(per_page).all()
    
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    has_next = page < total_pages
    has_prev = page > 1
    
    return {
        "projects": [schemas.Project.from_orm(p) for p in projects],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev
    }


# Trigger OpenGrep scan for a project (Admin only)
@router.post("/projects/{project_id}/scan/")
def trigger_scan(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Generate temporary path for cloning
    repo_name = project.github_url.rstrip("/").split("/")[-1].replace(".git", "")
    unique_id = str(uuid.uuid4())[:8]
    temp_path = os.path.join(PROJECTS_ROOT, f"temp-{repo_name}-{unique_id}")
    
    try:
        # Clone the repository (with authentication if integration is linked)
        print(f"[DEBUG] Cloning repository: {project.github_url} to {temp_path}")
        
        clone_url = project.github_url
        
        # Use authenticated clone if project has an integration_id
        if project.integration_id:
            integration = crud.get_github_integration(db, project.integration_id)
            if integration and integration.access_token:
                # Convert HTTPS URL to authenticated URL
                # https://github.com/org/repo.git -> https://<token>@github.com/org/repo.git
                if clone_url.startswith("https://github.com/"):
                    clone_url = clone_url.replace(
                        "https://github.com/",
                        f"https://{integration.access_token}@github.com/"
                    )
                    print(f"[DEBUG] Using authenticated clone for private repository access")
                else:
                    print(f"[DEBUG] Non-HTTPS URL, falling back to unauthenticated clone")
            else:
                print(f"[DEBUG] Integration not found or missing token, using unauthenticated clone")
        else:
            print(f"[DEBUG] No integration linked, using unauthenticated clone (public repos only)")
        
        subprocess.run(["git", "clone", "--depth", "1", clone_url, temp_path], 
                      check=True, capture_output=True, text=True)
        
        # Prepare exclude and include rules (merging global + project-specific)
        exclude_rules = project.exclude_rules or ""
        include_rules_yaml = project.include_rules_yaml or ""
        
        # Always merge global rules with project-specific rules
        global_exclude_config = crud.get_global_config(db, "global_exclude_rules")
        if global_exclude_config and global_exclude_config.value:
            global_exclude = global_exclude_config.value
            # Merge global and project exclude rules
            project_rules = [r.strip() for r in exclude_rules.split(",") if r.strip()]
            global_rules = [r.strip() for r in global_exclude.split(",") if r.strip()]
            all_exclude_rules = list(set(project_rules + global_rules))  # Remove duplicates
            exclude_rules = ",".join(all_exclude_rules)
        
        global_include_config = crud.get_global_config(db, "global_include_rules_yaml")
        if global_include_config and global_include_config.value:
            # Merge YAML file arrays (combine global + project-specific)
            import json
            try:
                # Parse project-specific YAML files
                project_yaml_files = []
                if include_rules_yaml:
                    try:
                        project_yaml_files = json.loads(include_rules_yaml)
                        if not isinstance(project_yaml_files, list):
                            project_yaml_files = []
                    except (json.JSONDecodeError, ValueError):
                        # Backward compatibility: treat as single YAML string
                        project_yaml_files = []
                
                # Parse global YAML files
                global_yaml_files = []
                try:
                    global_yaml_files = json.loads(global_include_config.value)
                    if not isinstance(global_yaml_files, list):
                        global_yaml_files = []
                except (json.JSONDecodeError, ValueError):
                    # Backward compatibility: treat as single YAML string
                    global_yaml_files = []
                
                # Merge arrays: global first, then project-specific
                merged_files = global_yaml_files + project_yaml_files
                include_rules_yaml = json.dumps(merged_files)
            except Exception as e:
                print(f"[WARNING] Failed to merge include rules: {e}")
                # In case of error, keep project-specific rules only
                pass
        
        # Run the scan
        scan_result = run_opengrep_scan(temp_path, exclude_rules, include_rules_yaml)
        # Add unique_key to all findings but DON'T filter yet (filtering happens on retrieval)
        if scan_result and isinstance(scan_result, dict):
            results = scan_result.get("results", [])
            if isinstance(results, list):
                for finding in results:
                    unique_key = generate_unique_key(finding)
                    finding["unique_key"] = unique_key
                    finding["status"] = "open"  # All new findings start as open
        
        # Store scan result with all findings (unfiltered)
        scan = schemas.ScanResultCreate(result_json=scan_result)
        db_scan = crud.create_scan_result(db=db, scan=scan, project_id=project_id)
        
        # Return processed version with current false positives filtered
        # (process_scan_findings makes a deep copy internally)
        processed_result = process_scan_findings(scan_result, project_id, db)
        
        return {
            "id": db_scan.id,
            "project_id": db_scan.project_id,
            "scan_date": db_scan.scan_date.isoformat() if db_scan.scan_date else None,
            "result_json": processed_result
        }
    
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Git clone failed: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
    finally:
        # Clean up: Delete the cloned repository
        if os.path.exists(temp_path):
            print(f"[DEBUG] Cleaning up temporary repository: {temp_path}")
            import shutil
            shutil.rmtree(temp_path, ignore_errors=True)

def run_opengrep_scan(local_path, exclude_rules_str, include_rules_yaml=None):
    config_file_paths = []
    try:
        cmd = ["opengrep", "scan", "--config", "auto"]
        
        # Add exclude rules if any
        if exclude_rules_str:
            for rule in exclude_rules_str.split(","):
                rule = rule.strip()
                if rule:
                    cmd += ["--exclude-rule", rule]
        
        # Add include rules from YAML if provided
        if include_rules_yaml and include_rules_yaml.strip():
            import tempfile
            import json
            
            # Try to parse as JSON array of file objects
            try:
                yaml_files = json.loads(include_rules_yaml)
                if isinstance(yaml_files, list) and len(yaml_files) > 0:
                    # Multiple YAML files - create separate temp files for each
                    for yaml_file in yaml_files:
                        if isinstance(yaml_file, dict) and 'content' in yaml_file:
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, dir=local_path) as f:
                                f.write(yaml_file['content'])
                                config_file_paths.append(f.name)
                                # Add each config file to the command
                                cmd += ["--config", f.name]
                else:
                    # Empty array, skip
                    pass
            except (json.JSONDecodeError, ValueError):
                # Not JSON, treat as single YAML string (backward compatibility)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, dir=local_path) as f:
                    f.write(include_rules_yaml)
                    config_file_paths.append(f.name)
                    cmd += ["--config", f.name]
        
        cmd += [".", "--json"]
        
        print(f"[DEBUG] Running opengrep command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=local_path, capture_output=True, text=True, check=True)
        
        # Clean up temporary config files if created
        for path in config_file_paths:
            if os.path.exists(path):
                os.remove(path)
        
        # Assume opengrep outputs JSON to stdout
        import json
        return json.loads(result.stdout)
    except Exception as e:
        # Clean up temporary config files on error
        for path in config_file_paths:
            if os.path.exists(path):
                os.remove(path)
        return {"error": str(e)}

def generate_unique_key(finding):
    """Generate unique key for a finding: path@line@rule-id"""
    path = finding.get("path", "unknown")
    line = finding.get("start", {}).get("line", 0) if isinstance(finding.get("start"), dict) else finding.get("line", 0)
    rule_id = finding.get("check_id", "unknown")
    unique_key = f"{path}@{line}@{rule_id}"
    return unique_key

def process_scan_findings(scan_result, project_id, db):
    """Add unique_key and status to findings, filter out false positives"""
    import copy
    
    if not scan_result or not isinstance(scan_result, dict):
        return scan_result
    
    # Make a deep copy to avoid modifying the original
    scan_result = copy.deepcopy(scan_result)
    
    results = scan_result.get("results", [])
    if not isinstance(results, list):
        return scan_result
    
    # Get false positives for this project
    false_positives = crud.get_false_positives(db, project_id)
    fp_keys = {fp.unique_key for fp in false_positives}
    
    print(f"[DEBUG] Processing scan for project {project_id}")
    print(f"[DEBUG] Found {len(false_positives)} false positive markers")
    print(f"[DEBUG] False positive keys: {fp_keys}")
    
    # Process findings
    processed_results = []
    filtered_fps = []
    
    for finding in results:
        # Use existing unique_key or generate new one
        unique_key = finding.get("unique_key") or generate_unique_key(finding)
        
        # Check if this is a false positive
        if unique_key in fp_keys:
            # Add to filtered list with false positive status
            finding["unique_key"] = unique_key
            finding["status"] = "false_positive"
            filtered_fps.append(finding)
            print(f"[DEBUG] Filtered as FP: {unique_key}")
        else:
            # Add to results with open status
            finding["unique_key"] = unique_key
            finding["status"] = "open"
            processed_results.append(finding)
    
    print(f"[DEBUG] Processed: {len(processed_results)} open, {len(filtered_fps)} false positives")
    
    scan_result["results"] = processed_results
    scan_result["false_positives"] = filtered_fps
    
    return scan_result


# Return only scan summary for history (no full JSON) (Authenticated)
@router.get("/projects/{project_id}/scans/")
def read_scan_summaries(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    scans = crud.get_scan_results(db, project_id=project_id, skip=skip, limit=limit)
    # Only return id, scan_date, and findings count - NO full result_json
    summaries = []
    for scan in scans:
        # Get current false positives for this project
        false_positives = crud.get_false_positives(db, project_id)
        fp_keys = {fp.unique_key for fp in false_positives}
        
        # Count only non-false-positive findings
        count = 0
        if scan.result_json and isinstance(scan.result_json, dict):
            results = scan.result_json.get("results", [])
            if isinstance(results, list):
                for finding in results:
                    unique_key = generate_unique_key(finding)
                    if unique_key not in fp_keys:
                        count += 1
        
        summaries.append({
            "id": scan.id,
            "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
            "findings_count": count
        })
    return summaries

# Fetch full scan result by scan id (re-process false positives dynamically) (Authenticated)
@router.get("/scans/{scan_id}/")
def get_scan_result(
    scan_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    scan = db.query(models.ScanResult).filter(models.ScanResult.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Re-process the scan to apply current false positive filters
    # This ensures FPs marked after the scan was run are properly filtered
    if scan.result_json:
        processed_result = process_scan_findings(scan.result_json, scan.project_id, db)
        
        # Return scan with re-processed results
        return {
            "id": scan.id,
            "project_id": scan.project_id,
            "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
            "result_json": processed_result
        }
    
    return {
        "id": scan.id,
        "project_id": scan.project_id,
        "scan_date": scan.scan_date.isoformat() if scan.scan_date else None,
        "result_json": scan.result_json
    }

# Mark a finding as false positive (Admin only)
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
    
    print(f"[DEBUG] Marking as false positive - Project: {project_id}, Unique Key: {unique_key}")
    fp = crud.create_false_positive(db, project_id, unique_key)
    print(f"[DEBUG] False positive created with ID: {fp.id}")
    
    return {"success": True, "false_positive_id": fp.id, "unique_key": unique_key}

# Get all false positives for a project (Authenticated)
@router.get("/projects/{project_id}/false-positives/")
def get_false_positives_list(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    fps = crud.get_false_positives(db, project_id)
    return [{"id": fp.id, "unique_key": fp.unique_key, "marked_at": fp.marked_at} for fp in fps]

# Remove false positive marking (Admin only)
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

# Get global configuration by key
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

# Update global configuration (Admin only)
@router.put("/configurations/global/{key}")
def update_global_config(
    key: str,
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    value = payload.get("value", "")
    
    # Validate YAML content for include rules
    if key == "global_include_rules_yaml" and value and value.strip():
        if not validate_yaml_content(value):
            raise HTTPException(
                status_code=400,
                detail="Invalid YAML content. Please provide valid YAML format."
            )
    
    config = crud.update_global_config(db, key, value)
    return {"key": config.key, "value": config.value}

# Get all global configurations
@router.get("/configurations/global")
def get_all_global_configs(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    global_exclude = crud.get_global_config(db, "global_exclude_rules")
    global_include = crud.get_global_config(db, "global_include_rules_yaml")
    
    return {
        "global_exclude_rules": global_exclude.value if global_exclude else "",
        "global_include_rules_yaml": global_include.value if global_include else ""
    }

# ==================== GITHUB INTEGRATION ENDPOINTS ====================

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:3000/integrations")

@router.get("/integrations/github/auth-url")
def get_github_auth_url(
    current_user: models.User = Depends(auth.get_current_active_admin)
):
    """Get GitHub OAuth authorization URL (Admin only)"""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables."
        )
    
    state = str(uuid.uuid4())  # Generate random state for CSRF protection
    auth_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={GITHUB_CLIENT_ID}&"
        f"redirect_uri={GITHUB_REDIRECT_URI}&"
        f"scope=repo,read:org&"
        f"state={state}"
    )
    
    return {"auth_url": auth_url, "state": state}

@router.post("/integrations/github/callback")
def github_oauth_callback(
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Handle GitHub OAuth callback and create integration (Admin only)"""
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is required")
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth is not configured"
        )
    
    try:
        import requests
        
        print(f"[DEBUG] GitHub OAuth callback - Code received: {code[:10]}...")
        print(f"[DEBUG] GitHub OAuth config - Client ID: {GITHUB_CLIENT_ID}")
        print(f"[DEBUG] GitHub OAuth config - Redirect URI: {GITHUB_REDIRECT_URI}")
        
        # Exchange code for access token
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI
            }
        )
        
        print(f"[DEBUG] Token exchange status: {token_response.status_code}")
        
        if token_response.status_code != 200:
            print(f"[ERROR] Token exchange failed: {token_response.text}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code for access token: {token_response.text}"
            )
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        print(f"[DEBUG] Token exchange response: {token_data}")
        print(f"[DEBUG] Access token received: {bool(access_token)}")
        
        if not access_token:
            error_msg = token_data.get('error_description', token_data.get('error', 'Unknown error'))
            print(f"[ERROR] No access token in response: {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=f"GitHub error: {error_msg}"
            )
        
        # Get GitHub username from user's repositories (instead of /user endpoint)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        print(f"[DEBUG] Fetching GitHub username from repositories...")
        
        # Get username from first repository
        repos_response = requests.get("https://api.github.com/user/repos?per_page=1", headers=headers)
        github_login = None
        
        if repos_response.status_code == 200 and repos_response.json():
            repos = repos_response.json()
            if repos:
                github_login = repos[0]["owner"]["login"]
                print(f"[DEBUG] GitHub username extracted from repos: {github_login}")
        
        # If no repos found, try to get username from organizations membership
        if not github_login:
            print(f"[DEBUG] No repos found, trying to get username from org membership...")
            org_memberships_response = requests.get("https://api.github.com/user/memberships/orgs", headers=headers)
            if org_memberships_response.status_code == 200:
                memberships = org_memberships_response.json()
                if memberships:
                    # Get username from organization URL
                    github_login = memberships[0]["user"]["login"]
                    print(f"[DEBUG] GitHub username extracted from org membership: {github_login}")
        
        # Get user's organizations
        print(f"[DEBUG] Fetching GitHub organizations...")
        orgs_response = requests.get("https://api.github.com/user/orgs", headers=headers)
        print(f"[DEBUG] Organizations response status: {orgs_response.status_code}")
        
        organizations = []
        if orgs_response.status_code == 200:
            organizations = [org["login"] for org in orgs_response.json()]
        

        
        # Create/update integrations
        created_integrations = []
        updated_integrations = []
        
        # 1. Create/update integration for personal account (if username found)
        if github_login:
            personal_org_name = f"{github_login} (Personal)"
            existing_personal = db.query(models.GitHubIntegration).filter(
                models.GitHubIntegration.org_name == personal_org_name
            ).first()
            
            if existing_personal:
                existing_personal.access_token = access_token
                existing_personal.organizations = []
                db.commit()
                db.refresh(existing_personal)
                updated_integrations.append(personal_org_name)
            else:
                personal_integration = schemas.GitHubIntegrationCreate(
                    org_name=personal_org_name,
                    access_token=access_token,
                    organizations=[]
                )
                crud.create_github_integration(db, personal_integration)
                created_integrations.append(personal_org_name)
        
        # 2. Create/update integration for each organization
        for org_name in organizations:
            existing_org = db.query(models.GitHubIntegration).filter(
                models.GitHubIntegration.org_name == org_name
            ).first()
            
            if existing_org:
                existing_org.access_token = access_token
                existing_org.organizations = []
                db.commit()
                db.refresh(existing_org)
                updated_integrations.append(org_name)
            else:
                org_integration = schemas.GitHubIntegrationCreate(
                    org_name=org_name,
                    access_token=access_token,
                    organizations=[]
                )
                crud.create_github_integration(db, org_integration)
                created_integrations.append(org_name)
        
        total_integrations = len(created_integrations) + len(updated_integrations)
        message = f"Successfully connected {total_integrations} integration(s)"
        if created_integrations:
            message += f" (Created: {', '.join(created_integrations)})"
        if updated_integrations:
            message += f" (Updated: {', '.join(updated_integrations)})"
        
        return {
            "github_user": github_login,
            "organizations": organizations,
            "total_integrations": total_integrations,
            "created": created_integrations,
            "updated": updated_integrations,
            "message": message
        }
    
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"GitHub API error: {str(e)}")

@router.post("/integrations/github", response_model=schemas.GitHubIntegration)
def create_github_integration(
    integration: schemas.GitHubIntegrationCreate,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Create a new GitHub integration (Admin only)"""
    return crud.create_github_integration(db, integration)

@router.get("/integrations/github", response_model=List[schemas.GitHubIntegration])
def list_github_integrations(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """List all GitHub integrations"""
    return crud.get_github_integrations(db)

@router.delete("/integrations/github/{integration_id}")
def delete_github_integration(
    integration_id: int,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Delete a GitHub integration (Admin only)"""
    success = crud.delete_github_integration(db, integration_id)
    if not success:
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"message": "Integration deleted successfully"}

@router.get("/integrations/github/{integration_id}/repositories", response_model=schemas.GitHubRepositoriesResponse)
def get_github_repositories(
    integration_id: int,
    page: int = 1,
    per_page: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch repositories from the specific organization/account with pagination"""
    integration = crud.get_github_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    try:
        import requests
        headers = {
            "Authorization": f"Bearer {integration.access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        all_repos = []
        
        # Determine if this is a personal account or organization
        org_name = integration.org_name
        
        # If it's a personal account (ends with "(Personal)"), extract the username
        if org_name.endswith(" (Personal)"):
            # Personal account - fetch user repos
            username = org_name.replace(" (Personal)", "")
            repos_url = f"https://api.github.com/users/{username}/repos"
        else:
            # Organization - fetch org repos
            repos_url = f"https://api.github.com/orgs/{org_name}/repos"
        
        # Fetch ALL repositories from GitHub first (to get accurate total count)
        print(f"[DEBUG] Fetching all repositories from {repos_url}")
        github_page = 1
        
        while True:
            print(f"[DEBUG] Fetching GitHub page {github_page} (per_page=100)")
            response = requests.get(repos_url, headers=headers, params={"per_page": 100, "page": github_page})
            if response.status_code == 200:
                repos = response.json()
                if not repos:
                    print(f"[DEBUG] No more repos on GitHub page {github_page}")
                    break
                
                print(f"[DEBUG] Got {len(repos)} repos from GitHub page {github_page}")
                
                for repo in repos:
                    all_repos.append({
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "html_url": repo["html_url"],
                        "clone_url": repo["clone_url"],
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "default_branch": repo.get("default_branch", "main")
                    })
                
                if len(repos) < 100:
                    print(f"[DEBUG] Got {len(repos)} repos (less than 100), last GitHub page")
                    break
                github_page += 1
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch repositories from GitHub: {response.text}"
                )
        
        total_repos = len(all_repos)
        print(f"[DEBUG] Total repositories from GitHub: {total_repos}")
        
        # Now paginate for the client
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_repos = all_repos[start_idx:end_idx]
        
        has_next = end_idx < total_repos
        total_pages = (total_repos + per_page - 1) // per_page
        
        print(f"[DEBUG] Returning page {page}/{total_pages}: {len(paginated_repos)} repos (total: {total_repos})")
        
        return {
            "repositories": paginated_repos,
            "page": page,
            "per_page": per_page,
            "total": total_repos,
            "total_pages": total_pages,
            "has_next": has_next
        }
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {str(e)}")

@router.post("/integrations/github/{integration_id}/import-projects")
def import_github_projects(
    integration_id: int,
    repo_urls: List[str] = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Import selected repositories as projects (Admin only)"""
    integration = crud.get_github_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    imported = []
    skipped = []
    
    for repo_url in repo_urls:
        # Check if project already exists
        existing = crud.get_project_by_github_url(db, repo_url)
        if existing:
            skipped.append({"url": repo_url, "reason": "Already exists"})
            continue
        
        # Create new project with integration_id link
        try:
            project_data = schemas.ProjectCreate(
                github_url=repo_url,
                integration_id=integration_id
            )
            project = crud.create_project(db, project_data, local_path=None)
            imported.append({"id": project.id, "url": project.github_url})
        except Exception as e:
            skipped.append({"url": repo_url, "reason": str(e)})
    
    return {
        "imported": imported,
        "skipped": skipped,
        "total_imported": len(imported),
        "total_skipped": len(skipped)
    }
