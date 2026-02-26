#!/usr/bin/env python3
"""
Migration script to add include rules and global configuration features.
Adds new columns to projects table and creates global_configurations table.
"""

import sqlite3
import os

# Get database path
DB_PATH = os.path.join(os.path.dirname(__file__), "vulnmonk.db")

def migrate_database():
    """Add new columns and tables for rules features"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("The database will be created automatically when you start the backend.")
        return
    
    print(f"🔄 Migrating database at {DB_PATH}...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(projects)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add new columns to projects table if they don't exist
        if 'include_rules_yaml' not in columns:
            print("  ➕ Adding include_rules_yaml column to projects table...")
            cursor.execute("ALTER TABLE projects ADD COLUMN include_rules_yaml TEXT DEFAULT ''")
        else:
            print("  ✓ include_rules_yaml column already exists")
        
        if 'apply_global_exclude' not in columns:
            print("  ➕ Adding apply_global_exclude column to projects table...")
            cursor.execute("ALTER TABLE projects ADD COLUMN apply_global_exclude INTEGER DEFAULT 0")
        else:
            print("  ✓ apply_global_exclude column already exists")
        
        if 'apply_global_include' not in columns:
            print("  ➕ Adding apply_global_include column to projects table...")
            cursor.execute("ALTER TABLE projects ADD COLUMN apply_global_include INTEGER DEFAULT 0")
        else:
            print("  ✓ apply_global_include column already exists")
        
        # Create global_configurations table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ✓ global_configurations table created/verified")
        
        # Create index on key column
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_global_configurations_key 
            ON global_configurations (key)
        """)
        
        conn.commit()
        print("✅ Migration completed successfully!")
        
        # Show summary
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]
        print(f"\n📊 Summary:")
        print(f"  - Projects migrated: {project_count}")
        print(f"  - New columns added: include_rules_yaml, apply_global_exclude, apply_global_include")
        print(f"  - New table created: global_configurations")
        print(f"\n✨ Your database is now ready to use include rules and global configurations!")
        
    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("VulnMonk Database Migration - Include Rules & Global Configs")
    print("=" * 60)
    migrate_database()
