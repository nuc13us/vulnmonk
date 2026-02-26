#!/usr/bin/env python3
"""
Database migration script to add users table to existing database.
This script preserves all existing data and only adds the new users table.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = "vulnmonk.db"

def migrate_database():
    """Add users table to existing database."""
    if not Path(DB_PATH).exists():
        print(f"❌ Error: Database file '{DB_PATH}' not found!")
        print("   The database will be created when you start the backend.")
        sys.exit(1)
    
    print(f"🔄 Migrating database: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if users table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        
        if cursor.fetchone():
            print("ℹ️  Users table already exists. Migration not needed.")
            conn.close()
            return
        
        # Create users table
        print("📝 Creating users table...")
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR NOT NULL UNIQUE,
                hashed_password VARCHAR NOT NULL,
                role VARCHAR NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Create index on username for faster lookups
        cursor.execute("""
            CREATE INDEX ix_users_username ON users (username)
        """)
        
        # Create a default admin user (username: admin, password: admin)
        # You should change this password immediately after first login!
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        admin_password_hash = pwd_context.hash("admin")
        
        cursor.execute("""
            INSERT INTO users (username, hashed_password, role, is_active)
            VALUES (?, ?, 'admin', 1)
        """, ("admin", admin_password_hash))
        
        conn.commit()
        print("✅ Migration completed successfully!")
        print()
        print("🔑 Default admin user created:")
        print("   Username: admin")
        print("   Password: admin")
        print()
        print("⚠️  IMPORTANT: Change the admin password immediately after first login!")
        print()
        
        # Show table statistics
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM scan_results")
        scan_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM false_positives")
        fp_count = cursor.fetchone()[0]
        
        print("📊 Database statistics:")
        print(f"   Projects: {project_count}")
        print(f"   Scans: {scan_count}")
        print(f"   False Positives: {fp_count}")
        print(f"   Users: 1 (admin)")
        print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    except ImportError:
        print("❌ Error: passlib not installed. Install dependencies first:")
        print("   pip3 install -r backend/requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("="*60)
    print("VulnMonk Database Migration - Add Authentication")
    print("="*60)
    print()
    migrate_database()
