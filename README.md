# VulnMonk SAST Dashboard

A full-stack dashboard for managing SAST scan results across GitHub repositories.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite, JWT auth
- **Frontend:** React 19, JavaScript, CSS
- **Scanner:** OpenGrep

## Setup

### Step 1 — Configure Environment Variables

Create `backend/.env` before starting the backend or running Docker:

```bash
cp backend/.env.example backend/.env
```

Then edit `backend/.env`:

```env
# Required — generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-secret-key-here
JWT_EXPIRE_DAYS=30

# GitHub OAuth — required only if you want to use the GitHub integration
# See GITHUB_OAUTH_SETUP.md for step-by-step instructions
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_REDIRECT_URI=http://YOUR_SERVER_IP_OR_DOMAIN:3000/integrations
```

> **GitHub OAuth setup:** See [GITHUB_OAUTH_SETUP.md](GITHUB_OAUTH_SETUP.md) for a step-by-step guide on creating a GitHub OAuth App and getting the `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` values.

---

### Step 2 — Backend

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload      # runs on http://localhost:8000
```

### Step 3 — Frontend

```bash
cd frontend
npm install
npm start   # runs on http://localhost:3000
```

---

### First Login — Create an Admin User

After the backend starts, create your first admin user:

```bash
python3 add_user.py <username> <password> admin
```

---

## Docker

```bash
docker compose up --build
```

Data is persisted in Docker named volumes (`vulnmonk-data`, `vulnmonk-projects`).

Make sure `backend/.env` exists with the values from Step 1 above — it is loaded automatically at runtime.

For overriding the frontend API URL at build time (non-Docker or custom deployments):

```
REACT_APP_API_BASE_URL=http://<your-host>:8000
```

**CLI tools inside the container:**
```bash
docker exec -it vulnmonk-backend python add_user.py <username> <password> admin
docker exec -it vulnmonk-backend python add_user.py --list
```

## User Management (CLI)

```bash
python3 add_user.py          # create a user
python3 add_user.py --list   # list all users
python3 view_db.py           # view database contents
```

## API Docs

Swagger UI: http://localhost:8000/docs

## Permissions

| Action                       | Admin | User |
|------------------------------|:-----:|:----:|
| Trigger scans                | ✅    | ❌   |
| Add / manage projects        | ✅    | ❌   |
| Mark false positives         | ✅    | ❌   |
| Manage users                 | ✅    | ❌   |
| View projects & scan results | ✅    | ✅   |
| Change own password          | ✅    | ✅   |

## Project Structure

```
vulnmonk/
├── backend/       # FastAPI app (api.py, auth.py, crud.py, models.py, schemas.py)
├── frontend/      # React app (src/components/, App.js, api.js)
├── projects/      # Cloned repos (auto-created at runtime)
├── add_user.py    # CLI user management
├── view_db.py     # Database viewer
└── vulnmonk.db    # SQLite database (auto-created)
```

## License

MIT — see [LICENSE](LICENSE).
