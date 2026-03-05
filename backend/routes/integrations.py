import os
import uuid

import requests
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import crud, models, schemas, auth
from ..database import get_db

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:3000/integrations")

router = APIRouter()

# ==================== GITHUB INTEGRATION ENDPOINTS ====================

@router.get("/integrations/github/auth-url")
def get_github_auth_url(
    current_user: models.User = Depends(auth.get_current_active_admin)
):
    """Get GitHub OAuth authorization URL (Admin only)."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables.",
        )

    state = str(uuid.uuid4())
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
    """Handle GitHub OAuth callback and create/update integrations (Admin only)."""
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is required")
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth is not configured")

    try:
        # Exchange code for access token
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code for access token: {token_response.text}",
            )

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            error_msg = token_data.get("error_description", token_data.get("error", "Unknown error"))
            raise HTTPException(status_code=400, detail=f"GitHub error: {error_msg}")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Resolve GitHub username from repos
        github_login = None
        repos_response = requests.get("https://api.github.com/user/repos?per_page=1", headers=headers)
        if repos_response.status_code == 200 and repos_response.json():
            repos = repos_response.json()
            if repos:
                github_login = repos[0]["owner"]["login"]

        if not github_login:
            org_memberships_response = requests.get(
                "https://api.github.com/user/memberships/orgs", headers=headers
            )
            if org_memberships_response.status_code == 200:
                memberships = org_memberships_response.json()
                if memberships:
                    github_login = memberships[0]["user"]["login"]

        # Get user's organizations
        orgs_response = requests.get("https://api.github.com/user/orgs", headers=headers)
        organizations = []
        if orgs_response.status_code == 200:
            organizations = [org["login"] for org in orgs_response.json()]

        created_integrations = []
        updated_integrations = []

        # Personal account integration
        if github_login:
            personal_org_name = f"{github_login} (Personal)"
            existing = db.query(models.GitHubIntegration).filter(
                models.GitHubIntegration.org_name == personal_org_name
            ).first()
            if existing:
                existing.access_token = access_token
                existing.organizations = []
                db.commit()
                updated_integrations.append(personal_org_name)
            else:
                crud.create_github_integration(
                    db,
                    schemas.GitHubIntegrationCreate(
                        org_name=personal_org_name, access_token=access_token, organizations=[]
                    ),
                )
                created_integrations.append(personal_org_name)

        # Organization integrations
        for org_name in organizations:
            existing = db.query(models.GitHubIntegration).filter(
                models.GitHubIntegration.org_name == org_name
            ).first()
            if existing:
                existing.access_token = access_token
                existing.organizations = []
                db.commit()
                updated_integrations.append(org_name)
            else:
                crud.create_github_integration(
                    db,
                    schemas.GitHubIntegrationCreate(
                        org_name=org_name, access_token=access_token, organizations=[]
                    ),
                )
                created_integrations.append(org_name)

        total = len(created_integrations) + len(updated_integrations)
        message = f"Successfully connected {total} integration(s)"
        if created_integrations:
            message += f" (Created: {', '.join(created_integrations)})"
        if updated_integrations:
            message += f" (Updated: {', '.join(updated_integrations)})"

        return {
            "github_user": github_login,
            "organizations": organizations,
            "total_integrations": total,
            "created": created_integrations,
            "updated": updated_integrations,
            "message": message,
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"GitHub API error: {str(e)}")


@router.post("/integrations/github", response_model=schemas.GitHubIntegration)
def create_github_integration(
    integration: schemas.GitHubIntegrationCreate,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Create a new GitHub integration (Admin only)."""
    return crud.create_github_integration(db, integration)


@router.get("/integrations/github", response_model=List[schemas.GitHubIntegration])
def list_github_integrations(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """List all GitHub integrations."""
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
    """Fetch repositories from the specific organization/account with pagination."""
    integration = crud.get_github_integration(db, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        headers = {
            "Authorization": f"Bearer {integration.access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        org_name = integration.org_name
        if org_name.endswith(" (Personal)"):
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
                repos = response.json()
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
                    detail=f"Failed to fetch repositories from GitHub: {response.text}",
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
