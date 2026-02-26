#!/usr/bin/env python3
"""
Database viewer utility for VulnMonk SAST Dashboard.
View projects, scans, and false positives in the database.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import SessionLocal, engine
from backend.models import Project, ScanResult, FalsePositive
import json
from datetime import datetime

def view_projects():
    """View all projects in the database"""
    db = SessionLocal()
    projects = db.query(Project).all()
    
    print("\n" + "="*80)
    print("PROJECTS")
    print("="*80)
    
    if not projects:
        print("No projects found.")
        return
    
    for p in projects:
        print(f"\nID: {p.id}")
        print(f"GitHub URL: {p.github_url}")
        print(f"Local Path: {p.local_path}")
        print(f"Exclude Rules: {p.exclude_rules}")
        print(f"Created At: {p.created_at}")
        print("-" * 80)
    
    db.close()

def view_scans():
    """View all scan results in the database"""
    db = SessionLocal()
    scans = db.query(ScanResult).all()
    
    print("\n" + "="*80)
    print("SCAN RESULTS")
    print("="*80)
    
    if not scans:
        print("No scans found.")
        return
    
    for s in scans:
        print(f"\nScan ID: {s.id}")
        print(f"Project ID: {s.project_id}")
        print(f"Scan Date: {s.scan_date}")
        
        if s.result_json:
            results = s.result_json.get('results', [])
            fps = s.result_json.get('false_positives', [])
            print(f"Total Findings in DB: {len(results)}")
            print(f"False Positives Array: {len(fps)}")
            
            if results:
                print("\n  Sample Findings (first 3):")
                for i, finding in enumerate(results[:3]):
                    unique_key = finding.get('unique_key', 'MISSING')
                    status = finding.get('status', 'MISSING')
                    path = finding.get('path', 'N/A')
                    line = finding.get('start', {}).get('line', 'N/A')
                    rule = finding.get('check_id', 'N/A')
                    print(f"    [{i+1}] Unique Key: {unique_key}")
                    print(f"        Status: {status}")
                    print(f"        Path: {path}, Line: {line}, Rule: {rule}")
                
                if len(results) > 3:
                    print(f"    ... and {len(results)-3} more")
            
            if fps:
                print("\n  False Positives in Scan (first 3):")
                for i, finding in enumerate(fps[:3]):
                    unique_key = finding.get('unique_key', 'MISSING')
                    path = finding.get('path', 'N/A')
                    line = finding.get('start', {}).get('line', 'N/A')
                    rule = finding.get('check_id', 'N/A')
                    print(f"    [{i+1}] {unique_key}")
                    print(f"        Path: {path}, Line: {line}, Rule: {rule}")
                
                if len(fps) > 3:
                    print(f"    ... and {len(fps)-3} more")
        
        print("-" * 80)
    
    db.close()

def view_false_positives():
    """View all false positive markers in the database"""
    db = SessionLocal()
    fps = db.query(FalsePositive).all()
    
    print("\n" + "="*80)
    print("FALSE POSITIVE MARKERS")
    print("="*80)
    
    if not fps:
        print("No false positives marked.")
        return
    
    # Group by project
    from collections import defaultdict
    fps_by_project = defaultdict(list)
    for fp in fps:
        fps_by_project[fp.project_id].append(fp)
    
    for project_id, project_fps in fps_by_project.items():
        print(f"\nProject ID: {project_id} ({len(project_fps)} false positives)")
        print("-" * 80)
        for fp in project_fps:
            print(f"  FP ID: {fp.id}")
            print(f"  Unique Key: {fp.unique_key}")
            print(f"  Marked At: {fp.marked_at}")
            print()
    
    db.close()

def view_all():
    """View everything in the database"""
    view_projects()
    view_scans()
    view_false_positives()

def main():
    """Main function"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == 'projects':
            view_projects()
        elif command == 'scans':
            view_scans()
        elif command == 'fps' or command == 'false-positives':
            view_false_positives()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python view_db.py [projects|scans|fps]")
    else:
        view_all()

if __name__ == "__main__":
    main()
