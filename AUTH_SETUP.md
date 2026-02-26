# VulnMonk Authentication Setup Guide

## Overview
Complete authentication and authorization system with JWT tokens for the VulnMonk SAST Dashboard.

## Features Implemented
✅ JWT-based authentication (30-day token validity)  
✅ Two user roles: **Admin** and **User**  
✅ Role-based access control (RBAC)  
✅ Login page with credentials  
✅ Account settings page (password change)  
✅ User management page (Admin only)  
✅ Protected API endpoints  
✅ Database migration script (preserves existing data)  
✅ User management CLI script  

---

## Setup Instructions

### 1. Install Backend Dependencies

```bash
cd backend
pip3 install -r requirements.txt
```

**New dependencies added:**
- `python-jose[cryptography]` - JWT token handling
- `passlib[bcrypt]` - Password hashing
- `python-multipart` - Form data parsing

### 2. Run Database Migration

**IMPORTANT**: This migration will preserve all your existing data (projects, scans, false positives).

```bash
# From project root
python migrate_db.py
```

**What the migration does:**
- Creates `users` table
- Adds indexes for username lookups
- Creates default admin user
- **Username:** `admin`
- **Password:** `admin`

**⚠️ SECURITY: Change the admin password immediately after first login!**

### 3. Start the Backend Server

```bash
cd backend
uvicorn main:app --reload
```

Server runs at: http://localhost:8000  
API docs: http://localhost:8000/docs

### 4. Start the Frontend

```bash
cd frontend
npm start
```

Frontend runs at: http://localhost:3000

---

## User Roles & Permissions

### Admin Role 👑
**Full access to all features:**
- ✅ View all projects and scans
- ✅ Add new projects
- ✅ Trigger scans
- ✅ Mark findings as false positives
- ✅ Manage exclude rules
- ✅ Manage users (create, update roles, activate/deactivate)
- ✅ View user list
- ✅ Change own password

### User Role 👤
**View-only access:**
- ✅ View all projects and scans
- ✅ View scan results and findings
- ✅ Search and filter
- ✅ Change own password
- ❌ Cannot add projects
- ❌ Cannot trigger scans
- ❌ Cannot mark false positives
- ❌ Cannot manage exclude rules
- ❌ Cannot access user management

---

## Managing Users

### Using the CLI Script

**Add a new user:**
```bash
python add_user.py <username> <password> <role>
```

**Examples:**
```bash
# Create a regular user
python add_user.py john secret123 user

# Create an admin user
python add_user.py alice admin456 admin
```

**List all users:**
```bash
python add_user.py --list
```

**Validation rules:**
- Username: Minimum 3 characters
- Password: Minimum 6 characters
- Role: Must be either `admin` or `user`

### Using the Web Interface (Admin Only)

1. Login as admin
2. Navigate to **Users** in the sidebar
3. Click **➕ Create User**
4. Fill in the form:
   - Username
   - Password
   - Role (Admin/User)
5. Click **Create User**

**Admin actions:**
- **Promote/Demote**: Change user role between admin and user
- **Activate/Deactivate**: Enable or disable user accounts
- Cannot change your own role (security measure)

---

## Using the Application

### Login
1. Navigate to http://localhost:3000
2. Enter credentials:
   - Default admin: `admin` / `admin`
3. Click **Sign In**

### Change Password
1. Login to the application
2. Click **Account** in the sidebar
3. Fill in the password change form:
   - Current password
   - New password
   - Confirm new password
4. Click **Update Password**

### Logout
- Click the **🚪 Logout** button in the sidebar footer

---

## API Endpoints

### Authentication Endpoints
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/auth/login` | Login and get JWT token | Public |
| GET | `/auth/me` | Get current user info | Authenticated |
| POST | `/auth/change-password` | Change password | Authenticated |

### User Management Endpoints (Admin Only)
| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/users/` | List all users | Admin |
| POST | `/users/` | Create new user | Admin |
| PUT | `/users/{user_id}/role` | Update user role/status | Admin |

