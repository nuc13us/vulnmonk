# VulnMonk SAST Dashboard - Copilot Instructions

## Project Overview
VulnMonk is a SAST + secret scanning dashboard for managing security scan results across GitHub repositories. It provides JWT-authenticated access to add projects, trigger OpenGrep (SAST) and TruffleHog (secret) scans, manage exclude/include rules, and run automatic PR scan checks via a GitHub App.

**Tech Stack:**
- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite, JWT auth (python-jose + bcrypt)
- **Frontend:** React 19, JavaScript, CSS
- **SAST Scanner:** OpenGrep
- **Secret Scanner:** TruffleHog
- **GitHub integration:** GitHub App (JWT + installation tokens via RSA private key)

## Project Structure
```
vulnmonk/
├── backend/
│   ├── api.py              # Router aggregator — includes all sub-routers
│   ├── auth.py             # JWT auth helpers + role guards
│   ├── crud.py             # Database CRUD operations
│   ├── database.py         # SQLAlchemy engine + session
│   ├── models.py           # ORM models (see Models section)
│   ├── schemas.py          # Pydantic schemas
│   ├── main.py             # FastAPI app entry point (loads .env, mounts router)
│   ├── github_app.py       # GitHub App JWT + installation token helpers
│   └── routes/
│       ├── auth.py         # POST /auth/login, GET /auth/me, POST /auth/change-password
│       ├── projects.py     # Projects, SAST scans, TruffleHog scans, FP management, global config
│       ├── integrations.py # GitHub App install URL, sync, list/delete integrations, repo import
│       └── webhooks.py     # GitHub webhook handler (PR scans), PR check config, PR scan results
├── frontend/
│   ├── src/
│   │   ├── App.js          # Root layout + auth guard + routing
│   │   ├── App.css         # All styles
│   │   ├── api.js          # API client (uses apiFetch for 401 handling)
│   │   └── components/
│   │       ├── Login.js
│   │       ├── Dashboard.js
│   │       ├── ProjectsView.js
│   │       ├── ScanResults.js
│   │       ├── Configurations.js
│   │       ├── Integrations.js
│   │       ├── Account.js
│   │       └── Users.js
│   └── package.json
├── projects/               # Cloned repos (auto-created at runtime)
├── add_user.py             # CLI: create/list users
├── view_db.py              # CLI: view all database tables
└── vulnmonk.db             # SQLite database (auto-created)
```

## Models (`backend/models.py`)
| Model | Table | Purpose |
|---|---|---|
| `Project` | `projects` | GitHub URL, exclude/include rules, TruffleHog exclude detectors, global rule preferences, integration link |
| `ScanResult` | `scan_results` | OpenGrep scan output (JSON), findings_count |
| `FalsePositive` | `false_positives` | SAST FP markers keyed by `path@rule_id@content_hash` |
| `TrufflehogScanResult` | `trufflehog_scan_results` | TruffleHog scan output (JSON), findings_count |
| `TrufflehogFalsePositive` | `trufflehog_false_positives` | Secret scan FP markers keyed by `path@raw_hash@detector` |
| `PRScanResult` | `pr_scan_results` | PR-triggered scan results (SAST + TH), status, changed files |
| `PRCheckConfig` | `pr_check_configs` | Per-project PR blocking settings (severity threshold, TH block mode) |
| `GitHubIntegration` | `github_integrations` | GitHub App installations (org/user, installation_id) |
| `User` | `users` | Username, hashed password, role (admin/user), is_active |
| `GlobalConfiguration` | `global_configurations` | Key/value store for global exclude rules, include rules, PR scan toggle |

## Key Features
- JWT auth with 30-day tokens; 401 auto-redirects to login
- Role-based access: Admin (full) and User (view-only)
- **GitHub App integration** — installs via `GITHUB_APP_ID` + RSA private key; tokens are per-installation and auto-rotated; no OAuth tokens
- **SAST scanning** — on-demand OpenGrep scans; per-project and global exclude/include YAML rules merged at scan time
- **Secret scanning** — on-demand TruffleHog scans; per-project and global exclude detector lists
- **PR scan checks** — GitHub App webhook (`POST /api/webhooks/github`) triggers SAST + TruffleHog on changed files only; posts `vulnmonk/pr-scan` commit status back to GitHub
- **PR blocking** — configurable per-project: block on SAST severity (INFO/WARNING/ERROR) or TruffleHog findings (verified-only or all)
- **False positive management** — SAST FPs keyed by `path@rule_id@content_hash` (stable across line shifts); TH FPs keyed by `path@raw_hash@detector`
- **Global PR scan toggle** — enable/disable PR checks globally from Integrations page
- Scan errors surfaced in the UI

## Development

### Start servers
```bash
# Backend (from project root)
uvicorn backend.main:app --reload   # http://localhost:8000

# Frontend
cd frontend && npm start             # http://localhost:3000
```

### Add a new feature
1. **Backend:** add endpoint in the appropriate `routes/` file, CRUD in `crud.py`, schema in `schemas.py`
2. **Frontend:** API call in `api.js`, component in `components/`
3. **Schema changes:** delete `vulnmonk.db` and restart backend to recreate

### Notes
- **CORS** is handled by nginx in production; no CORSMiddleware in FastAPI
- All authenticated API calls use `apiFetch()` in `api.js` — fires `auth:expired` on 401 so App.js redirects to login
- Backend routes have no `/api` prefix — nginx strips it when proxying from port 3000 → backend:8000
- **Webhook URL** for the GitHub App: `http://YOUR_SERVER_IP:3000/api/webhooks/github`
- OpenGrep scan errors return `{"error": "..."}` in result_json; the UI reads this and shows it in the scan logs
- Scan timestamps from the backend have no timezone suffix — `formatDate()` in `ScanResults.js` appends `Z` before parsing
- `github_app.py` supports both file-path and inline PEM for `GITHUB_APP_PRIVATE_KEY`
- In-memory sets `scanning_projects` and `trufflehog_scanning_projects` in `routes/projects.py` prevent concurrent scans on the same project
