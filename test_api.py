#!/usr/bin/env python3
"""
Test if the backend API returns exclude_rules.
"""

import requests

API_BASE = "http://127.0.0.1:8000"

# First, login to get token
print("1. Logging in...")
response = requests.post(
    f"{API_BASE}/auth/login",
    data={"username": "admin", "password": "admin"}
)

if response.status_code != 200:
    print(f"Login failed: {response.status_code}")
    print(response.text)
    exit(1)

token = response.json()["access_token"]
print(f"✅ Logged in, token: {token[:20]}...")

# Get projects
print("\n2. Getting projects...")
response = requests.get(
    f"{API_BASE}/projects/",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code != 200:
    print(f"Failed to get projects: {response.status_code}")
    print(response.text)
    exit(1)

projects = response.json()
print(f"✅ Got {len(projects)} projects")

# Check exclude_rules in each project
print("\n3. Checking exclude_rules field:")
for proj in projects:
    proj_id = proj.get('id')
    github_url = proj.get('github_url', 'N/A')
    exclude_rules = proj.get('exclude_rules', 'NOT PRESENT')
    
    print(f"  Project {proj_id}: {github_url[:50]}")
    print(f"    exclude_rules: '{exclude_rules}'")
    if 'exclude_rules' not in proj:
        print("    ⚠️  exclude_rules field is MISSING from response!")
