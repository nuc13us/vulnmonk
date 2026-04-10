"""
GitHub webhook receiver + PR scan engine.

Flow:
  1. GitHub POSTs a pull_request event to POST /webhooks/github
  2. We immediately return 200 and queue the scan as a BackgroundTask
  3. Background: fetch only the changed files via GitHub API → run opengrep →
     filter findings to changed lines → post commit status back to GitHub
"""

import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile

import requests
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import crud, models, schemas, auth, github_app
from ..database import get_db, SessionLocal

router = APIRouter()

# ==================== SEVERITY HELPERS ====================

SEVERITY_ORDER = {"INFO": 1, "WARNING": 2, "ERROR": 3}

def _normalize_severity(raw: str) -> str:
    """Map old/alternate semgrep severity names to INFO | WARNING | ERROR."""
    s = (raw or "").upper()
    if s in ("CRITICAL", "C", "ERROR"):
        return "ERROR"
    if s in ("HIGH", "H", "MEDIUM", "M", "WARNING"):
        return "WARNING"
    if s in ("LOW", "L", "INFO"):
        return "INFO"
    return "INFO"


def _should_block(findings: list, block_on_severity: str) -> bool:
    """Return True if any finding meets or exceeds the blocking threshold."""
    if block_on_severity == "none" or not block_on_severity:
        return False
    threshold = SEVERITY_ORDER.get(block_on_severity, 0)
    for f in findings:
        sev = _normalize_severity(f.get("extra", {}).get("severity", ""))
        if SEVERITY_ORDER.get(sev, 0) >= threshold:
            return True
    return False


def _should_block_trufflehog(th_findings: list, th_block_on: str) -> bool:
    """Return True if TruffleHog findings should block the PR."""
    if not th_block_on or th_block_on == "none":
        return False
    if th_block_on == "all":
        return len(th_findings) > 0
    if th_block_on == "verified":
        return any(f.get("Verified", False) for f in th_findings)
    return False


# ==================== GITHUB API HELPERS ====================

def _github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def _get_pr_files(token: str, owner: str, repo: str, pr_number: int) -> list:
    """Return list of file dicts from GitHub PR files API (up to 300 files)."""
    files = []
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
            headers=_github_headers(token),
            params={"per_page": 100, "page": page},
            timeout=30,
        )
        if resp.status_code != 200:
            break
        batch = resp.json()
        if not batch:
            break
        files.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return files


def _parse_changed_lines(patch: str) -> set:
    """
    Parse a git diff patch and return the set of new/changed line numbers.
    Only the '+' side (new file) lines count — those are what opengrep reports.
    """
    changed = set()
    if not patch:
        return changed
    for m in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch):
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        for line in range(start, start + count):
            changed.add(line)
    return changed


def _fetch_file_content(token: str, owner: str, repo: str,
                        path: str, ref: str) -> bytes | None:
    """Download a single file's content from GitHub at the given ref."""
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers=_github_headers(token),
        params={"ref": ref},
        timeout=30,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"].replace("\n", ""))
    # fallback: download_url
    dl = data.get("download_url")
    if dl:
        r2 = requests.get(dl, headers=_github_headers(token), timeout=30)
        if r2.status_code == 200:
            return r2.content
    return None


def _post_commit_status(token: str, owner: str, repo: str, sha: str,
                        state: str, description: str,
                        target_url: str = "") -> None:
    """Post a commit status to GitHub (state: pending | success | failure | error)."""
    requests.post(
        f"https://api.github.com/repos/{owner}/{repo}/statuses/{sha}",
        headers=_github_headers(token),
        json={
            "state": state,
            "description": description[:140],
            "context": "vulnmonk/pr-scan",
            "target_url": target_url,
        },
        timeout=15,
    )


def _build_pr_scan_dashboard_url(project_id: int, pr_number: int | None = None) -> str:
    """Build frontend URL for a project's PR scans page."""
    base = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/project/{project_id}"


