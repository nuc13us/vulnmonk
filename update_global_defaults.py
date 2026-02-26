#!/usr/bin/env python3
"""
Update existing projects to have global rules disabled by default.
Run this script to update all existing projects.
"""

import sqlite3
import os

# Get database path
DB_PATH = os.path.join(os.path.dirname(__file__), "vulnmonk.db")

def update_defaults():
    """Update existing projects to disable global rules by default"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return
    
    print(f"🔄 Updating project defaults in {DB_PATH}...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Update all existing projects to have global rules disabled by default
        cursor.execute("""
            UPDATE projects 
            SET apply_global_exclude = 0, 
                apply_global_include = 0
            WHERE apply_global_exclude IS NULL 
               OR apply_global_include IS NULL
               OR apply_global_exclude = 1
               OR apply_global_include = 1
        """)
        
        updated_count = cursor.rowcount
        conn.commit()
        
        print(f"✅ Updated {updated_count} projects to have global rules disabled by default")
        print(f"💡 Projects can now opt-in to global rules individually via checkboxes")
        
    except sqlite3.Error as e:
        print(f"❌ Update failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("VulnMonk - Update Global Rules Defaults")
    print("=" * 60)
    update_defaults()
