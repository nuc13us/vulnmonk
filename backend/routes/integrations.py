import os

import requests
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import crud, models, schemas, auth, github_app
from ..database import get_db

router = APIRouter()

# ==================== GITHUB APP INTEGRATION ENDPOINTS ====================

@router.get("/integrations/github/app-install-url")
def get_github_app_install_url(
    target_type: str = "",
    current_user: models.User = Depends(auth.get_current_active_admin)
):
    """Return the URL to install the GitHub App on an org or personal account.

    Optional query param `target_type=Organization` restricts the GitHub
    account picker to org accounts only, which avoids landing on an
    already-installed personal account.
    """
    if not github_app.get_slug():
        raise HTTPException(
            status_code=400,
            detail="GITHUB_APP_SLUG is not configured. Save your GitHub App credentials first (App Slug field).",
        )
    return {"install_url": github_app.get_install_url(target_type=target_type)}


@router.post("/integrations/github/app/sync")
def sync_github_app_installations(
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Pull all current App installations from GitHub and upsert into DB.

    Useful when the installation webhook was not received (e.g. ngrok was
    not running at install time).  Requires GITHUB_APP_ID and
    GITHUB_APP_PRIVATE_KEY to be configured.
    """
    if not github_app.is_configured():
        raise HTTPException(
            status_code=500,
            detail=(
                "GitHub App credentials not configured. "
                "Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY in your .env file."
            ),
        )
    try:
        app_jwt = github_app.get_app_jwt()
        resp = requests.get(
            "https://api.github.com/app/installations",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        resp.raise_for_status()
        installations = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub API error: {e}")

    synced = []
    for inst in installations:
        row = crud.create_or_update_app_installation(
            db,
            installation_id=inst["id"],
            account_login=inst["account"]["login"],
            account_type=inst["account"]["type"],
        )
        synced.append(row.org_name)

    return {"synced": synced, "count": len(synced)}


@router.post("/integrations/github", response_model=schemas.GitHubIntegration)
def create_github_integration(
    integration: schemas.GitHubIntegrationCreate,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Manually create a GitHub integration (Admin only)."""
    return crud.create_github_integration(db, integration)


@router.get("/integrations/github", response_model=List[schemas.GitHubIntegration])
def list_github_integrations(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """List all GitHub App installations / integrations."""
    return crud.get_github_integrations(db)


@router.delete("/integrations/github/{integration_id}")
def delete_github_integration(
    integration_id: int,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Delete a GitHub integration (Admin only)."""
    success = crud.delete_github_integration(db, integration_id)
    if not success:
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"message": "Integration deleted successfully"}


@router.get(
    "/integrations/github/{integration_id}/repositories",
    response_model=schemas.GitHubRepositoriesResponse,
)
def get_github_repositories(
    integration_id: int,
    page: int = 1,
    per_page: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch repositories accessible to this installation / integration."""
    integration = crud.get_github_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        # ── Resolve auth token ────────────────────────────────────────────
        if integration.installation_id:
            token = github_app.get_installation_token(integration.installation_id)
        elif integration.access_token:
            token = integration.access_token
        else:
            raise HTTPException(status_code=400,
                                detail="Integration has no access token or installation ID")

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # ── Choose correct repos endpoint ─────────────────────────────────
        org_name = integration.org_name
        if integration.account_type == "Organization":
            repos_url = f"https://api.github.com/orgs/{org_name}/repos"
        elif integration.installation_id:
            # App installs: list repos the installation can access
            repos_url = "https://api.github.com/installation/repositories"
        elif org_name.endswith(" (Personal)"):
            username = org_name.replace(" (Personal)", "")
            repos_url = f"https://api.github.com/users/{username}/repos"
        else:
            repos_url = f"https://api.github.com/orgs/{org_name}/repos"

        all_repos = []
        github_page = 1
        while True:
            response = requests.get(
                repos_url, headers=headers, params={"per_page": 100, "page": github_page}
            )
            if response.status_code == 200:
                data = response.json()
                # /installation/repositories wraps results
                repos = data.get("repositories", data) if isinstance(data, dict) else data
                if not repos:
                    break
                for repo in repos:
                    all_repos.append({
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "html_url": repo["html_url"],
                        "clone_url": repo["clone_url"],
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "default_branch": repo.get("default_branch", "main"),
                    })
                if len(repos) < 100:
                    break
                github_page += 1
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch repositories: {response.text}",
                )

        total_repos = len(all_repos)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_repos = all_repos[start_idx:end_idx]
        total_pages = (total_repos + per_page - 1) // per_page

        return {
            "repositories": paginated_repos,
            "page": page,
            "per_page": per_page,
            "total": total_repos,
            "total_pages": total_pages,
            "has_next": end_idx < total_repos,
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
    """Import selected repositories as projects (Admin only)."""
    integration = crud.get_github_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    imported = []
    skipped = []

    for repo_url in repo_urls:
        existing = crud.get_project_by_github_url(db, repo_url)
        if existing:
            skipped.append({"url": repo_url, "reason": "Already exists"})
            continue
        try:
            project_data = schemas.ProjectCreate(github_url=repo_url, integration_id=integration_id)
            project = crud.create_project(db, project_data, local_path=None)
            imported.append({"id": project.id, "url": project.github_url})
        except Exception as e:
            skipped.append({"url": repo_url, "reason": str(e)})

    return {
        "imported": imported,
        "skipped": skipped,
        "total_imported": len(imported),
        "total_skipped": len(skipped),
    }


# ==================== SLACK INTEGRATION ENDPOINTS ====================

@router.get("/integrations/slack")
def get_slack_config(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Return current Slack webhook URL and global enabled state."""
    return crud.get_slack_config(db)


@router.put("/integrations/slack")
def save_slack_config(
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Save Slack webhook URL and global enabled state (Admin only).

    If ``webhook_url`` is omitted or null the existing stored URL is preserved
    so that the UI can update the toggle without inadvertently clearing the URL.
    """
    enabled = bool(payload.get("enabled", False))

    # Determine the URL to persist
    if "webhook_url" not in payload or payload["webhook_url"] is None:
        # Keep existing URL — only update enabled flag
        existing = crud.get_slack_webhook_url_raw(db)
        webhook_url = existing
    else:
        webhook_url = (payload["webhook_url"] or "").strip()

    if webhook_url and not webhook_url.startswith("https://hooks.slack.com/"):
        raise HTTPException(
            status_code=400,
            detail="webhook_url must be a valid Slack incoming webhook URL (https://hooks.slack.com/...)",
        )
    return crud.save_slack_config(db, webhook_url, enabled)


# ==================== GITHUB APP CREDENTIALS ENDPOINTS ====================

@router.get("/integrations/github-app/config")
def get_github_app_config(
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Return masked GitHub App config (sensitive values are never returned)."""
    return crud.get_github_app_config(db)


@router.post("/integrations/github-app/config")
async def save_github_app_config(
    app_id: Optional[str] = Form(None),
    slug: Optional[str] = Form(None),
    webhook_secret: Optional[str] = Form(None),
    private_key_file: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Save GitHub App credentials (Admin only).  Private key is uploaded as a .pem file.
    
    Only fields that are provided (non-empty) will be updated.
    Sensitive values (private key, webhook secret) are stored but never returned.
    """
    private_key_pem: Optional[str] = None

    if private_key_file and private_key_file.filename:
        content = await private_key_file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded private key file is empty.")
        private_key_pem = content.decode("utf-8").strip()
        # Basic validation: must look like a PEM key
        if "-----BEGIN" not in private_key_pem:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file does not appear to be a valid PEM private key.",
            )

    # Treat empty-string form fields as "no change"
    app_id_val = (app_id or "").strip() or None
    slug_val = (slug or "").strip() or None
    secret_val = (webhook_secret or "").strip() or None

    result = crud.save_github_app_config(
        db,
        app_id=app_id_val,
        slug=slug_val,
        private_key_pem=private_key_pem,
        webhook_secret=secret_val,
    )

    # Reload the runtime github_app module so it uses the newly saved credentials
    raw = crud.get_github_app_config_raw(db)
    github_app.reload_config(
        app_id=raw["app_id"],
        slug=raw["slug"],
        private_key_pem=raw["private_key_pem"],
        webhook_secret=raw["webhook_secret"],
    )

    return result
