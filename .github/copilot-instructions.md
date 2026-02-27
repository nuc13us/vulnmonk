# VulnMonk SAST Dashboard - Copilot Instructions

## Project Overview
VulnMonk is a SAST dashboard for managing security scan results across GitHub repositories. It provides JWT-authenticated access to add projects, trigger OpenGrep scans, view vulnerabilities, and manage exclude/include rules.

**Tech Stack:**
- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite, JWT auth (python-jose + bcrypt)
- **Frontend:** React 19, JavaScript, CSS
- **Scanner:** OpenGrep

## Project Structure
```
vulnmonk/
├── backend/
│   ├── api.py              # All FastAPI routes
│   ├── auth.py             # JWT auth helpers
│   ├── crud.py             # Database CRUD operations
│   ├── database.py         # SQLAlchemy engine + session
│   ├── models.py           # ORM models
│   ├── schemas.py          # Pydantic schemas
│   ├── main.py             # FastAPI app entry point
│   └── requirements.txt
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
├── projects/               # Cloned repos (auto-created)
├── add_user.py             # CLI: create/list users
├── view_db.py              # CLI: view database contents
└── vulnmonk.db             # SQLite database (auto-created)
```

## Key Features
- JWT auth with 30-day tokens; 401 auto-redirects to login
- Role-based access: Admin (full) and User (view-only)
- GitHub OAuth integration for private repo access
- On-demand OpenGrep scans with per-project exclude/include YAML rules
- Global exclude/include rules merged at scan time
- False positive management per finding
- Scan errors (e.g. opengrep not found) surfaced in the UI
- Project URL navigation (`/project/:id`) fetches project directly if not in local list

## Development

### Start servers
```bash
# Backend (from project root)
uvicorn backend.main:app --reload   # http://localhost:8000

# Frontend
cd frontend && npm start             # http://localhost:3000
```

### Add a new feature
1. **Backend:** endpoint in `api.py`, CRUD in `crud.py`, schema in `schemas.py`
2. **Frontend:** API call in `api.js`, component in `components/`
3. **Schema changes:** delete `vulnmonk.db` and restart backend to recreate

### Notes
- CORS is enabled for `localhost:3000`
- All authenticated API calls use `apiFetch()` in `api.js` — it fires `auth:expired` on 401 so App.js redirects to login
- `run_opengrep_scan()` in `api.py` returns `{"error": "..."}` on failure; `trigger_scan` raises HTTP 500 so the UI shows the error in the logs
- Scan timestamps from the backend have no timezone suffix — `formatDate()` in `ScanResults.js` appends `Z` before parsing
