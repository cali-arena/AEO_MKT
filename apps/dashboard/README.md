# AI MKT Dashboard

Next.js (App Router) dashboard for tenant analytics and monitoring.

## Prerequisites

- Node.js 18+
- npm (or pnpm/yarn)

## Run locally (from monorepo root)

```bash
# From project root
cd apps/dashboard
npm install
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000).

## Scripts

| Script  | Description                    |
|---------|--------------------------------|
| `dev`   | Start dev server (port 3000)   |
| `build` | Production build               |
| `start` | Start production server        |
| `lint`  | Run ESLint                     |

## Environment

- `NEXT_PUBLIC_API_BASE` – Backend API base URL (default: `http://localhost:8000`). Copy `.env.example` to `.env.local`.

### Vercel

For monorepo deploys: set **Root Directory** to `apps/dashboard` in the Vercel project.

| Variable                  | Description                                   |
|---------------------------|-----------------------------------------------|
| `NEXT_PUBLIC_API_BASE`    | Backend API URL (e.g. `https://api.example.com`) |

## Structure

```
app/
  login/page.tsx
  tenants/[tenantId]/
    layout.tsx
    overview/page.tsx
    domains/page.tsx
    trends/page.tsx
    worst-queries/page.tsx
    leakage/page.tsx
components/
  ui/          # shadcn or custom UI
  charts/
  tables/
  layout/
lib/
  api.ts       # API client
  auth.ts      # Auth helpers
  types.ts     # Shared types
```
