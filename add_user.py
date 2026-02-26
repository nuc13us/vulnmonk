#!/usr/bin/env python3
"""
Script to add users to the VulnMonk database.
Usage:
    python add_user.py <username> <password> <role>
    
Example:
    python add_user.py john secret123 user
    python add_user.py alice secret456 admin
"""

import sqlite3
import sys
from pathlib import Path
from passlib.context import CryptContext

DB_PATH = "vulnmonk.db"

def add_user(username, password, role="user"):
    """Add a new user to the database."""
    
    # Validate inputs
    if not username or len(username) < 3:
        print("❌ Error: Username must be at least 3 characters long")
        return False
    
    if not password or len(password) < 6:
        print("❌ Error: Password must be at least 6 characters long")
        return False
    
    if role not in ["admin", "user"]:
        print("❌ Error: Role must be 'admin' or 'user'")
        return False
    
    if not Path(DB_PATH).exists():
        print(f"❌ Error: Database file '{DB_PATH}' not found!")
        print("   Run the backend server first to create the database, or run migrate_db.py")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        
        if not cursor.fetchone():
            print("❌ Error: Users table doesn't exist. Run migrate_db.py first:")
            print("   python migrate_db.py")
            conn.close()
            return False
        
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            print(f"❌ Error: User '{username}' already exists!")
            conn.close()
            return False
        
        # Hash the password
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash(password)
        
        # Get current timestamp
        from datetime import datetime
        created_at = datetime.utcnow().isoformat()
        
        # Insert the new user
        cursor.execute("""
            INSERT INTO users (username, hashed_password, role, is_active, created_at)
            VALUES (?, ?, ?, 1, ?)
        """, (username, hashed_password, role, created_at))
        
        conn.commit()
        user_id = cursor.lastrowid
        
        print("✅ User created successfully!")
        print(f"   ID: {user_id}")
        print(f"   Username: {username}")
        print(f"   Role: {role}")
        print()
        
        # Show all users
        cursor.execute("SELECT id, username, role, created_at FROM users ORDER BY id")
        users = cursor.fetchall()
        
        print(f"📊 Total users in database: {len(users)}")
        print("-" * 60)
        print(f"{'ID':<5} {'Username':<20} {'Role':<10} {'Created'}")
        print("-" * 60)
        for user in users:
            print(f"{user[0]:<5} {user[1]:<20} {user[2]:<10} {user[3]}")
        print()
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def list_users():
    """List all users in the database."""
    if not Path(DB_PATH).exists():
        print(f"❌ Error: Database file '{DB_PATH}' not found!")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, role, is_active, created_at 
            FROM users 
            ORDER BY id
        """)
        users = cursor.fetchall()
        
        if not users:
            print("ℹ️  No users found in database.")
            conn.close()
            return
        
        print(f"📊 Total users: {len(users)}")
        print("-" * 70)
        print(f"{'ID':<5} {'Username':<20} {'Role':<10} {'Active':<8} {'Created'}")
        print("-" * 70)
        for user in users:
            active_status = "Yes" if user[3] else "No"
            print(f"{user[0]:<5} {user[1]:<20} {user[2]:<10} {active_status:<8} {user[4]}")
        print()
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False

def print_usage():
    """Print usage instructions."""
    print("="*60)
    print("VulnMonk User Management")
    print("="*60)
    print()
    print("Add a new user:")
    print("  python add_user.py <username> <password> <role>")
    print()
    print("List all users:")
    print("  python add_user.py --list")
    print()
    print("Arguments:")
    print("  username  - Username (min 3 characters)")
    print("  password  - Password (min 6 characters)")
    print("  role      - User role: 'admin' or 'user'")
    print()
    print("Examples:")
    print("  python add_user.py john secret123 user")
    print("  python add_user.py alice secret456 admin")
    print("  python add_user.py --list")
    print()

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in ["--list", "-l"]:
        list_users()
    elif len(sys.argv) == 4:
        username = sys.argv[1]
        password = sys.argv[2]
        role = sys.argv[3]
        add_user(username, password, role)
    else:
        print_usage()
        sys.exit(1)
