# GitHub App Setup

> **Security reminder:** The webhook endpoint receives inbound requests from GitHub and the GitHub App can access repository contents. Set this up only on a secured host (TLS, restricted inbound access where possible) and keep your private key + webhook secret confidential.

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

## 4. Configure the app in VulnMonk

After the app is created in GitHub, save it in VulnMonk from the Integrations page:

1. Open the VulnMonk admin UI.
2. Go to the Integrations page.
3. Add a new GitHub App configuration.
4. Upload the generated private key `.pem`.
5. Save the App ID, App Slug, and webhook secret.
6. Use the Install button for the app to install it on the correct org/account.

Set the following in `backend/.env` only for the frontend URL used in PR status links:

```env
FRONTEND_URL=http://YOUR_SERVER_IP:3000
```

> `FRONTEND_URL` is used to build the **Details** link on the GitHub PR status check. Set it to the public URL of your VulnMonk frontend so the link is reachable from GitHub.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "GitHub not configured" | Save the app in the Integrations page and confirm its app ID / private key / slug are present |
| Webhook not triggering | Verify the Webhook URL and ensure the server is publicly accessible |

> **Installing in other organizations:** By default, a GitHub App can only be installed on the account that created it. To install it on other organizations, go to **GitHub App settings → Advanced** and set the app visibility to **Public**.
