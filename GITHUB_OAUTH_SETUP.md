# GitHub OAuth App Setup

## 1. Create the OAuth App

Go to **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App** and fill in:

| Field | Value |
|---|---|
| Homepage URL | `http://YOUR_SERVER_IP:3000` |
| Authorization callback URL | `http://YOUR_SERVER_IP:3000/integrations` |

## 2. Get Credentials

- **Client ID** — shown on the app page.
- **Client Secret** — click "Generate a new client secret" (shown once).

## 3. Configure `backend/.env`

```env
GITHUB_CLIENT_ID=your_client_id_here
GITHUB_CLIENT_SECRET=your_client_secret_here
GITHUB_REDIRECT_URI=http://YOUR_SERVER_IP:3000/integrations
```

`GITHUB_REDIRECT_URI` must exactly match the registered callback URL.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `redirect_uri_mismatch` | Ensure `GITHUB_REDIRECT_URI` matches GitHub app settings |
| "GitHub not configured" | Check `GITHUB_CLIENT_ID` in `.env` and restart backend |
| 401 after redirect | Regenerate client secret on GitHub and update `.env` |
