#!/usr/bin/env python3
"""
Check user roles in the database.
"""

import sqlite3
from pathlib import Path

DB_PATH = "vulnmonk.db"

def check_users():
    """Display all users and their roles."""
    if not Path(DB_PATH).exists():
        print(f"❌ Error: Database file '{DB_PATH}' not found!")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        
        if not cursor.fetchone():
            print("❌ Users table does not exist. Please run migrate_db.py first!")
            conn.close()
            return
        
        # Get all users
        cursor.execute("""
            SELECT id, username, role, is_active, created_at
            FROM users
            ORDER BY id
        """)
        
        users = cursor.fetchall()
        
        if not users:
            print("ℹ️  No users found in database.")
        else:
            print(f"\n📊 Found {len(users)} user(s):\n")
            print(f"{'ID':<5} {'Username':<20} {'Role':<10} {'Active':<8} {'Created At':<20}")
            print("=" * 70)
            for user in users:
                user_id, username, role, is_active, created_at = user
                active_str = "Yes" if is_active else "No"
                print(f"{user_id:<5} {username:<20} {role:<10} {active_str:<8} {created_at:<20}")
            print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    check_users()