# ==================== OPENGREP SCAN HELPERS ====================

def _run_opengrep_on_dir(scan_dir: str, exclude_rules: str = "",
                          include_rules_yaml: str = "") -> dict:
    """Run opengrep scan on a directory, return parsed JSON or {"error": ...}."""
    config_files = []
    try:
        cmd = ["opengrep", "scan", "--config", "auto"]

        if exclude_rules:
            for rule in exclude_rules.split(","):
                rule = rule.strip()
                if rule:
                    cmd += ["--exclude-rule", rule]

        if include_rules_yaml and include_rules_yaml.strip():
            try:
                yaml_files = json.loads(include_rules_yaml)
                if isinstance(yaml_files, list):
                    for yf in yaml_files:
                        if isinstance(yf, dict) and "content" in yf:
                            with tempfile.NamedTemporaryFile(
                                mode="w", suffix=".yaml", delete=False, dir=scan_dir
                            ) as f:
                                f.write(yf["content"])
                                config_files.append(f.name)
                                cmd += ["--config", f.name]
            except (json.JSONDecodeError, ValueError):
                pass

        cmd += [".", "--json"]
        result = subprocess.run(
            cmd, cwd=scan_dir, capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}
    finally:
        for p in config_files:
            if os.path.exists(p):
                os.remove(p)


# ==================== TRUFFLEHOG SCAN HELPERS ====================

