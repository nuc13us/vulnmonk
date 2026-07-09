# Google SSO Setup

This guide explains how to enable "Sign in with Google" on the VulnMonk login page alongside the existing username/password login.

## Configuration Required

You need to set two environment variables before Google SSO will work:

| Where | Variable | Value |
|---|---|---|
| `backend/.env` | `GOOGLE_CLIENT_ID` | Your OAuth 2.0 Web Client ID from Google Cloud Console |
| `frontend/.env` | `REACT_APP_GOOGLE_CLIENT_ID` | Same client ID |

Both files use the **same Client ID**. No client secret is needed — the flow uses Google's ID token verification which requires only the public client ID.

---

## Create a Google OAuth Client ID

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Go to **APIs & Services → OAuth consent screen**
   - User Type: **Internal** (restricts login to users within your Google Workspace organisation only)
   - Fill in App name (e.g. `VulnMonk`) and support email → Save
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - **Authorized JavaScript origins**: `https://yourdomain.com`
   - **Authorized redirect URIs**: `https://yourdomain.com` (the `@react-oauth/google` library handles the flow in-page, no redirect URI needed beyond this)
5. Click **Create** → copy the **Client ID** (looks like `123456789-abc....apps.googleusercontent.com`)

---

## Add the Credentials

**`backend/.env`**
```
GOOGLE_CLIENT_ID=123456789-abc....apps.googleusercontent.com
```

**`frontend/.env`**
```
REACT_APP_GOOGLE_CLIENT_ID=123456789-abc....apps.googleusercontent.com
```

---

## How It Works

1. User clicks the Google button on the login page
2. Google issues a signed **ID token** directly to the browser
3. The frontend sends the token to `POST /api/auth/google`
4. The backend verifies the token by calling Google's public `tokeninfo` API — no client secret required
5. If valid, the backend finds or auto-creates a VulnMonk user using the Google email address, then returns a VulnMonk JWT
6. New Google SSO users are created with `role="user"` — promote to admin via **Settings → Users** if needed

