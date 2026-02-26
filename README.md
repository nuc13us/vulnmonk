# VulnMonk SAST Dashboard

A full-stack security dashboard for managing and visualizing SAST (Static Application Security Testing) scan results across multiple GitHub repositories.

## Features

### Security & Access Control
- 🔐 **JWT Authentication** - Secure token-based authentication with 30-day validity
- 👥 **Role-Based Access Control** - Admin and User roles with different permissions
- 🔒 **Protected Endpoints** - All API endpoints require authentication
- 👤 **Account Management** - Users can change passwords and view profile information
- 🛡️ **Admin Panel** - User management interface for admins (create, promote/demote, activate/deactivate)

### Project Management
- 📁 **GitHub Integration** - Add projects directly from GitHub URLs
- 🔄 **Automated Cloning** - Projects are automatically cloned for scanning
- ⚙️ **Exclude Rules** - Configure security rules to exclude from scans per project
- 📊 **Project Dashboard** - View all projects with scan statistics

### Scan Management
- ⚡ **On-Demand Scanning** - Trigger security scans from the UI (Admin only)
- 📈 **Scan History** - View complete scan history for each project
- 🔍 **Vulnerability Details** - Detailed view of findings with severity badges
- 🎯 **False Positive Management** - Mark vulnerabilities as false positives
- 📝 **Scan Logs** - Real-time scan status and activity logs

### User Interface
- 🎨 **Modern Enterprise UI** - Clean, professional dashboard design
- 🌙 **Dark Sidebar** - Elegant navigation with cyan accents
- 📱 **Responsive Layout** - Card-based design that works on all screen sizes
- 🔔 **Real-time Feedback** - Status messages and notifications
- 🎯 **Severity Badges** - Color-coded vulnerability severity (Critical, High, Medium, Low)

## Tech Stack

**Backend:**
- Python 3.12
- FastAPI (REST API)
- SQLAlchemy (ORM)
- SQLite (Database)
- JWT Authentication (python-jose)
- Password Hashing (bcrypt)

**Frontend:**
- React 19
- JavaScript (ES6+)
- CSS3
- Browser LocalStorage for token management

**Security Tools:**
- SAST scanning tool (e.g., Semgrep, OpenGrep)

## Prerequisites

- Python 3.12+
- Node.js 16+ and npm
- Git
- SAST scanning tool (for scanning)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/vulnmonk.git
cd vulnmonk
```

### 2. Backend Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Create environment file
cp backend/.env.example backend/.env
# Edit backend/.env and set your JWT_SECRET_KEY

# Run database migration (creates users table and default admin)
python3 migrate_db.py
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create environment file (optional)
cp .env.example .env
# Edit .env if you want to change the API URL
```

## Configuration

### Backend Environment Variables

Create `backend/.env` file:

```bash
# JWT Configuration
JWT_SECRET_KEY=your-very-secure-random-secret-key
JWT_EXPIRE_DAYS=30

# Database (optional, defaults to opengrep.db in project root)
DATABASE_PATH=

# CORS Origins (comma-separated, defaults to http://localhost:3000)
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

**Generate a secure JWT secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Frontend Environment Variables

Create `frontend/.env` file (optional):

```bash
# Backend API URL (defaults to http://127.0.0.1:8000)
REACT_APP_API_BASE_URL=http://127.0.0.1:8000
```

## Running the Application

### Start Backend Server

```bash
# From project root, with venv activated
uvicorn backend.main:app --reload

# Server runs on http://localhost:8000
# API docs available at http://localhost:8000/docs
```

### Start Frontend Server

```bash
# In a new terminal
cd frontend
npm start

# Server runs on http://localhost:3000
```

## Default Credentials

After running the migration script, default admin account is created:

- **Username:** `admin`
- **Password:** `admin`

**⚠️ IMPORTANT:** Change the default password immediately after first login!

## User Management

### Adding Users via CLI

```bash
# Activate virtual environment first
source venv/bin/activate

# Add a new user
python3 add_user.py

