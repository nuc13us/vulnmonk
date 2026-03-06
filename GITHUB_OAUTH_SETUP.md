# GitHub OAuth App Setup

VulnMonk uses a GitHub OAuth App to let users authenticate with GitHub and import private repositories. Follow the steps below to create one and configure the credentials.

> **Official reference:** [Creating an OAuth App — GitHub Docs](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)

---

## 1. Create a GitHub OAuth App

1. Go to **GitHub → Settings → Developer settings → OAuth Apps**  
   Direct link: https://github.com/settings/developers

2. Click **"New OAuth App"**.

3. Fill in the registration form:

   | Field | Value |
   |---|---|
   | **Application name** | `VulnMonk` (or any name you like) |
   | **Homepage URL** | The URL where your app is hosted, e.g. `http://YOUR_SERVER_IP:3000` |
   | **Authorization callback URL** | `http://YOUR_SERVER_IP:3000/integrations` |

   > Replace `YOUR_SERVER_IP` with your actual server IP or domain name.  
   > If running locally: use `http://localhost:3000/integrations`.

4. Click **"Register application"**.

---

## 2. Get Your Credentials

After registration you will see:

- **Client ID** — visible on the app page immediately.
- **Client Secret** — click **"Generate a new client secret"** and copy it. It is only shown once.

---

## 3. Add Credentials to `backend/.env`

Open (or create) `backend/.env` and set:

```env
GITHUB_CLIENT_ID=your_client_id_here
GITHUB_CLIENT_SECRET=your_client_secret_here
GITHUB_REDIRECT_URI=http://YOUR_SERVER_IP:3000/integrations
```

`GITHUB_REDIRECT_URI` must **exactly match** the "Authorization callback URL" you registered in Step 1.

---

## 4. Updating the Callback URL

If your server address changes, update **both** places:

1. GitHub → Settings → Developer settings → OAuth Apps → your app → **Edit** → "Authorization callback URL"
2. `backend/.env` → `GITHUB_REDIRECT_URI`

They must always be identical or GitHub will reject the OAuth flow.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `redirect_uri_mismatch` error from GitHub | `GITHUB_REDIRECT_URI` doesn't match the registered callback URL | Update them to match (see Step 4) |
| Integration page shows "GitHub not configured" | `GITHUB_CLIENT_ID` is missing or empty | Check `backend/.env` and restart the backend |
| 401 after GitHub redirects back | `GITHUB_CLIENT_SECRET` is wrong or expired | Regenerate the secret on GitHub and update `.env` |
