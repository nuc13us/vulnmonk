# VulnMonk SAST Dashboard

A full-stack dashboard for managing SAST scan results and secret scanning across GitHub repositories.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite, JWT auth
- **Frontend:** React 19, JavaScript, CSS
- **SAST Scanner:** OpenGrep
- **Secret Scanner:** TruffleHog

## Setup

### 1. Configure Environment Variables

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```env
# Required — generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-secret-key-here
JWT_EXPIRE_DAYS=30

# GitHub App — required for PR scan checks and private repo access
GITHUB_APP_ID=
GITHUB_APP_SLUG=
GITHUB_APP_PRIVATE_KEY=backend/your-app.private-key.pem

FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
```

> **GitHub App setup:** See [GITHUB_AUTH_SETUP.md](GITHUB_AUTH_SETUP.md).

### 2. Backend

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload   # http://localhost:8000
```

> Ensure `opengrep` and `trufflehog` are on your `PATH` for local dev. Both are pre-installed in the Docker image.
> - OpenGrep: https://github.com/opengrep/opengrep/releases/latest
> - TruffleHog: `brew install trufflehog` or https://github.com/trufflesecurity/trufflehog/releases/latest

### 3. Frontend

```bash
cd frontend && npm install && npm start   # http://localhost:3000
```

### 4. Create an Admin User

```bash
python3 add_user.py <username> <password> admin
```

---

## Docker

```bash
docker compose up --build
```

If you hit a `Module not found` build error, force a clean build:
```bash
docker compose build --no-cache && docker compose up
```

CLI tools inside the container:
```bash
docker exec -it vulnmonk-backend python add_user.py <username> <password> admin
docker exec -it vulnmonk-backend python add_user.py --list
```

---

## Features

- **SAST scanning** — on-demand OpenGrep scans with per-project and global exclude/include YAML rules
- **Secret scanning** — on-demand TruffleHog scans with per-project and global exclude detector lists
- **PR scan checks** — automatic SAST + TruffleHog scans on pull requests via GitHub App webhooks
- **PR blocking** — fail `vulnmonk/pr-scan` status check based on SAST severity threshold or TruffleHog findings
- **False positive management** — mark/unmark findings per `path@rule_id` or `path@raw_hash@detector`
- **Role-based access** — Admin (full control) and User (view-only)
- **Scan history** — per-project history with finding counts and timestamps

## Permissions

| Action | Admin | User |
|---|:---:|:---:|
| Trigger SAST / secret scans | ✅ | ❌ |
| Add / manage projects | ✅ | ❌ |
| Mark false positives | ✅ | ❌ |
| Configure PR scan settings | ✅ | ❌ |
| Configure exclude rules/detectors | ✅ | ❌ |
| Manage users | ✅ | ❌ |
| View projects & scan results | ✅ | ✅ |
| Change own password | ✅ | ✅ |

## User Management (CLI)

```bash
python3 add_user.py                          # create a user
python3 add_user.py --list                   # list all users
python3 view_db.py                           # view database contents
```

## API Docs

Swagger UI: `http://YOUR_SERVER_IP:8000/docs`

## Project Structure

```
vulnmonk/
├── backend/
│   ├── main.py             # FastAPI app entry point
│   ├── models.py           # ORM models
│   ├── schemas.py          # Pydantic schemas
│   ├── crud.py             # Database operations
│   ├── auth.py             # JWT auth helpers
│   └── routes/
│       ├── projects.py     # Project, SAST & TruffleHog scan endpoints
│       ├── webhooks.py     # GitHub App webhook handler (PR scans)
│       ├── auth.py         # Login / token endpoints
│       └── integrations.py # GitHub integration endpoints
├── frontend/               # React app
├── add_user.py             # CLI user management
├── view_db.py              # Database viewer
└── vulnmonk.db             # SQLite database (auto-created)
```

## License

MIT — see [LICENSE](LICENSE).