# List all users
python3 add_user.py --list
```

### Adding Users via UI

1. Login as admin
2. Navigate to "Users" in the sidebar
3. Click "Create New User"
4. Enter username, password, and select role
5. Click "Create User"

## Database Management

### View Database Contents

```bash
python3 view_db.py              # View everything
python3 view_db.py projects     # View only projects
python3 view_db.py scans        # View only scans
python3 view_db.py fps          # View only false positives
```

### Check User Roles

```bash
python3 check_user.py
```

### Reset Database

```bash
# Delete the database file
rm vulnmonk.db

# Restart backend to recreate schema
uvicorn backend.main:app --reload

# Run migration to add users table
python3 migrate_db.py
```

## API Documentation

Once the backend is running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Project Structure

```
vulnmonk/
├── backend/                    # Python FastAPI backend
│   ├── api.py                 # API routes and endpoints
│   ├── auth.py                # Authentication utilities
│   ├── crud.py                # Database CRUD operations
│   ├── database.py            # Database connection
│   ├── models.py              # SQLAlchemy ORM models
│   ├── schemas.py             # Pydantic validation schemas
│   ├── main.py                # FastAPI application entry
│   ├── requirements.txt       # Python dependencies
│   └── .env.example           # Environment variables template
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── Login.js      # Login page
│   │   │   ├── Account.js    # Account settings
│   │   │   ├── Users.js      # User management (admin)
│   │   │   ├── Dashboard.js  # Main dashboard
│   │   │   ├── ProjectsView.js   # Projects list
│   │   │   ├── ScanResults.js    # Scan results viewer
│   │   │   └── Configurations.js # Exclude rules editor
│   │   ├── App.js            # Main application
│   │   ├── App.css           # Global styles
│   │   ├── api.js            # API client
│   │   └── index.js          # React entry point
│   ├── public/                # Static assets
│   ├── package.json           # Node dependencies
│   └── .env.example           # Environment variables template
├── projects/                   # Cloned GitHub repos (auto-created)
├── migrate_db.py              # Database migration script
├── add_user.py                # CLI user management
├── check_user.py              # Check user roles utility
├── view_db.py                 # Database viewer utility
├── vulnmonk.db                # SQLite database (auto-created)
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## Permissions

### Admin Users Can:
- ✅ Trigger scans
- ✅ Add/edit projects
- ✅ Manage exclude rules
- ✅ Mark false positives
- ✅ View all users
- ✅ Create new users
- ✅ Change user roles
- ✅ Activate/deactivate users
- ✅ View all content

### Regular Users Can:
- ✅ View projects
- ✅ View scan results
- ✅ View configurations
- ✅ Change their own password
- ❌ Cannot trigger scans
- ❌ Cannot edit configurations
- ❌ Cannot manage users

## Security Best Practices

1. **Change Default Password:** Immediately change the default admin password after first login
2. **Secure JWT Secret:** Use a strong, randomly generated JWT secret key
3. **HTTPS in Production:** Always use HTTPS in production environments
4. **CORS Configuration:** Restrict CORS origins to your frontend domain only
5. **Regular Updates:** Keep dependencies updated for security patches
6. **Backup Database:** Regularly backup your `vulnmonk.db` file
7. **Environment Variables:** Never commit `.env` files to version control

## Troubleshooting

### Backend won't start

- Ensure virtual environment is activated
- Check all dependencies are installed: `pip install -r backend/requirements.txt`
- Verify Python version is 3.12+

### Frontend won't compile

- Delete `node_modules` and run `npm install` again
- Check Node version is 16+
- Clear npm cache: `npm cache clean --force`

### Authentication errors

- Ensure JWT_SECRET_KEY is set in backend/.env
- Clear browser localStorage and login again
- Check backend logs for detailed error messages

### Database issues

- Run `python3 migrate_db.py` to ensure users table exists
- Check database permissions
- Verify database path in backend/.env

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review API documentation at `/docs`

## Roadmap

- [ ] Export scan results as PDF/CSV
- [ ] Integration with CI/CD pipelines
- [ ] Webhook support for automated scans
- [ ] Enhanced charts and trend analysis
- [ ] Multi-user collaboration features
- [ ] Support for multiple SAST tools
- [ ] Email notifications
- [ ] Advanced filtering and search
- [ ] Custom severity configurations

