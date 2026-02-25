# Deploy dashboard to Vercel (model first)

Get the frontend running in the cloud with your API on the VM.

## 1. Push code and connect Vercel

1. Ensure your repo is on GitHub (e.g. `cali-arena/AEO_MKT`).
2. Go to [vercel.com](https://vercel.com) → **Add New** → **Project**.
3. Import the GitHub repo **AEO_MKT**.
4. **Root Directory:** Click **Edit** and set to **`apps/dashboard`** (required for this monorepo).
5. **Framework Preset:** Next.js (auto-detected).
6. **Build Command:** `npm run build` (default).
7. **Output Directory:** leave default.

## 2. Environment variable (API URL) — required

In the Vercel project → **Settings** → **Environment Variables**, add:

| Name | Value | Environments |
|------|--------|--------------|
| `NEXT_PUBLIC_API_BASE` | `http://89.167.81.215:8000` | Production, Preview |

- **Required:** On Vercel the dashboard does not use any localhost fallback; if this is missing, API calls will fail.
- Use your VM’s public IP and port where the API runs (no trailing slash).
- **Mixed content:** The API is HTTP; the dashboard on Vercel is HTTPS. Some browsers may block requests from HTTPS to HTTP. For a first deploy this often still works; if you see CORS or blank data, plan to put the API behind HTTPS (e.g. reverse proxy + Let’s Encrypt on the VM) and set `NEXT_PUBLIC_API_BASE` to `https://api.yourdomain.com`.

## 3. Deploy

Click **Deploy**. Wait for the build to finish. Vercel will give you a URL like `https://aeo-mkt-xxx.vercel.app`.

## 4. Allow the frontend in the API (CORS)

The backend must allow requests from your Vercel URL.

On the **VM**, edit `.env` in the repo root and set:

```bash
CORS_ALLOW_ORIGINS=https://YOUR_VERCEL_URL.vercel.app,http://localhost:3000
```

Replace `YOUR_VERCEL_URL` with your actual Vercel project URL (e.g. `aeo-mkt-xxx`), **no trailing slash**. Then restart the API:

```bash
cd /root/AEO_MKT
docker compose -f infra/docker-compose.yml --env-file .env up -d --build api
```

## 5. Check

- Open the Vercel URL in the browser.
- Log in (tenant token) and open **Health** or a tenant page; it should call the API.
- If the UI loads but API calls fail: check CORS (step 4), and that `NEXT_PUBLIC_API_BASE` is set and redeployed (rebuilds need the env at build time for Next.js).

## Optional: custom domain

In Vercel: **Settings** → **Domains** → add your domain and follow the DNS steps.
