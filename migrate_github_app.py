"""
Migration: add GitHub App columns to github_integrations table.

Run once after pulling this update:
    python migrate_github_app.py
"""

import os
import sqlite3

DB_PATH = os.getenv("DATABASE_PATH", None)
if not DB_PATH:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(PROJECT_ROOT, "vulnmonk.db")

print(f"Migrating database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check existing columns
cur.execute("PRAGMA table_info(github_integrations)")
existing = {row[1] for row in cur.fetchall()}

changes = []

if "installation_id" not in existing:
    cur.execute("ALTER TABLE github_integrations ADD COLUMN installation_id INTEGER")
    changes.append("installation_id INTEGER")

if "account_type" not in existing:
    cur.execute("ALTER TABLE github_integrations ADD COLUMN account_type TEXT DEFAULT 'User'")
    changes.append("account_type TEXT DEFAULT 'User'")

# access_token was NOT NULL before — relax it for App-based integrations
# SQLite doesn't support ALTER COLUMN, so we just leave the constraint as-is;
# new rows that come from App installs will store "" (empty string) which satisfies NOT NULL.

conn.commit()
conn.close()

if changes:
    print(f"Added columns: {', '.join(changes)}")
else:
    print("Nothing to do — columns already exist.")

print("Done.")
