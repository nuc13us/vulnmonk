#!/usr/bin/env python3
"""
Fix admin user password after bcrypt error during migration.
"""

import sqlite3
from pathlib import Path

DB_PATH = "vulnmonk.db"

def fix_admin_password():
    """Reset admin password with proper bcrypt hashing."""
    if not Path(DB_PATH).exists():
        print(f"❌ Error: Database file '{DB_PATH}' not found!")
        return
    
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Hash the password "admin"
        admin_password_hash = pwd_context.hash("admin")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Update admin user's password
        cursor.execute("""
            UPDATE users 
            SET hashed_password = ?, role = 'admin', is_active = 1
            WHERE username = 'admin'
        """, (admin_password_hash,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print("✅ Admin password has been reset successfully!")
            print()
            print("🔑 Admin credentials:")
            print("   Username: admin")
            print("   Password: admin")
            print()
            print("⚠️  Please change this password after logging in!")
        else:
            print("❌ Admin user not found in database.")
        
        conn.close()
        
    except ImportError:
        print("❌ Error: passlib not installed. Install dependencies first:")
        print("   pip3 install passlib bcrypt==4.0.1")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_admin_password()
