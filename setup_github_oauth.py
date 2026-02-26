#!/usr/bin/env python3
"""
Script to help configure GitHub OAuth for VulnMonk.
This script will guide you through setting up GitHub OAuth authentication.
"""

import os
import sys
from pathlib import Path

def print_header():
    print("\n" + "="*70)
    print(" GitHub OAuth Setup for VulnMonk SAST Dashboard")
    print("="*70 + "\n")

def print_step(step_num, title):
    print(f"\n{'='*70}")
    print(f" Step {step_num}: {title}")
    print(f"{'='*70}\n")

def main():
    print_header()
    
    print("This script will help you configure GitHub OAuth authentication.")
    print("You'll need to:")
    print("  1. Create a GitHub OAuth App")
    print("  2. Configure environment variables")
    print("  3. Restart the backend server")
    print()
    
    input("Press Enter to continue...")
    
    # Step 1: Create GitHub OAuth App
    print_step(1, "Create GitHub OAuth App")
    print("1. Open your browser and go to:")
    print("   → https://github.com/settings/developers")
    print()
    print("2. Click 'OAuth Apps' → 'New OAuth App'")
    print()
    print("3. Fill in the form:")
    print("   - Application name: VulnMonk SAST Dashboard")
    print("   - Homepage URL: http://localhost:3000")
    print("   - Authorization callback URL: http://localhost:3000/integrations")
    print()
    print("4. Click 'Register application'")
    print()
    print("5. On the next page:")
    print("   - Copy the 'Client ID'")
    print("   - Click 'Generate a new client secret'")
    print("   - Copy the 'Client Secret' (you won't see it again!)")
    print()
    
    input("Press Enter when you have your Client ID and Client Secret...")
    
    # Step 2: Get credentials
    print_step(2, "Enter Your GitHub OAuth Credentials")
    print()
    
    client_id = input("Enter your GitHub Client ID: ").strip()
    if not client_id:
        print("❌ Client ID cannot be empty!")
        sys.exit(1)
    
    client_secret = input("Enter your GitHub Client Secret: ").strip()
    if not client_secret:
        print("❌ Client Secret cannot be empty!")
        sys.exit(1)
    
    redirect_uri = input("Enter redirect URI [http://localhost:3000/integrations]: ").strip()
    if not redirect_uri:
        redirect_uri = "http://localhost:3000/integrations"
    
    cors_origins = input("Enter CORS origins [http://localhost:3000]: ").strip()
    if not cors_origins:
        cors_origins = "http://localhost:3000"
    
    # Step 3: Create .env file
    print_step(3, "Creating Environment Configuration")
    
    backend_dir = Path("backend")
    if not backend_dir.exists():
        print("❌ Error: backend directory not found!")
        print("   Make sure you're running this script from the project root.")
        sys.exit(1)
    
    env_path = backend_dir / ".env"
    
    if env_path.exists():
        response = input(f"\n⚠️  {env_path} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)
    
    env_content = f"""# GitHub OAuth Configuration
GITHUB_CLIENT_ID={client_id}
GITHUB_CLIENT_SECRET={client_secret}
GITHUB_REDIRECT_URI={redirect_uri}

# CORS Configuration
CORS_ORIGINS={cors_origins}

# Database Path (optional)
# DATABASE_PATH=/path/to/vulnmonk.db
"""
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Created {env_path}")
    print()
    
    # Step 4: Next steps
    print_step(4, "Next Steps")
    print("Configuration complete! Now:")
    print()
    print("1. Restart your backend server:")
    print("   cd backend")
    print("   python3 -m uvicorn main:app --reload")
    print()
    print("2. Make sure your frontend is running:")
    print("   cd frontend")
    print("   npm start")
    print()
    print("3. Navigate to: http://localhost:3000/integrations")
    print()
    print("4. Click 'Connect with GitHub' to authenticate")
    print()
    print("✅ Setup complete!")
    print()
    print("📖 For more information, see: GITHUB_OAUTH_SETUP.md")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
