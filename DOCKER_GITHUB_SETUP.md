# GitHub Integration Setup for Docker

This guide explains how to configure GitHub App integration when running VulnMonk in Docker.

## Problem Overview

GitHub integration requires proper configuration of environment variables and the GitHub App private key. In Docker environments, these need to be properly passed into the container.

## Solution

### Option 1: Using backend/.env file (Recommended)

1. **Create the GitHub App** (if not already done):
   - Follow the instructions in `GITHUB_OAUTH_SETUP.md`
   - Download the private key `.pem` file

2. **Place the private key file**:
   ```bash
   # Copy your downloaded private key to the backend directory
   cp ~/Downloads/vulnmonk.2024-12-01.private-key.pem backend/vulnmonk.private-key.pem
   ```

3. **Configure backend/.env**:
   ```bash
   # Copy the example file
   cp backend/.env.example backend/.env
   
   # Edit backend/.env with your GitHub App credentials
   ```
   
   Add the following to `backend/.env`:
   ```env
   # GitHub App Configuration
   GITHUB_APP_ID=123456
   GITHUB_APP_SLUG=your-app-slug
   GITHUB_APP_PRIVATE_KEY=backend/vulnmonk.private-key.pem
   GITHUB_APP_WEBHOOK_SECRET=your-webhook-secret
   
   # Other required settings
   JWT_SECRET_KEY=your-secret-key-here
   FRONTEND_URL=http://localhost:3000
   ```

4. **Rebuild and restart Docker containers**:
   ```bash
   # Rebuild to include the .env file and private key
   docker compose down
   docker compose build --no-cache backend
   docker compose up -d
   ```

### Option 2: Using Environment Variables

Instead of using a `.env` file, you can pass the private key as an environment variable:

```bash
# Export the private key content (with literal \n)
export GITHUB_APP_PRIVATE_KEY=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' backend/vulnmonk.private-key.pem)
export GITHUB_APP_ID=123456
export GITHUB_APP_SLUG=your-app-slug
export GITHUB_APP_WEBHOOK_SECRET=your-webhook-secret

# Start Docker Compose
docker compose up -d
```

### Option 3: Using docker-compose override

Create a `docker-compose.override.yml` file (not tracked in git):

```yaml
services:
  backend:
    environment:
      - GITHUB_APP_ID=123456
      - GITHUB_APP_SLUG=your-app-slug
      - GITHUB_APP_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----
      - GITHUB_APP_WEBHOOK_SECRET=your-webhook-secret
```

## Verification

After setup, verify the integration is working:

1. **Check the backend logs**:
   ```bash
   docker compose logs backend | grep -i github
   ```

2. **Test the integration**:
   - Navigate to the Integrations page in VulnMonk UI (http://localhost:3000/integrations)
   - Click "Install GitHub App"
   - Complete the GitHub App installation
   - Click "↻ Refresh" to sync installations
   - You should see your GitHub account/organization listed

3. **Verify environment variables are loaded**:
   ```bash
   # Check if GitHub App ID is set
   docker compose exec backend sh -c 'echo $GITHUB_APP_ID'
   
   # Should return your App ID, not empty
   ```

## Troubleshooting

### Issue: "GitHub App credentials not configured" error

**Cause**: Environment variables are not being loaded into the container.

**Solution**:
- Ensure `backend/.env` exists with the correct credentials
- Rebuild the container: `docker compose build --no-cache backend`
- Check that `.dockerignore` doesn't block `backend/.env`

### Issue: "Could not read GITHUB_APP_PRIVATE_KEY file" error

**Cause**: The private key file path is incorrect or the file isn't in the container.

**Solution**:
- Verify the file exists: `ls -la backend/*.pem`
- Use the inline private key format in `backend/.env`:
  ```env
  GITHUB_APP_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----
  ```
- Or ensure the path is relative to `/app` inside the container: `backend/your-key.pem`

### Issue: Integration installed but not showing in UI

**Cause**: Webhook events are not being received or processed.

**Solution**:
- Ensure your VulnMonk instance is accessible from the internet (required for GitHub webhooks)
- Use ngrok or similar for local development:
  ```bash
  ngrok http 3000
  ```
- Update the GitHub App webhook URL to point to your ngrok URL
- Click "↻ Refresh" in the Integrations page to manually sync installations

### Issue: Private key format error

**Cause**: The private key has incorrect line breaks or formatting.

**Solution**:
Convert your private key to the inline format:
```bash
# Convert PEM to inline format with \n
awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' backend/vulnmonk.private-key.pem
```

Then paste the output directly into `backend/.env`:
```env
GITHUB_APP_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----
```

## Important Notes

1. **Rebuild Required**: After adding or modifying the `backend/.env` file or private key, you MUST rebuild the Docker image:
   ```bash
   docker compose build --no-cache backend
   docker compose up -d
   ```

2. **Security**: Never commit `backend/.env` or `.pem` files to version control. They are already in `.gitignore`.

3. **Webhook URL**: For production deployments, ensure your webhook URL in the GitHub App settings points to:
   ```
   https://your-domain.com/api/webhooks/github
   ```

4. **Database Persistence**: GitHub integration records are stored in the SQLite database, which is persisted in the `vulnmonk-data` Docker volume.

## Testing the Integration

1. **Install the GitHub App** on a test repository
2. **Verify installation** appears in the Integrations UI
3. **Import a repository** from the installation
4. **Create a test PR** in the repository
5. **Check PR Scan Results** in VulnMonk

If all steps complete successfully, your GitHub integration is properly configured!