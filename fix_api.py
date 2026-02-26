#!/usr/bin/env python3
"""
Fix api.py to remove background scanning and status tracking
"""

# Read the file
with open('backend/api.py', 'r') as f:
    lines = f.readlines()

# Find and replace the problematic sections
new_lines = []
skip_until = None
i = 0

while i < len(lines):
    line = lines[i]
    
    # Skip the run_scan_in_background function (approx lines 60-113)
    if 'def run_scan_in_background(' in line:
        # Skip until we find the next @router or def at the same indentation level
        skip_until = 'next_function'
        i += 1
        continue
    
    if skip_until == 'next_function':
        if line.startswith('# Trigger') or line.startswith('@router'):
            skip_until = None
            # Don't skip this line, process it
        else:
            i += 1
            continue
    
   # Skip the get_scan_status endpoint (after trigger_scan)
    if 'def get_scan_status(' in line:
        skip_until = 'after_get_scan_status'
        i += 1
        continue
    
    if skip_until == 'after_get_scan_status':
        if line.startswith('def run_opengrep_scan('):
            skip_until = None
            # Don't skip this line, process it
        else:
            i += 1
            continue
    
    # Fix the trigger_scan function - replace with synchronous version
    if line.strip() == '# Trigger OpenGrep scan for a project (runs in background)':
        # Replace the whole trigger_scan with synchronous version
        new_lines.append('# Trigger OpenGrep scan for a project\n')
        i += 1
        # Skip @router line
        new_lines.append(lines[i])  # @router.post
        i += 1
        new_lines.append(lines[i])  # def trigger_scan
        i += 1
        # Skip until we find the return statement, replace the whole body
        while i < len(lines) and not (lines[i].startswith('# Get scan status') or lines[i].startswith('def run_opengrep_scan')):
            i += 1
        
        # Insert the synchronous scanning code
        new_lines.append('''    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Generate temporary path for cloning
    repo_name = project.github_url.rstrip("/").split("/")[-1].replace(".git", "")
    unique_id = str(uuid.uuid4())[:8]
    temp_path = os.path.join(PROJECTS_ROOT, f"temp-{repo_name}-{unique_id}")
    
    try:
        # Clone the repository
        print(f"[DEBUG] Cloning repository: {project.github_url} to {temp_path}")
        subprocess.run(["git", "clone", "--depth", "1", project.github_url, temp_path], 
                      check=True, capture_output=True, text=True)
        
        # Run the scan
        print(f"[DEBUG] Running scan on {temp_path}")
        scan_result = run_opengrep_scan(temp_path, project.exclude_rules)
        
        # Add unique_key to all findings but DON'T filter yet (filtering happens on retrieval)
        if scan_result and isinstance(scan_result, dict):
            results = scan_result.get("results", [])
            if isinstance(results, list):
                for finding in results:
                    unique_key = generate_unique_key(finding)
                    finding["unique_key"] = unique_key
                    finding["status"] = "open"  # All new findings start as open
        
        # Store scan result with all findings (unfiltered)
        scan = schemas.ScanResultCreate(result_json=scan_result)
        db_scan = crud.create_scan_result(db=db, scan=scan, project_id=project_id)
        
        # Return processed version with current false positives filtered
        # (process_scan_findings makes a deep copy internally)
        processed_result = process_scan_findings(scan_result, project_id, db)
        
        return {
            "id": db_scan.id,
            "project_id": db_scan.project_id,
            "scan_date": db_scan.scan_date.isoformat() if db_scan.scan_date else None,
            "result_json": processed_result
        }
    
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Git clone failed: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
    finally:
        # Clean up: Delete the cloned repository
        if os.path.exists(temp_path):
            print(f"[DEBUG] Cleaning up temporary repository: {temp_path}")
            import shutil
            shutil.rmtree(temp_path, ignore_errors=True)

''')
        continue
    
    # Fix the summaries.append to remove status and error_message
    if '"status": scan.status,' in line:
        i += 1  # Skip this line
        continue
    if '"error_message": scan.error_message' in line:
        i += 1  # Skip this line
        continue
    
    new_lines.append(line)
    i += 1

# Write the fixed file
with open('backend/api.py', 'w') as f:
    f.writelines(new_lines)

print("Fixed api.py - removed background scanning and status tracking")