def _run_trufflehog_on_dir(scan_dir: str, exclude_detectors_str: str = "") -> list:
    """
    Run trufflehog filesystem scan on a directory already populated with changed files.
    Returns a list of finding objects (SourceMetadata present) or [] on error.
    """
    try:
        cmd = ["trufflehog", "filesystem", scan_dir, "--json"]
        if exclude_detectors_str and exclude_detectors_str.strip():
            cmd.append(f"--exclude-detectors={exclude_detectors_str.strip()}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        findings = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # Only include actual findings — they have SourceMetadata with Filesystem data
                if "SourceMetadata" in obj:
                    src_data = obj.get("SourceMetadata", {}).get("Data", {})
                    if "Filesystem" in src_data:
                        findings.append(obj)
            except json.JSONDecodeError:
                continue
        return findings
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


# ==================== CORE PR SCAN LOGIC ====================

def _run_pr_scan(pr_scan_id: int, project_id: int, pr_number: int,
                 head_sha: str, owner: str, repo: str,
                 access_token: str, pr_files: list,
                 block_on_severity: str, project_exclude: str,
                 project_include_yaml: str,
                 dashboard_url: str = "",
                 th_exclude_detectors: str = "",
                 th_block_on: str = "none") -> None:
    """
    Background task: download changed files, scan with opengrep + trufflehog,
    filter findings to changed lines only, post commit status, update DB.
    """
    db = SessionLocal()
    scan_dir = tempfile.mkdtemp(prefix=f"pr-{pr_number}-")

    try:
        # ── 1. Build changed-lines map and download files ──────────────────
        file_changed_lines: dict[str, set] = {}  # relative path → set of line numbers

        for file_info in pr_files:
            status = file_info.get("status", "")
            if status == "removed":
                continue  # deleted files have no new findings
            relative_path = file_info.get("filename", "")
            patch = file_info.get("patch", "")

            file_changed_lines[relative_path] = _parse_changed_lines(patch)

            content = _fetch_file_content(access_token, owner, repo,
                                          relative_path, head_sha)
            if content is None:
                continue

            dest = os.path.join(scan_dir, relative_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(content)

        # ── 2. Run opengrep ────────────────────────────────────────────────
        scan_result = _run_opengrep_on_dir(
            scan_dir, project_exclude, project_include_yaml
        )

        if isinstance(scan_result, dict) and "error" in scan_result:
            _post_commit_status(access_token, owner, repo, head_sha,
                                "error", f"Scan error: {scan_result['error'][:100]}",
                                target_url=dashboard_url)
            crud.update_pr_scan(db, pr_scan_id, "error", 0, scan_result)
            return

        # ── 3. Filter opengrep findings to changed lines only ──────────────
        all_findings = scan_result.get("results", []) if isinstance(scan_result, dict) else []
        filtered = []

        for finding in all_findings:
            path = finding.get("path", "")
            # opengrep returns paths relative to cwd (scan_dir), strip it
            if path.startswith(scan_dir):
                path = path[len(scan_dir):].lstrip("/")
                finding = dict(finding)
                finding["path"] = path

            start = finding.get("start", {})
            line = start.get("line", 0) if isinstance(start, dict) else 0

            changed = file_changed_lines.get(path, set())
            if line in changed:
                finding["unique_key"] = f"{path}@{line}@{finding.get('check_id', 'unknown')}"
                finding["status"] = "open"
                filtered.append(finding)

        # ── 4. Run trufflehog on the same downloaded files ─────────────────
        th_findings_raw = _run_trufflehog_on_dir(scan_dir, th_exclude_detectors)
        th_filtered = []

        for th_finding in th_findings_raw:
            fs_data = th_finding.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {})
            abs_path = fs_data.get("file", "")
            line = fs_data.get("line", 0) if fs_data.get("line") else 0

            # Strip scan_dir prefix to get path relative to repo root
            if abs_path.startswith(scan_dir):
                rel_path = abs_path[len(scan_dir):].lstrip("/")
            else:
                rel_path = abs_path

            changed = file_changed_lines.get(rel_path, set())
            if line in changed:
                th_finding = dict(th_finding)
                th_finding["_pr_file"] = rel_path
                th_filtered.append(th_finding)

        # ── 5. Determine commit status ─────────────────────────────────────
        block_sast = _should_block(filtered, block_on_severity)
        block_th = _should_block_trufflehog(th_filtered, th_block_on)
        block = block_sast or block_th
        count = len(filtered)
        th_count = len(th_filtered)

        if count == 0 and th_count == 0:
            gh_state = "success"
            description = "No security issues or secrets found in changed lines."
        elif block:
            reasons = []
            if block_sast:
                reasons.append(f"{count} SAST issue(s) ({block_on_severity}+)")
            if block_th:
                verified_count = sum(1 for f in th_filtered if f.get("Verified"))
                reasons.append(f"{th_count} secret(s) ({verified_count} verified)")
            gh_state = "failure"
            description = f"PR blocked — {', '.join(reasons)}."
        else:
            parts = []
            if count > 0:
                parts.append(f"{count} SAST issue(s)")
            if th_count > 0:
                parts.append(f"{th_count} secret(s)")
            gh_state = "success"
            description = (", ".join(parts) + " found (below blocking threshold).") if parts else "No issues found."

        _post_commit_status(access_token, owner, repo, head_sha,
                            gh_state, description, target_url=dashboard_url)

        result_payload = {
            "results": filtered,
            "total": count,
            "trufflehog_results": th_filtered,
            "trufflehog_total": th_count,
        }
        scan_status = "failure" if block else "success"
        crud.update_pr_scan(db, pr_scan_id, scan_status, count, result_payload)

    except Exception as exc:
        try:
            _post_commit_status(access_token, owner, repo, head_sha,
                                "error", f"VulnMonk internal error: {str(exc)[:80]}",
                                target_url=dashboard_url)
            crud.update_pr_scan(db, pr_scan_id, "error", 0,
                                {"error": str(exc)})
        except Exception:
            pass
    finally:
        db.close()
        shutil.rmtree(scan_dir, ignore_errors=True)


# ==================== WEBHOOK ENDPOINT ====================

@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Receive GitHub webhook events (GitHub App).
    Authentication: single App-level HMAC-SHA256 secret — no per-project secrets.

    Handles:
    - installation / installation_repositories  → manage GitHubIntegration records
    - pull_request (opened / synchronize / reopened) → trigger PR scan
    """
    body = await request.body()

    # ── Verify App webhook signature ───────────────────────────────────────
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not github_app.verify_webhook_signature(body, sig_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # ── Parse payload ──────────────────────────────────────────────────────
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = request.headers.get("X-GitHub-Event", "")

    # ── Handle App installation events ────────────────────────────────────
    if event_type in ("installation", "installation_repositories"):
        action = payload.get("action", "")
        installation = payload.get("installation", {})
        installation_id = installation.get("id")
        account = installation.get("account", {})
        account_login = account.get("login", "")
        account_type = account.get("type", "User")  # "User" or "Organization"

        if action in ("created", "new_permissions_accepted", "unsuspend"):
            crud.create_or_update_app_installation(
                db, installation_id, account_login, account_type
            )
            return {"status": "ok", "action": f"installation {action}", "account": account_login}

        if action in ("deleted", "suspend"):
            crud.delete_github_integration_by_installation_id(db, installation_id)
            return {"status": "ok", "action": f"installation {action}", "account": account_login}

        return {"status": "ignored", "reason": f"installation action '{action}' not handled"}

    # ── Handle PR events ───────────────────────────────────────────────────
    if event_type != "pull_request":
        return {"status": "ignored", "reason": f"event type '{event_type}' not handled"}

    action = payload.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": f"action '{action}' not monitored"}

    repo_full_name = payload.get("repository", {}).get("full_name", "")
    if not repo_full_name:
        raise HTTPException(status_code=400, detail="Missing repository.full_name")

    # ── Resolve project + scan settings ───────────────────────────────────
    project, block_on_severity, th_block_on = crud.get_project_and_severity_for_pr(db, repo_full_name)
    if not project:
        return {"status": "ignored", "reason": "Repo not tracked or PR checks disabled"}

    # ── Get installation access token ──────────────────────────────────────
    installation_id = payload.get("installation", {}).get("id")
    if not installation_id:
        # Fall back to stored OAuth token if no installation context
        integration = crud.get_github_integration(db, project.integration_id) if project.integration_id else None
        if not integration:
            owner = repo_full_name.split("/")[0]
            integrations = crud.get_github_integrations(db)
            integration = next(
                (i for i in integrations if owner in (i.org_name, f"{owner} (Personal)")),
                None,
            )
        if not integration:
            raise HTTPException(status_code=400,
                                detail=f"No GitHub integration found for '{repo_full_name}'")
        access_token = integration.access_token
    elif github_app.is_configured():
        try:
            access_token = github_app.get_installation_token(installation_id)
        except Exception as exc:
            raise HTTPException(status_code=500,
                                detail=f"Failed to mint installation token: {exc}")
    else:
        raise HTTPException(status_code=500,
                            detail="GitHub App credentials not configured (GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY)")

    # ── Extract PR details ─────────────────────────────────────────────────
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    pr_title = pr.get("title", "")
    head_sha = pr.get("head", {}).get("sha", "")
    base_branch = pr.get("base", {}).get("ref", "")
    head_branch = pr.get("head", {}).get("ref", "")
    owner, repo_name = repo_full_name.split("/", 1)

    if not head_sha or not pr_number:
        raise HTTPException(status_code=400, detail="Missing PR head SHA or number")

    dashboard_url = _build_pr_scan_dashboard_url(project.id, pr_number)

    # ── Post 'pending' status immediately ─────────────────────────────────
    _post_commit_status(access_token, owner, repo_name, head_sha,
                        "pending", "VulnMonk PR scan in progress...",
                        target_url=dashboard_url)

    # ── Fetch changed files from GitHub ───────────────────────────────────
    pr_files = _get_pr_files(access_token, owner, repo_name, pr_number)
    changed_filenames = [f["filename"] for f in pr_files if f.get("status") != "removed"]

    # ── Create DB record ───────────────────────────────────────────────────
    pr_scan_record = crud.create_pr_scan(
        db,
        project_id=project.id,
        pr_number=pr_number,
        pr_title=pr_title,
        head_sha=head_sha,
        base_branch=base_branch,
        head_branch=head_branch,
        repo_full_name=repo_full_name,
        changed_files=changed_filenames,
    )

    # ── Queue background scan ──────────────────────────────────────────────
    # Merge project + global TruffleHog exclude detectors
    th_project_detectors = [d.strip() for d in (project.trufflehog_exclude_detectors or "").split(",") if d.strip()]
    th_global_config = crud.get_global_config(db, "global_trufflehog_exclude_detectors")
    th_global_detectors = [d.strip() for d in (th_global_config.value if th_global_config else "").split(",") if d.strip()]
    th_exclude_detectors = ",".join(set(th_project_detectors + th_global_detectors))

    background_tasks.add_task(
        _run_pr_scan,
        pr_scan_id=pr_scan_record.id,
        project_id=project.id,
        pr_number=pr_number,
        head_sha=head_sha,
        owner=owner,
        repo=repo_name,
        access_token=access_token,
        pr_files=pr_files,
        block_on_severity=block_on_severity,
        project_exclude=project.exclude_rules or "",
        project_include_yaml=project.include_rules_yaml or "",
        dashboard_url=dashboard_url,
        th_exclude_detectors=th_exclude_detectors,
        th_block_on=th_block_on or "none",
    )

    return {"status": "queued", "pr_scan_id": pr_scan_record.id}


# ==================== PR CONFIG ENDPOINTS ====================

@router.get("/projects/{project_id}/pr-check-config")
def get_pr_check_config(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    config = crud.get_pr_check_config(db, project_id)
    return schemas.PRCheckConfigOut.from_orm(config)


@router.put("/projects/{project_id}/pr-check-config")
def save_pr_check_config(
    project_id: int,
    payload: schemas.PRCheckConfigUpdate,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db),
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.block_on_severity not in ("none", "INFO", "WARNING", "ERROR"):
        raise HTTPException(status_code=400,
                            detail="block_on_severity must be none, INFO, WARNING, or ERROR")

    if payload.th_block_on not in ("none", "verified", "all"):
        raise HTTPException(status_code=400,
                            detail="th_block_on must be none, verified, or all")

    # Generate a secret if enabling for the first time and none provided
    secret = payload.webhook_secret
    if payload.enabled and not secret:
        secret = secrets.token_hex(32)

    config = crud.save_pr_check_config(
        db, project_id,
        enabled=payload.enabled,
        webhook_secret=secret or "",
        block_on_severity=payload.block_on_severity,
        th_block_on=payload.th_block_on,
    )
    return schemas.PRCheckConfigOut.from_orm(config)


# ==================== PR SCAN HISTORY ENDPOINTS ====================

@router.get("/projects/{project_id}/pr-scans/")
def list_pr_scans(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    scans = crud.get_pr_scans(db, project_id)
    return [
        {
            "id": s.id,
            "pr_number": s.pr_number,
            "pr_title": s.pr_title,
            "head_sha": s.head_sha[:8] if s.head_sha else "",
            "base_branch": s.base_branch,
            "head_branch": s.head_branch,
            "repo_full_name": s.repo_full_name,
            "status": s.status,
            "findings_count": s.findings_count,
            "changed_files": s.changed_files or [],
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in scans
    ]


@router.get("/pr-scans/{pr_scan_id}/")
def get_pr_scan_detail(
    pr_scan_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    scan = crud.get_pr_scan(db, pr_scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="PR scan not found")
    return {
        "id": scan.id,
        "project_id": scan.project_id,
        "pr_number": scan.pr_number,
        "pr_title": scan.pr_title,
        "head_sha": scan.head_sha,
        "base_branch": scan.base_branch,
        "head_branch": scan.head_branch,
        "repo_full_name": scan.repo_full_name,
        "status": scan.status,
        "findings_count": scan.findings_count,
        "result_json": scan.result_json,
        "changed_files": scan.changed_files or [],
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
    }
