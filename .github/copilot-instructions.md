# VulnMonk SAST Dashboard - Copilot Instructions

## Project Overview
VulnMonk is a SAST (Static Application Security Testing) dashboard built to manage security scan results across multiple GitHub repositories. The dashboard provides a user-friendly interface to add projects, trigger scans, view vulnerabilities, and manage exclude rules.

**Tech Stack:**
- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite
- **Frontend:** React 19, JavaScript, CSS
- **Database:** SQLite (file-based at `vulnmonk.db`)
- **Scan Tool:** SAST scanning tools (Semgrep, OpenGrep, etc.)

## Project Structure
```
vulnmonk/
├── backend/
│   ├── api.py              # FastAPI routes and endpoints
│   ├── crud.py             # Database CRUD operations
│   ├── database.py         # Database connection and session
│   ├── models.py           # SQLAlchemy ORM models
│   ├── schemas.py          # Pydantic validation schemas
│   ├── main.py             # FastAPI application entry point
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.js          # Main React app component
│   │   ├── App.css         # Global styles (sidebar, topbar, cards, badges, logs)
│   │   ├── index.js        # React entry point
│   │   ├── api.js          # API client functions
│   │   └── components/
│   │       ├── ProjectList.js    # Projects list component
│   │       └── ScanResults.js    # Scan results and detail view
│   ├── package.json        # Node dependencies
│   └── public/
│       └── index.html      # HTML template
├── projects/               # Cloned GitHub repositories (created at runtime)
├── repos/                  # Additional repository storage
├── vulnmonk.db            # SQLite database file (created at runtime)
└── README.md              # Project documentation
```

## Key Features Implemented
- [x] **Project Management:** Add projects via GitHub URL, clone to local storage
- [x] **Scan Triggering:** Run security scans from the UI with configurable exclude rules
- [x] **Scan History:** View all scans for a project with timestamps and finding counts
- [x] **Vulnerability Details:** View detailed scan results in a table with severity badges (Critical=red, High=orange, Medium=yellow, Low=cyan)
- [x] **Exclude Rules:** Set per-project security rules to exclude from scans
- [x] **Enterprise UI:** Sidebar navigation, topbar, card-based layout, log/status area for user feedback
- [x] **Real-time Updates:** Scan logs display status during operations

## Backend Setup & Running

### Install Dependencies
```bash
# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate    # On macOS/Linux

# Install dependencies
pip install -r backend/requirements.txt
```

### Start Backend Server
```bash
# From project root
cd backend
uvicorn main:app --reload

# Server runs on http://localhost:8000
# API docs available at http://localhost:8000/docs
```

### Database
- **File:** `vulnmonk.db` (SQLite)
- **Auto-created** when backend starts (via SQLAlchemy)
- **Reset:** Delete `vulnmonk.db` to start fresh with new schema
- **Schema includes:**
  - `projects` table (id, github_url, local_path, exclude_rules, created_at)
  - `scan_results` table (id, project_id, scan_date, result_json, findings_count)

### Backend API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects/` | List all projects |
| POST | `/projects/` | Create new project (with local_path) |
| POST | `/projects/github/` | Add project from GitHub URL |
| GET | `/projects/{project_id}/scans/` | Get scan history for project |
| GET | `/scans/{scan_id}/` | Get scan details and vulnerabilities |
| POST | `/scans/trigger/` | Trigger new scan |
| PUT | `/projects/{project_id}/exclude-rules/` | Update exclude rules |

## Frontend Setup & Running

### Install Dependencies
```bash
cd frontend
npm install
```

### Start Development Server
```bash
npm start

# Server runs on http://localhost:3000
```

### Build for Production
```bash
npm run build
```

### Frontend Components
- **App.js:** Main layout with sidebar, topbar, and content area
- **ProjectList.js:** Left panel - list of projects, add new GitHub project
- **ScanResults.js:** Right panel - scan controls, history, details, logs

### UI Features
- **Sidebar:** Dark theme (#181c23), cyan accent (#22d3ee), navigation menu
- **Topbar:** White background, dashboard title
- **Cards:** White background, subtle shadows, modern spacing
- **Buttons:** Blue primary (#2563eb), hover effects, disabled states
- **Badges:** Color-coded severity tags (Critical, High, Medium, Low)
- **Logs:** Inline status messages for scan actions (info=blue, success=green, error=red)
- **Tables:** Clean borders, alternating row colors, responsive

## Development Workflow

### Adding a New Feature
1. **Backend:** Add endpoint in `api.py`, add CRUD in `crud.py`, update `models.py` and `schemas.py`
2. **Frontend:** Add API call in `api.js`, update component in `components/`
3. **Test:** Check both backend (/docs) and frontend (localhost:3000)
4. **Database:** If schema changes, delete `vulnmonk.db` to regenerate

### Common Tasks
- **Reset Database:** `rm vulnmonk.db` then restart backend
- **Kill Servers:** Use `kill_terminal` or Ctrl+C in relevant terminal
- **Debug Backend:** Check Uvicorn logs in terminal, check `vulnmonk.db` with SQLite client
- **Debug Frontend:** Check browser console (F12), check React DevTools
- **Fix Import Errors:** Ensure all imports are at top of file with correct relative paths

## Important Notes
- **CORS:** Backend has CORS enabled for localhost:3000
- **SAST Tool:** Security scanning tool must be installed and available in PATH for scan triggering to work
- **GitHub Cloning:** Projects are cloned to `projects/` directory; ensure git is installed
- **Database Path:** `vulnmonk.db` is in project root, referenced in `backend/database.py`

## Deployed on Production
- Frontend: Build React app and serve static files via web server
- Backend: Run Uvicorn with production ASGI server (gunicorn, uvicorn, etc.)
- Database: Use persistent SQLite or migrate to PostgreSQL/MySQL
- Security: Enable proper CORS, add authentication, use HTTPS

## Future Enhancements
- Add user authentication
- Export scan results as PDF/CSV
- Integrate with CI/CD pipelines
- Add webhook support for automated scans
- Enhanced charts/dashboards for finding trends
- Multi-user collaboration features
- Support for multiple SAST tools
