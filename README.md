# VAT Report Analyzer Rwanda

A stateless tool that ingests Rwanda EBM (Electronic Billing Machine) Sales and Purchase
Excel exports and generates an accountant-ready VAT analysis report — figures, a
Kinyarwanda WhatsApp-style summary, and a branded PDF — for a user-selected reporting
period.

There are no user accounts and nothing is persisted. Each report is computed fresh from
the two files you upload in a single request, and both the uploads and the generated PDF
are discarded once the response is sent — no database, no stored files.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a deeper look at the request flow,
parsing strategy, and VAT formulas.

## Features

- **Tolerant Excel parsing** — resolves columns by matching header *names* against alias
  dictionaries (not fixed positions), so it survives EBM template drift such as renamed
  or reordered columns. Company name, TIN, and reporting period are extracted from the
  free-form metadata rows above the data table.
- **VAT position calculation** — output VAT, input VAT, payable/refund position, refund
  carried forward, and the additional sales/purchases needed to clear a refund or payable
  balance.
- **Missing-receipt detection** — groups SDC receipt numbers by device prefix and flags
  gaps in the sequence (e.g. `SDC010193518/10`, `.../11`, missing `.../12`), a common sign
  of an unrecorded sale.
- **Branded PDF report** — generated in-memory with ReportLab (pure Python, no system
  dependencies).
- **WhatsApp-ready summary text** — a Kinyarwanda-language report accountants can copy or
  share directly to a client's WhatsApp, with time-of-day-appropriate greetings.

## Stack

