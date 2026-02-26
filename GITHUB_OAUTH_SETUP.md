# GitHub OAuth Setup Guide

This guide will help you configure GitHub OAuth authentication for the VulnMonk SAST Dashboard.

## Why OAuth Instead of Personal Access Tokens?

OAuth provides several advantages:
- **More Secure**: Users authenticate directly with GitHub
- **Better Permissions**: Granular access control
- **No Token Management**: No need to manually create and store tokens
- **User-Friendly**: Simple "Connect with GitHub" button

## Setup Steps

### 1. Create a GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **"OAuth Apps"** in the left sidebar
3. Click **"New OAuth App"**
4. Fill in the application details:
   - **Application name**: `VulnMonk SAST Dashboard` (or your preferred name)
   - **Homepage URL**: `http://localhost:3000` (change for production)
   - **Authorization callback URL**: `http://localhost:3000/integrations`
   - **Application description**: (optional) `Security scanning dashboard`
5. Click **"Register application"**

### 2. Get Your Client Credentials

After creating the OAuth app:
1. Copy the **Client ID**
2. Click **"Generate a new client secret"**
3. Copy the **Client Secret** (you won't be able to see it again!)

### 3. Configure Environment Variables

Create a `.env` file in the backend directory:

```bash
cd backend
cp ../.env.example .env
```

Edit `.env` and add your credentials:

```env
GITHUB_CLIENT_ID=your_client_id_here
GITHUB_CLIENT_SECRET=your_client_secret_here
GITHUB_REDIRECT_URI=http://localhost:3000/integrations
CORS_ORIGINS=http://localhost:3000
```

### 4. Restart the Backend Server

```bash
# In the backend directory
python3 -m uvicorn main:app --reload
```

Or from the project root:

```bash
cd /path/to/vulnmonk
python3 -m uvicorn backend.main:app --reload
```

### 5. Test the Integration

1. Open the frontend: http://localhost:3000
2. Login with your admin account
3. Navigate to **Integrations**
4. Click **"Connect with GitHub"**
5. Authorize the application on GitHub
6. You'll be redirected back with your GitHub account connected

## Production Deployment

For production environments:

1. **Update the OAuth App URLs**:
   - Homepage URL: `https://yourdomain.com`
   - Authorization callback URL: `https://yourdomain.com/integrations`

2. **Update Environment Variables**:
   ```env
   GITHUB_REDIRECT_URI=https://yourdomain.com/integrations
   CORS_ORIGINS=https://yourdomain.com
   ```

3. **Secure Your Secrets**:
   - Never commit `.env` file to version control
   - Use environment variables in your hosting platform
   - Consider using a secrets management service

## Permissions Requested

The OAuth flow requests the following GitHub scopes:
- **`repo`**: Access to repositories (read-only for scanning)
- **`read:org`**: Read organization membership and repository access

## Troubleshooting

### "GitHub OAuth is not configured" Error

**Solution**: Ensure `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` are set in your `.env` file.

### OAuth Redirect Issues

**Solution**: Verify the callback URL in your GitHub OAuth app matches `GITHUB_REDIRECT_URI` in `.env`.

### "Failed to exchange code for access token"

**Solution**: Check that your `GITHUB_CLIENT_SECRET` is correct and hasn't expired.

## Security Best Practices

1. **Rotate Secrets Regularly**: Generate new client secrets periodically
2. **Use HTTPS in Production**: Never use OAuth over HTTP in production
3. **Limit Access**: Only grant OAuth app access to necessary permissions
4. **Monitor Usage**: Review GitHub OAuth app usage in settings
5. **Revoke Unused Tokens**: Remove integrations that are no longer needed

## FAQ

**Q: Can multiple users connect their GitHub accounts?**
A: Currently, only admin users can connect GitHub integrations. Each integration is shared across all users.

**Q: What happens if I revoke access on GitHub?**
A: The integration will stop working. Delete it from the dashboard and reconnect.

**Q: Can I connect multiple GitHub accounts/organizations?**
A: The current implementation supports one GitHub account per instance. The authenticated user's account and organizations are accessible.

**Q: Is my GitHub access token stored securely?**
A: Yes, tokens are stored in the database. For production, ensure the database is properly secured and encrypted.

## Next Steps

After successful setup:
1. Browse repositories from your GitHub account/organizations
2. Select repositories to import as projects
3. Run security scans on imported projects
4. View and manage scan results in the dashboard
