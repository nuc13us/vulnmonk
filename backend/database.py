from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
import os

# Get database path from environment or use default
DB_PATH = os.getenv("DATABASE_PATH", None)
if not DB_PATH:
    # Default: vulnmonk.db in project root
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(PROJECT_ROOT, "vulnmonk.db")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def _run_migrations():
    """Apply any schema migrations that create_all cannot handle (new columns on existing tables)."""
    with engine.connect() as conn:
        # projects.scheduled_scan_enabled — added for daily scheduled scans feature
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE projects ADD COLUMN scheduled_scan_enabled INTEGER"
                )
            )
            conn.commit()
        except Exception:
            # Column already exists — safe to ignore
            pass

        # projects.slack_notify_enabled — added for Slack notifications feature
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE projects ADD COLUMN slack_notify_enabled INTEGER"
                )
            )
            conn.commit()
        except Exception:
            pass

def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
