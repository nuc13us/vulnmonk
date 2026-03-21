"""One-time migration: add findings_count column and backfill existing scan rows."""
import sqlite3
import json

conn = sqlite3.connect("vulnmonk.db")
cur = conn.cursor()

cols = [r[1] for r in cur.execute("PRAGMA table_info(scan_results)").fetchall()]
if "findings_count" not in cols:
    cur.execute("ALTER TABLE scan_results ADD COLUMN findings_count INTEGER DEFAULT NULL")
    print("Column added")
else:
    print("Column already exists")

fp_by_project = {}
for project_id, unique_key in cur.execute("SELECT project_id, unique_key FROM false_positives").fetchall():
    fp_by_project.setdefault(project_id, set()).add(unique_key)

updated = 0
for scan_id, project_id, result_json_raw in cur.execute(
    "SELECT id, project_id, result_json FROM scan_results WHERE findings_count IS NULL"
).fetchall():
    try:
        data = json.loads(result_json_raw) if isinstance(result_json_raw, str) else result_json_raw
        results = data.get("results", []) if isinstance(data, dict) else []
        fp_keys = fp_by_project.get(project_id, set())
        count = 0
        for f in results:
            start = f.get("start") or {}
            line = start.get("line", f.get("line", 0))
            key = f"{f.get('path','unknown')}@{line}@{f.get('check_id','unknown')}"
            if key not in fp_keys:
                count += 1
        cur.execute("UPDATE scan_results SET findings_count=? WHERE id=?", (count, scan_id))
        updated += 1
    except Exception as e:
        print(f"  scan {scan_id}: {e}")

conn.commit()
print(f"Backfilled {updated} scan rows")
conn.close()
