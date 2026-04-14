from fastapi import FastAPI
import os
import secrets
import string
import logging
from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing other modules
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Now import modules that depend on environment variables
from . import api, database

logger = logging.getLogger("vulnmonk")

app = FastAPI()

# CORS is handled by nginx in production (proxy_hide_header strips backend headers,
# nginx injects Access-Control-Allow-Origin: * for all /api/ responses).
# No CORSMiddleware needed here.

def _ensure_admin_exists():
    """Create a default admin user if no admin account exists yet."""
    from .database import SessionLocal
    from . import crud, schemas
    from .auth import get_password_hash

    db = SessionLocal()
    try:
        users = crud.get_users(db)
        has_admin = any(u.role == "admin" for u in users)
        if not has_admin:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "".join(secrets.choice(alphabet) for _ in range(20))
            hashed = get_password_hash(password)
            user_in = schemas.UserCreate(username="admin", password=password, role="admin")
            crud.create_user(db=db, user=user_in, hashed_password=hashed)
            logger.warning(
                "=" * 60
            )
            logger.warning("No admin user found — created default admin account.")
            logger.warning("  Username : admin")
            logger.warning("  Password : %s", password)
            logger.warning(
                "=" * 60
            )
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    database.init_db()
    _ensure_admin_exists()
    from .scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    from .scheduler import stop_scheduler
    stop_scheduler()


app.include_router(api.router)

@app.get("/")
def read_root():
    return {"message": "VulnMonk SAST Dashboard Backend"}
