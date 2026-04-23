# NEST — Deploy

Three ways to run this repo. Local dev is untouched (`python app.py` + `npm run dev`); the configs here are for containerized prod and the two hosted platforms the brief named.

## Truth-in-advertising

The deploy plan in Series 12 referenced systems that do **not** exist in this repo yet:

- **Supabase schema / migrations** — no tables, no RLS, no Realtime. State is in-memory Python dicts.
- **Auth (three roles)** — no login, no JWT, no middleware.
- **Document ingestion** — Series 3 skipped.
- **FRED / SendGrid / Stripe integrations** — keys are accepted in `.env` as placeholders, but nothing reads them.
- **Vector / Maxwell agents** — not built. Morgan, Aria, Sterling are the only agents.

What **is** wired and will deploy:
- Flask + Flask-SocketIO backend on `:6000` with `/api/fund`, `/api/marketing`, `/api/deals`, `/api/health`, and live WebSocket ticker.
- Next.js 14 frontend on `:4000` with `(public)` marketing site and `(app)` fund + marketing studio.
- Three agents (Morgan/Aria/Sterling) backed by the Anthropic API when `ANTHROPIC_API_KEY` is set; graceful stubs when it is not.

The post-deploy checklist at the bottom reflects only what is actually testable today.

## Option 1 — Docker Compose (single host, nginx reverse proxy)

```
cp backend/.env.example backend/.env   # fill in ANTHROPIC_API_KEY
docker compose build
docker compose up -d
open http://localhost
```

nginx terminates on `:80` and routes:
- `/api/*`           → `backend:6000`
- `/socket.io/*`     → `backend:6000` (WebSocket upgrade headers set)
- everything else    → `frontend:4000`

Since nginx fronts both, `NEXT_PUBLIC_API_URL` is built empty — the Next.js client calls the same origin it was served from. For split origins override `NEXT_PUBLIC_API_URL` at build time.

## Option 2 — Railway (backend) + Vercel (frontend)

### Railway — backend
1. New project → Deploy from GitHub repo.
2. Service root: `backend/`. Railway picks up `backend/Dockerfile` automatically; `railway.json` at the repo root pins the start command and healthcheck.
3. Set variables (from `backend/.env.example`). Minimum for a working deploy: `SECRET_KEY`, `FRONTEND_ORIGIN=https://<your-vercel-domain>`, `ANTHROPIC_API_KEY`, `DEBUG=false`. Leave the Supabase/FRED/SendGrid/Stripe keys empty — nothing in code reads them yet.
4. Deploy. Confirm `GET https://<railway-url>/api/health` returns `{"ok": true}`.

### Vercel — frontend
1. New project → import repo. Root directory: `frontend/`. Framework preset: Next.js.
2. Environment variables:
   - `NEXT_PUBLIC_API_URL` = your Railway URL (e.g. `https://nest-backend.up.railway.app`).
3. Deploy. `frontend/vercel.json` ships `pdx1` region (Portland) by default.
4. Back on Railway, update `FRONTEND_ORIGIN` to the Vercel URL so Flask-CORS and Socket.IO accept it.

### WebSocket note for split deploys
Flask-SocketIO + Railway works out of the box over wss. The client (`frontend/lib/socket.ts`) reads `NEXT_PUBLIC_API_URL` and opens `wss://<railway-url>/socket.io/` — no extra config. If you later move behind Cloudflare, enable WebSockets in the zone settings.

## Option 3 — Supabase (aspirational, not yet integrated)

Leaving this section as a placeholder. Before you can run Series 12's Supabase steps meaningfully we need:
- A migrations directory (`backend/migrations/` or similar) — none exists.
- SQLAlchemy or `supabase-py` in `requirements.txt` — neither is there.
- RLS policies authored per table — no tables.

When you're ready, the right order is: design the schema, generate migrations, swap the in-memory `FundEngine`, `DealsRegistry`, `AriaAgent._leads` stores for DB-backed ones, then do Supabase.

## Environment variable map (what reads what today)

| Var                         | Read by                                     | Wired? |
|-----------------------------|---------------------------------------------|--------|
| `PORT`, `HOST`, `DEBUG`     | `backend/config.py` → `app.py`              | yes    |
| `SECRET_KEY`                | Flask app config                            | yes    |
| `FRONTEND_ORIGIN`           | Flask-CORS + SocketIO CORS                  | yes    |
| `FUND_TICK_SECONDS`         | `app.py` ticker thread                      | yes    |
| `B_TRANCHE_COUPON_PCT`, `MGMT_FEE_PCT`, `WC_SPREAD_BPS` | `FundEngine` | yes    |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS` | `agents/_claude.py` | yes |
| `NEXT_PUBLIC_API_URL`       | `frontend/lib/api.ts`, `lib/socket.ts`      | yes    |
| `SUPABASE_URL`              | — | no |
| `SUPABASE_SERVICE_KEY`      | — | no |
| `JWT_SECRET_KEY`            | — | no |
| `FRED_API_KEY`              | — | no |
| `SENDGRID_API_KEY`          | — | no |
| `STRIPE_SECRET_KEY`         | — | no |

## Post-deploy checklist — honest version

- [ ] `GET /api/health` returns `{"ok": true, "service": "nest-backend"}`
- [ ] Public homepage `/` renders with evergreen palette and 8 sections
- [ ] `/fund` loads position via REST and receives `fund_update` over WebSocket within 60s
- [ ] Marketing Studio `/admin/marketing` generates content when `ANTHROPIC_API_KEY` is set
- [ ] Intake form `POST /api/marketing/intake` creates a lead and returns Aria's reply
- [ ] `/api/deals/active` returns the four seed deals
- [ ] nginx (Option 1 only) passes WebSocket upgrade for `/socket.io/`

Items from the original Series 12 checklist that **cannot be checked** until their prerequisite series are built:

- ~~Auth flow tested (all 3 roles)~~ — no auth exists.
- ~~Document upload + extraction working~~ — no upload path.
- ~~Vector agent running on schedule~~ — agent not built.
- ~~Marketplace visible to public~~ — only the preview on the homepage; full marketplace not built.
- ~~Admin portal locked to admin role only~~ — no roles, no gating.
