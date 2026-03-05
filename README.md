# VulnMonk SAST Dashboard

A full-stack dashboard for managing SAST scan results across GitHub repositories.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite, JWT auth
- **Frontend:** React 19, JavaScript, CSS
- **Scanner:** OpenGrep

## Setup

### Backend

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env   # set JWT_SECRET_KEY
uvicorn backend.main:app --reload      # runs on http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm start   # runs on http://localhost:3000
```

## Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs

Data is persisted in Docker named volumes (`vulnmonk-data`, `vulnmonk-projects`).

**`backend/.env`** is loaded automatically at runtime. Create it with:
```
JWT_SECRET_KEY=<random-secret>
JWT_EXPIRE_DAYS=30
CORS_ORIGINS=http://localhost:3000

# GitHub OAuth (optional — needed for github integration)
GITHUB_CLIENT_ID=<your-github-oauth-app-client-id>
GITHUB_CLIENT_SECRET=<your-github-oauth-app-client-secret>
GITHUB_REDIRECT_URI=http://localhost:3000/integrations
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

For overriding the frontend API URL at build time:
```
REACT_APP_API_BASE_URL=http://<your-host>:8000
```

**CLI tools inside the container:**
```bash
docker exec -it vulnmonk-backend python add_user.py
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
