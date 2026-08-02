# VAT Report Analyzer Rwanda — Architecture

## 1. Overview

A multi-tenant-capable SaaS that ingests EBM (Electronic Billing Machine) Sales and
Purchase Excel exports, parses and validates them, computes VAT position, and produces
a bilingual (Kinyarwanda-flavored) accountant-ready report as PDF/text.

## 2. High-level architecture

```
                          ┌─────────────────┐
                          │      Nginx       │  (TLS, reverse proxy, static)
                          └───────┬─────────┘
                    ┌─────────────┴─────────────┐
              ┌─────▼─────┐               ┌─────▼─────┐
              │  Next.js  │               │  FastAPI   │
              │ (frontend)│──── REST ────▶│  (backend) │
              └───────────┘               └─────┬─────┘
                                                  │
                       ┌──────────────────────────┼───────────────────────┐
                       │                           │                       │
                ┌──────▼──────┐           ┌────────▼────────┐     ┌────────▼────────┐
                │  PostgreSQL │           │  Local Storage   │     │   (future) S3    │
                │             │           │ uploads/ pdfs/   │     │                  │
                └─────────────┘           └──────────────────┘     └──────────────────┘
```

Backend follows **Clean Architecture**: routes (API layer) depend on services
(business logic layer), services depend on repositories (data access layer),
repositories depend on SQLAlchemy models. Dependencies point inward only.
Routes never contain business logic or raw SQL.

```
API (FastAPI routers) → Services (business logic) → Repositories (data access) → Models (ORM)
                       ↘ Schemas (Pydantic I/O contracts, all layers)
```

## 3. Tech stack rationale

- **FastAPI + Pydantic v2**: async-first, native OpenAPI docs, strong typing end to end.
- **SQLAlchemy 2.0 (async) + Alembic**: mature ORM, explicit migrations, works well with Postgres JSONB for flexible raw-row storage.
- **Pandas + openpyxl**: column-name-based Excel parsing that tolerates EBM template drift (no positional indexing).
- **PostgreSQL**: relational integrity for financial data, numeric precision via `NUMERIC`.
- **Next.js 15 (App Router) + shadcn/ui + TanStack Query**: server components for fast first paint, React Query for cache/mutation state, Zod shared validation mirroring backend Pydantic schemas.
- **reportlab** for PDF generation: pure-Python, no external binary dependency (chosen over WeasyPrint to avoid GTK/Cairo system deps in the Docker image — simpler, smaller, more portable image).
- **JWT access + rotating refresh tokens** stored hashed in DB (`refresh_tokens` table) so they can be revoked — plain stateless JWT alone can't be invalidated on logout/compromise.

## 4. Database schema (PostgreSQL)

```
roles
├─ id (PK)
├─ name (unique)                e.g. ADMIN, ACCOUNTANT, VIEWER
└─ description

users
├─ id (PK)
├─ email (unique)
├─ hashed_password
├─ full_name
├─ role_id (FK → roles.id)
├─ is_active
├─ created_at / updated_at

refresh_tokens
├─ id (PK)
├─ user_id (FK → users.id)
├─ token_hash (unique)
├─ expires_at
├─ revoked_at (nullable)
├─ created_at

companies
├─ id (PK)
├─ name
├─ tin (unique, 9-digit Rwanda TIN)
├─ address, phone, email
├─ logo_path (nullable)
├─ owner_id (FK → users.id)          -- creator / primary owner
├─ created_at / updated_at

company_members                       -- many-to-many users↔companies (RBAC per company)
├─ id (PK)
├─ company_id (FK)
├─ user_id (FK)
├─ role (enum: OWNER, ACCOUNTANT, VIEWER)

uploads
├─ id (PK)
├─ company_id (FK → companies.id)
├─ uploaded_by (FK → users.id)
├─ file_type (enum: SALES, PURCHASE)
├─ original_filename
├─ stored_path
├─ file_hash (sha256, for duplicate detection)
├─ status (enum: PENDING, PROCESSING, PROCESSED, FAILED)
├─ period_start / period_end (detected)
├─ error_message (nullable)
├─ created_at

sales
├─ id (PK)
├─ upload_id (FK → uploads.id)
├─ company_id (FK, denormalized for query speed)
├─ invoice_number
├─ invoice_date
├─ customer_name / customer_tin (nullable)
├─ taxable_amount NUMERIC(18,2)
├─ vat_amount NUMERIC(18,2)
├─ total_amount NUMERIC(18,2)
├─ raw_row JSONB                       -- full original row for audit/debug

purchases
├─ id (PK)
├─ upload_id (FK → uploads.id)
├─ company_id (FK)
├─ invoice_number
├─ invoice_date
├─ supplier_name / supplier_tin (nullable)
├─ taxable_amount NUMERIC(18,2)
├─ vat_amount NUMERIC(18,2)
├─ total_amount NUMERIC(18,2)
├─ raw_row JSONB

reports
├─ id (PK)
├─ company_id (FK)
├─ sales_upload_id (FK → uploads.id)
├─ purchase_upload_id (FK → uploads.id)
├─ generated_by (FK → users.id)
├─ period_start / period_end
├─ total_taxable_sales NUMERIC(18,2)
├─ output_vat NUMERIC(18,2)
├─ total_taxable_purchases NUMERIC(18,2)
├─ input_vat NUMERIC(18,2)
├─ vat_difference NUMERIC(18,2)         -- output_vat - input_vat
├─ vat_payable NUMERIC(18,2)            -- max(vat_difference, 0)
├─ refund NUMERIC(18,2)                 -- max(-vat_difference, 0)
├─ remaining_refund NUMERIC(18,2)       -- refund carried forward, adjustable
├─ required_sales_to_clear_refund NUMERIC(18,2)
├─ pdf_path (nullable)
├─ created_at

audit_logs
├─ id (PK)
├─ user_id (FK → users.id, nullable for system events)
├─ action (e.g. LOGIN, UPLOAD_CREATED, REPORT_GENERATED, PDF_DOWNLOADED)
├─ entity_type / entity_id
├─ metadata JSONB
├─ ip_address
├─ created_at
```

