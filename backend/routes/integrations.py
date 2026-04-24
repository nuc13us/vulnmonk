import os

import requests
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import crud, models, schemas, auth, github_app
from ..database import get_db

router = APIRouter()

# ==================== GITHUB APP INTEGRATION ENDPOINTS ====================

@router.get("/integrations/github/app-install-url")
def get_github_app_install_url(
    current_user: models.User = Depends(auth.get_current_active_admin)
):
    """Return the URL to install the GitHub App on an org or personal account."""
    if not github_app.GITHUB_APP_SLUG:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_APP_SLUG is not configured. Add it to your .env file.",
        )
    return {"install_url": github_app.get_install_url()}


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
    """Save Slack webhook URL and global enabled state (Admin only)."""
    webhook_url = (payload.get("webhook_url") or "").strip()
    enabled = bool(payload.get("enabled", False))
    if webhook_url and not webhook_url.startswith("https://hooks.slack.com/"):
        raise HTTPException(
            status_code=400,
            detail="webhook_url must be a valid Slack incoming webhook URL (https://hooks.slack.com/...)",
        )
    return crud.save_slack_config(db, webhook_url, enabled)
