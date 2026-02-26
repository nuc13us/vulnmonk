#!/usr/bin/env python3
"""
Check exclude_rules in projects table.
"""

import sqlite3
from pathlib import Path

DB_PATH = "vulnmonk.db"

def check_exclude_rules():
    """Check if exclude_rules column exists and has data."""
    if not Path(DB_PATH).exists():
        print(f"❌ Error: Database file '{DB_PATH}' not found!")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("PRAGMA table_info(projects)")
        columns = cursor.fetchall()
        
        print("📋 Projects table columns:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Check if exclude_rules column exists
        has_exclude_rules = any(col[1] == 'exclude_rules' for col in columns)
        
        if not has_exclude_rules:
            print("\n❌ exclude_rules column NOT FOUND in projects table!")
            print("   The column may have been lost during migration.")
        else:
            print("\n✅ exclude_rules column exists")
            
            # Get all projects with their exclude_rules
            cursor.execute("SELECT id, github_url, exclude_rules FROM projects")
            projects = cursor.fetchall()
            
            print(f"\n📊 Projects with exclude rules:")
            print(f"{'ID':<5} {'GitHub URL':<50} {'Exclude Rules':<30}")
            print("=" * 90)
            
            has_data = False
            for proj in projects:
                proj_id, url, rules = proj
                url_short = url[:47] + "..." if len(url) > 50 else url
                rules_display = rules if rules else "(none)"
                if rules:
                    has_data = True
                print(f"{proj_id:<5} {url_short:<50} {rules_display:<30}")
            
            if not has_data:
                print("\n⚠️  No projects have exclude_rules set!")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    check_exclude_rules()