- **Backend**: FastAPI, Pydantic v2, Pandas, openpyxl, ReportLab — no database
- **Frontend**: Next.js 15, TypeScript, TailwindCSS, shadcn/ui, TanStack Query, React Hook Form, Zod
- **Infra**: Docker Compose + Nginx (see [Docker notes](#docker-compose-status) below — the
  compose file expects a `backend/Dockerfile`, `frontend/Dockerfile`, and
  `nginx/nginx.conf` that aren't in this repo yet)

## Local development

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt   # runtime deps + test suite; use requirements.txt for runtime-only
cp ../.env.example .env
uvicorn app.main:app --reload
```

- API: http://localhost:8000/api
- Swagger docs: http://localhost:8000/api/docs

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

- App: http://localhost:3000

The frontend calls the backend at `NEXT_PUBLIC_API_URL` (see
[`frontend/.env.local.example`](frontend/.env.local.example)), so make sure the backend
is running first.

## Deploying to Vercel

Both halves of the app deploy to Vercel as **two separate projects** from this one repo
(frontend and backend each have their own `Root Directory`, build, and env vars).

### Backend (`backend/`)

The FastAPI app is exposed to Vercel's Python runtime via `backend/api/index.py`
(re-exports the ASGI `app` from `app/main.py`), with `backend/vercel.json` rewriting every
path to that function so FastAPI's own router handles `/api/...`, `/api/docs`, etc.

1. New Vercel project → import this repo → set **Root Directory** to `backend`.
2. Framework preset: **Other**. Vercel auto-installs from `requirements.txt` (kept
   runtime-only/lean on purpose — test deps live in `requirements-dev.txt` instead) and
   picks up `backend/vercel.json` automatically.
3. Set environment variables (Project Settings → Environment Variables) from
   [`.env.example`](.env.example) — at minimum `BACKEND_CORS_ORIGINS` set to your
   frontend's production URL (e.g. `["https://your-frontend.vercel.app"]`).
4. Deploy. The API root becomes `https://<backend-project>.vercel.app`, with docs at
   `/api/docs`.

Known serverless caveats:

- **Rate limiting** (`slowapi`, in-memory) is per-instance, not shared across a
  serverless function's cold-started copies — treat `RATE_LIMIT_GENERATE` as
  best-effort on Vercel, not a hard guarantee. A shared store (e.g. Upstash Redis) would
  be needed for real cross-instance limiting.
- **Execution time**: `maxDuration` is set to 30s in `backend/vercel.json`; Vercel caps
  this per plan (lower it if your plan's limit is stricter). Very large Excel files could
  approach this.
- **Deployment size**: the function bundles pandas/reportlab and is comfortably under
  Vercel's 250MB unzipped limit at the time of writing, but keep an eye on it if adding
  dependencies.
- Nothing is written to disk (reports are generated in memory), so the read-only
  serverless filesystem is not an issue.

### Frontend (`frontend/`)

1. New Vercel project → import this repo → set **Root Directory** to `frontend`.
   Framework preset **Next.js** is auto-detected.
2. Set `NEXT_PUBLIC_API_URL` to the backend project's URL plus `/api`, e.g.
   `https://your-backend.vercel.app/api`.
3. Deploy. `next.config.ts` skips the Docker-only `output: "standalone"` automatically
   when Vercel's `VERCEL` env var is present.

Preview deployments get a unique, unpredictable URL per branch/PR, which won't match a
fixed `BACKEND_CORS_ORIGINS` entry — add specific preview URLs there as needed, or point
preview builds' `NEXT_PUBLIC_API_URL` at a non-production backend with looser CORS.

## Docker Compose (alternative, self-hosted)

[`docker-compose.yml`](docker-compose.yml) defines `backend`, `frontend`, and `nginx`
services wired together on one network, but the `backend/Dockerfile`,
`frontend/Dockerfile`, and `nginx/nginx.conf` it references have not been added to this
repo yet — `docker compose up` will fail until those exist. Use the local development
steps above, or the Vercel instructions above, until the container images are added.

## Environment variables

Copy [`.env.example`](.env.example) to `.env` (backend) and
[`frontend/.env.local.example`](frontend/.env.local.example) to `frontend/.env.local`,
then adjust as needed.

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | `development` disables the HSTS response header |
| `TZ` | `Africa/Kigali` | Timezone used by the containers |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed origins for the frontend to call the API |
| `MAX_UPLOAD_SIZE_MB` | `20` | Per-file upload size cap |
| `VAT_RATE` | `0.18` | Standard VAT rate used in all calculations |
| `RATE_LIMIT_GENERATE` | `20/minute` | Rate limit on `POST /api/reports/generate`, keyed by client IP |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | Base URL the frontend uses to reach the backend |

## API

A single endpoint does all the work:

```
POST /api/reports/generate   (multipart/form-data)
```

**Form fields:**

| Field | Type | Notes |
|---|---|---|
| `company_name` | string | Required |
| `tin` | string | Required, exactly 9 digits |
| `period_start` | date (`YYYY-MM-DD`) | Required |
| `period_end` | date (`YYYY-MM-DD`) | Required, must be ≥ `period_start` |
| `previous_remaining_refund` | number | Optional, ≥ 0, default `0` — refund carried forward from a prior period |
| `sales_file` | file | Required, `.xlsx`/`.xls`, EBM Sales export |
| `purchase_file` | file | Required, `.xlsx`/`.xls`, EBM Purchase export |

**Response:** VAT figures, `missing_sales_receipts` (gap groups, if any),
`whatsapp_text` (ready-to-share summary), and `pdf_base64` (the report PDF, base64
encoded).

Full request/response schemas are available at `/api/docs` (Swagger) or
`/api/redoc` while the backend is running.

## Testing

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

Tests cover the calculation engine, Excel parser, receipt-gap detector, report-text
builder (all pure unit tests, no I/O), and an integration test that drives
`POST /api/reports/generate` end to end.

## Project layout

```
backend/app/
  api/v1/        REST routers — a single /reports/generate endpoint, plus /health
  core/          config, logging, rate limiting, exceptions
  services/      business logic (Excel parsing, VAT calculation, receipt-gap detection,
                 PDF generation, WhatsApp text generation)
  schemas/       Pydantic request/response contracts
  utils/         shared formatting helpers (currency, dates)
  tests/         unit + integration tests

frontend/
  app/           Next.js App Router pages
  components/    reusable UI components (shadcn/ui based)
  hooks/         reusable React hooks (TanStack Query wrappers)
  services/      typed API client functions
  lib/           utilities (API client, Zod validation, WhatsApp share helper)
  types/         shared TypeScript types
```
