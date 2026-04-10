# GitHub Integration Setup for Docker

## Setup

1. Copy the private key to the backend directory:
   ```bash
   cp ~/Downloads/vulnmonk.private-key.pem backend/vulnmonk.private-key.pem
   ```

2. Configure `backend/.env`:
   ```env
   GITHUB_APP_ID=123456
   GITHUB_APP_SLUG=your-app-slug
   GITHUB_APP_PRIVATE_KEY=backend/vulnmonk.private-key.pem
   GITHUB_APP_WEBHOOK_SECRET=your-webhook-secret
   JWT_SECRET_KEY=your-secret-key-here
   FRONTEND_URL=http://localhost:3000
   ```

3. Rebuild and start:
   ```bash
   docker compose down
   docker compose build --no-cache backend
   docker compose up -d
   ```

## Verification

Go to `http://localhost:3000/integrations`, install the GitHub App, and click "↻ Refresh". Your account/org should appear.

## Troubleshooting

| Issue | Fix |
|---|---|
| "GitHub App credentials not configured" | Check `backend/.env` exists and rebuild the container |
| "Could not read GITHUB_APP_PRIVATE_KEY" | Verify the `.pem` path or paste the key inline in `.env` |
| Integration not showing in UI | Use ngrok for local webhooks; click "↻ Refresh" to manually sync |
| Private key format error | Convert: `awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' key.pem` and paste inline |

> Never commit `backend/.env` or `.pem` files. They are in `.gitignore`.
