#!/usr/bin/env python3
"""
Database viewer utility for VulnMonk SAST Dashboard.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import SessionLocal
from backend.models import (
    Project, ScanResult, FalsePositive,
    User, GlobalConfiguration, GitHubIntegration,
    PRCheckConfig, TrufflehogScanResult, TrufflehogFalsePositive, PRScanResult,
)
from collections import defaultdict

SEP = "=" * 80
DIV = "-" * 80


def view_projects():
    db = SessionLocal()
    projects = db.query(Project).all()
    print(f"\n{SEP}\nPROJECTS ({len(projects)})\n{SEP}")
    for p in projects:
        print(f"\nID: {p.id}  |  {p.github_url}")
        print(f"  Integration ID:            {p.integration_id}")
        print(f"  Exclude Rules:             {p.exclude_rules or '(none)'}")
        print(f"  Include Rules YAML:        {'(set)' if p.include_rules_yaml else '(none)'}")
        print(f"  Apply Global Exclude:      {bool(p.apply_global_exclude)}")
        print(f"  Apply Global Include:      {bool(p.apply_global_include)}")
        print(f"  TruffleHog Exclude:        {p.trufflehog_exclude_detectors or '(none)'}")
        print(f"  Created At:                {p.created_at}")
    db.close()


def view_scans():
    db = SessionLocal()
    scans = db.query(ScanResult).order_by(ScanResult.id.desc()).all()
    print(f"\n{SEP}\nSAST SCAN RESULTS ({len(scans)})\n{SEP}")
    for s in scans:
        print(f"\nScan ID: {s.id}  |  Project ID: {s.project_id}  |  {s.scan_date}")
        print(f"  Findings Count: {s.findings_count}")
        if s.result_json:
            results = s.result_json.get('results', [])
            print(f"  Findings in JSON: {len(results)}")
            for i, f in enumerate(results[:3]):
                print(f"    [{i+1}] {f.get('path','?')}:{f.get('start',{}).get('line','?')}  rule={f.get('check_id','?')}")
            if len(results) > 3:
                print(f"    ... and {len(results)-3} more")
    db.close()


def view_false_positives():
    db = SessionLocal()
    fps = db.query(FalsePositive).all()
    print(f"\n{SEP}\nSAST FALSE POSITIVES ({len(fps)})\n{SEP}")
    by_project = defaultdict(list)
    for fp in fps:
        by_project[fp.project_id].append(fp)
    for project_id, items in by_project.items():
        print(f"\nProject ID: {project_id} ({len(items)} entries)")
        for fp in items:
            print(f"  [{fp.id}] {fp.unique_key}  |  {fp.marked_at}")
    db.close()


def view_trufflehog_scans():
    db = SessionLocal()
    scans = db.query(TrufflehogScanResult).order_by(TrufflehogScanResult.id.desc()).all()
    print(f"\n{SEP}\nTRUFFLEHOG SCAN RESULTS ({len(scans)})\n{SEP}")
    for s in scans:
        print(f"\nScan ID: {s.id}  |  Project ID: {s.project_id}  |  {s.scan_date}")
        print(f"  Findings Count: {s.findings_count}")
        if s.result_json:
            results = s.result_json if isinstance(s.result_json, list) else []
            print(f"  Findings in JSON: {len(results)}")
            for i, f in enumerate(results[:3]):
                print(f"    [{i+1}] {f.get('SourceMetadata',{}).get('Data',{}).get('Filesystem',{}).get('file','?')}  detector={f.get('DetectorName','?')}  verified={f.get('Verified','?')}")
            if len(results) > 3:
                print(f"    ... and {len(results)-3} more")
    db.close()


def view_trufflehog_fps():
    db = SessionLocal()
    fps = db.query(TrufflehogFalsePositive).all()
    print(f"\n{SEP}\nTRUFFLEHOG FALSE POSITIVES ({len(fps)})\n{SEP}")
    by_project = defaultdict(list)
    for fp in fps:
        by_project[fp.project_id].append(fp)
    for project_id, items in by_project.items():
        print(f"\nProject ID: {project_id} ({len(items)} entries)")
        for fp in items:
            print(f"  [{fp.id}] {fp.unique_key}  |  {fp.marked_at}")
    db.close()


def view_pr_scans():
    db = SessionLocal()
    prs = db.query(PRScanResult).order_by(PRScanResult.id.desc()).all()
    print(f"\n{SEP}\nPR SCAN RESULTS ({len(prs)})\n{SEP}")
    for p in prs:
        print(f"\nPR Scan ID: {p.id}  |  Project ID: {p.project_id}  |  {p.created_at}")
        print(f"  Repo:          {p.repo_full_name}  PR #{p.pr_number}: {p.pr_title}")
        print(f"  Branch:        {p.head_branch} → {p.base_branch}  sha={p.head_sha[:7] if p.head_sha else '?'}")
        print(f"  Status:        {p.status}  |  Findings: {p.findings_count}")
        if p.changed_files:
            print(f"  Changed Files: {len(p.changed_files)}")
    db.close()


def view_pr_configs():
    db = SessionLocal()
    configs = db.query(PRCheckConfig).all()
    print(f"\n{SEP}\nPR CHECK CONFIGS ({len(configs)})\n{SEP}")
    for c in configs:
        print(f"\nProject ID: {c.project_id}  |  Enabled: {bool(c.enabled)}")
        print(f"  Block on SAST severity: {c.block_on_severity}")
        print(f"  TruffleHog block on:    {c.th_block_on}")
        print(f"  Updated At:             {c.updated_at}")
    db.close()


def view_integrations():
    db = SessionLocal()
    integrations = db.query(GitHubIntegration).all()
    print(f"\n{SEP}\nGITHUB INTEGRATIONS ({len(integrations)})\n{SEP}")
    for i in integrations:
        print(f"\nID: {i.id}  |  {i.org_name}  ({i.account_type})")
        print(f"  Installation ID: {i.installation_id}")
        print(f"  Created At:      {i.created_at}")
        print(f"  Updated At:      {i.updated_at}")
    db.close()


def view_users():
    db = SessionLocal()
    users = db.query(User).all()
    print(f"\n{SEP}\nUSERS ({len(users)})\n{SEP}")
    for u in users:
        print(f"\nID: {u.id}  |  {u.username}  role={u.role}  active={bool(u.is_active)}")
        print(f"  Created At: {u.created_at}")
    db.close()


def view_global_config():
    db = SessionLocal()
    configs = db.query(GlobalConfiguration).all()
    print(f"\n{SEP}\nGLOBAL CONFIGURATIONS ({len(configs)})\n{SEP}")
    for c in configs:
        value_preview = (c.value[:120] + "...") if c.value and len(c.value) > 120 else c.value
        print(f"\nKey: {c.key}")
        print(f"  Value:      {value_preview or '(empty)'}")
        print(f"  Updated At: {c.updated_at}")
    db.close()


def view_all():
    view_projects()
    view_scans()
    view_false_positives()
    view_trufflehog_scans()
    view_trufflehog_fps()
    view_pr_scans()
    view_pr_configs()
    view_integrations()
    view_users()
    view_global_config()


COMMANDS = {
    'projects':       view_projects,
    'scans':          view_scans,
    'fps':            view_false_positives,
    'th-scans':       view_trufflehog_scans,
    'th-fps':         view_trufflehog_fps,
    'pr-scans':       view_pr_scans,
    'pr-configs':     view_pr_configs,
    'integrations':   view_integrations,
    'users':          view_users,
    'config':         view_global_config,
}


def main():
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        fn = COMMANDS.get(command)
        if fn:
            fn()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python view_db.py [" + "|".join(COMMANDS) + "]")
    else:
        view_all()


if __name__ == "__main__":
    main()