### Protected Project Endpoints
| Method | Endpoint | Access |
|--------|----------|--------|
| GET | `/projects/` | Authenticated |
| POST | `/projects/github/` | **Admin only** |
| POST | `/projects/{id}/scan/` | **Admin only** |
| PUT | `/projects/{id}/exclude_rules/` | **Admin only** |

### Protected Scan Endpoints
| Method | Endpoint | Access |
|--------|----------|--------|
| GET | `/projects/{id}/scans/` | Authenticated |
| GET | `/scans/{id}/` | Authenticated |
| POST | `/projects/{id}/false-positives/` | **Admin only** |
| GET | `/projects/{id}/false-positives/` | Authenticated |
| DELETE | `/projects/{id}/false-positives/{key}` | **Admin only** |

---

## Security Features

### JWT Tokens
- **Validity**: 30 days
- **Storage**: Browser localStorage
- **Algorithm**: HS256
- **Automatic**: Added to all API requests via Authorization header

### Password Security
- **Hashing**: bcrypt algorithm
- **Salt**: Auto-generated per password
- **No plaintext**: Passwords never stored in plain text

### API Protection
- All endpoints require authentication (except login)
- Role-based access control on write operations
- Token validation on every request
- Automatic 401 on invalid/expired tokens

---

## Troubleshooting

### "Authentication failed" error
- Ensure backend server is running
- Check username/password are correct
- Try logging in with default admin credentials

### "Admin access required" messages
- Your user has "user" role (view-only)
- Ask an admin to promote you to admin role
- Or login with an admin account

### Migration errors
- Ensure backend dependencies are installed: `pip3 install -r backend/requirements.txt`
- Check database file exists: `vulnmonk.db` in project root
- If table already exists, migration skips automatically

### Login page not showing
- Clear browser cache and localStorage
- Check frontend is running on port 3000
- Check browser console for errors

---

## Production Deployment

**⚠️ IMPORTANT for Production:**

1. **Change SECRET_KEY** in `backend/auth.py`:
   ```python
   SECRET_KEY = "your-secure-random-key-here"  # Use a strong random string
   ```
   Generate a secure key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Change default admin password** immediately

3. **Use HTTPS** for all API communication

4. **Enable CORS** only for your production domain

5. **Use environment variables** for sensitive configuration

6. **Consider switching to PostgreSQL** for production database

---

## File Structure

```
vulnmonk/
├── backend/
│   ├── auth.py              # Authentication utilities (NEW)
│   ├── models.py            # User model added
│   ├── schemas.py           # User schemas added
│   ├── crud.py              # User CRUD operations added
│   ├── api.py               # Auth endpoints & protected routes
│   └── requirements.txt     # Updated dependencies
├── frontend/
│   ├── src/
│   │   ├── api.js           # Auth token management added
│   │   ├── App.js           # Auth flow added
│   │   ├── App.css          # Auth styles added
│   │   └── components/
│   │       ├── Login.js     # Login page (NEW)
│   │       ├── Account.js   # Account settings (NEW)
│   │       ├── Users.js     # User management (NEW)
│   │       ├── ProjectsView.js    # Updated with role checks
│   │       ├── ScanResults.js     # Updated with role checks
│   │       └── Configurations.js  # Updated with role checks
├── migrate_db.py            # Database migration script (NEW)
├── add_user.py              # User management CLI (NEW)
└── AUTH_SETUP.md            # This file (NEW)
```

---

## Default Credentials

**⚠️ FOR DEVELOPMENT ONLY**

- **Username:** admin
- **Password:** admin

**Change immediately in production!**

---

## Support

For issues or questions:
1. Check API docs at http://localhost:8000/docs
2. Review browser console for errors
3. Check backend terminal logs
4. Verify database migration completed successfully

---

**Last Updated:** February 21, 2026
