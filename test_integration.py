import requests
import json

# Configuration
API_BASE = "http://127.0.0.1:8000"
USERNAME = "admin"  # Replace with your admin username
PASSWORD = "admin"  # Replace with your admin password

# Step 1: Login and get token
login_data = {
    "username": USERNAME,
    "password": PASSWORD
}
response = requests.post(
    f"{API_BASE}/auth/login",
    data=login_data
)
token = response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("✓ Logged in successfully")

# Step 2: Create GitHub integration
integration_data = {
    "org_name": "your-org-name",  # Replace with actual GitHub org name
    "access_token": "your-github-token"  # Replace with your GitHub PAT
}

response = requests.post(
    f"{API_BASE}/integrations/github",
    headers=headers,
    json=integration_data
)

if response.status_code == 200:
    integration = response.json()
    print(f"✓ Created integration with ID: {integration['id']}")
    integration_id = integration['id']
    
    # Step 3: Fetch repositories
    response = requests.get(
        f"{API_BASE}/integrations/github/{integration_id}/repositories",
        headers=headers
    )
    
    if response.status_code == 200:
        repos = response.json()
        print(f"✓ Found {len(repos)} repositories:")
        for repo in repos[:5]:  # Show first 5
            print(f"  - {repo['name']} ({repo['language']})")
    else:
        print(f"✗ Error fetching repos: {response.status_code}")
        print(response.json())
else:
    print(f"✗ Error creating integration: {response.status_code}")
    print(response.json())
