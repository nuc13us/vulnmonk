# GitHub App Setup

## 1. Create the GitHub App

Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App** and fill in:

| Field | Value |
|---|---|
| Homepage URL | `http://YOUR_SERVER_IP:3000` |
| Webhook URL | `http://YOUR_SERVER_IP:3000/api/webhooks/github` |

Generate a webhook secret and paste it into the **Webhook secret** field:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 2. Set Permissions

Under **Repository permissions**:

| Permission | Level |
|---|---|
| Commit statuses | Read and write |
| Contents | Read only |
| Pull requests | Read and write |

Under **Subscribe to events**, enable **Pull request**.
Click **Create GitHub App** to finish.

## 3. Get Credentials

- **App ID** — shown on the app page.
- **App Slug** — the app name visible in the URL (e.g. `github.com/apps/your-slug`).
- **Private key** — click "Generate a private key" and save the `.pem` file.

## 4. Install the GitHub App

Go to **GitHub App settings → Install App** and install it on your account or the target organization. This grants the app access to repositories.

## 5. Configure `backend/.env`

Copy the private key to the backend directory:
```bash
cp ~/Downloads/your-app.private-key.pem backend/your-app.private-key.pem
```

Then set in `backend/.env`:
```env
GITHUB_APP_ID=your_app_id_here
GITHUB_APP_SLUG=your_app_slug
GITHUB_APP_PRIVATE_KEY=backend/your-app-private-key.pem
GITHUB_APP_WEBHOOK_SECRET=your_webhook_secret
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| "GitHub not configured" | Check `GITHUB_APP_ID` in `.env` and restart backend |
| Webhook not triggering | Verify the Webhook URL and ensure the server is publicly accessible |

> **Installing in other organizations:** By default, a GitHub App can only be installed on the account that created it. To install it on other organizations, go to **GitHub App settings → Advanced** and set the app visibility to **Public**.