ER relationships:
`users 1—N companies (owner)`, `users N—N companies (company_members)`,
`companies 1—N uploads`, `uploads 1—N sales|purchases`, `companies 1—N reports`,
`users 1—N audit_logs`, `users 1—N refresh_tokens`.

## 5. VAT calculation formulas

```
total_taxable_sales      = Σ sales.taxable_amount
output_vat                = Σ sales.vat_amount
total_taxable_purchases  = Σ purchases.taxable_amount
input_vat                  = Σ purchases.vat_amount

vat_difference             = output_vat - input_vat

if vat_difference >= 0:
    vat_payable = vat_difference
    refund      = 0
else:
    vat_payable = 0
    refund      = abs(vat_difference)

# Required additional taxable sales, at the standard 18% VAT rate, whose
# output VAT would exactly consume the remaining refund:
required_sales_to_clear_refund = refund / VAT_RATE     # VAT_RATE = 0.18
```

All of the above lives in `CalculationService` (`app/services/calculation_service.py`),
fully unit-testable with no I/O.

## 6. API contract (summary — full OpenAPI generated at `/api/docs`)

```
POST   /api/auth/register
POST   /api/auth/login                 → { access_token, refresh_token }
POST   /api/auth/refresh
POST   /api/auth/logout
GET    /api/auth/me

GET    /api/companies
POST   /api/companies
GET    /api/companies/{id}
PATCH  /api/companies/{id}
DELETE /api/companies/{id}
POST   /api/companies/{id}/logo

POST   /api/uploads                    (multipart: company_id, file_type, file)
GET    /api/uploads?company_id=&status=
GET    /api/uploads/{id}
GET    /api/uploads/{id}/preview       (parsed rows preview)

POST   /api/reports/generate           { company_id, sales_upload_id, purchase_upload_id }
GET    /api/reports?company_id=
GET    /api/reports/{id}
GET    /api/reports/{id}/text          (WhatsApp-ready copy text)

GET    /api/pdf/{report_id}            (streams branded PDF)

GET    /api/dashboard/summary
GET    /api/dashboard/monthly-trend?company_id=
```

Every endpoint requires `Authorization: Bearer <access_token>` except
`/api/auth/register|login|refresh`. RBAC is enforced via FastAPI dependencies
(`require_role(...)`, `require_company_access(...)`).

## 7. Security

- Passwords hashed with bcrypt (via `passlib`).
- JWT access tokens (short-lived, 15 min) signed HS256; refresh tokens (7 days) stored
  hashed in DB, rotated on every use, revocable.
- Rate limiting via `slowapi` on auth + upload endpoints.
- Pydantic validation on every input boundary; SQLAlchemy parameterized queries (no raw SQL).
- File upload validation: extension allow-list, 20 MB size cap, MIME sniff, sha256 dedup.
- Security headers + CORS allow-list via middleware.
- All mutating actions and downloads written to `audit_logs`.

## 8. Deployment

Single `docker-compose.yml` at repo root brings up: `postgres`, `backend` (FastAPI +
Alembic migrations run on start), `frontend` (Next.js standalone build), `nginx`
(reverse proxy + TLS termination point). One command: `docker compose up -d --build`.
