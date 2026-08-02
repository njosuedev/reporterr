# VAT Report Analyzer Rwanda — Architecture

## 1. Overview

A stateless request/response tool: the client uploads two EBM (Electronic Billing
Machine) Excel exports — Sales and Purchase — along with business details and a
reporting period, and receives back a computed VAT position, a Kinyarwanda WhatsApp-style
summary, and a branded PDF, all in one JSON response. There is no database, no user
accounts, and no persisted files — everything is computed in memory for the duration of
the request and discarded afterward.

## 2. High-level architecture

```
                ┌──────────┐        POST /api/reports/generate       ┌─────────────┐
                │ Next.js  │ ───────────────────────────────────────▶│   FastAPI    │
                │(frontend)│◀─────────────────────────────────────── │  (backend)   │
                └──────────┘   { figures, whatsapp_text, pdf_base64 } └─────────────┘
```

Nginx sits in front as a reverse proxy in the (currently incomplete — see the root
README's Docker Compose notes) container deployment; in local development the frontend
talks to the backend directly over `NEXT_PUBLIC_API_URL`.

Backend request flow, all synchronous and in-memory:

```
UploadFile (Sales) ──┐
                      ├─▶ ExcelParserService.parse() ──▶ ParsedUpload (rows + totals)
UploadFile (Purchase)─┘
                              │
                              ▼
                    CalculationService.calculate() ──▶ VatCalculationResult
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
     ReportTextService  PdfService      ReceiptGapService
     (WhatsApp text)    (PDF bytes)     (missing receipt groups,
                                          from Sales invoice numbers)
              │               │                │
              └───────────────┴────────────────┘
                              ▼
                   GenerateReportResponse (JSON)
```

`app/api/v1/reports.py` is a thin controller: it validates the form fields, calls the
services in sequence, and assembles the response. All business logic lives in
`app/services/`, each service pure and independently unit-tested (`app/tests/unit/`).

## 3. Tech stack rationale

- **FastAPI + Pydantic v2**: async-first, native OpenAPI docs (`/api/docs`), strong typing
  on the one response schema (`app/schemas/report.py`).
- **Pandas + openpyxl**: column-name-based Excel parsing (`ExcelParserService`) that
  tolerates EBM template drift — columns are matched against alias dictionaries and
  qualifier hints (e.g. "excl VAT" vs "incl VAT"), never by fixed position.
- **reportlab** for PDF generation: pure-Python, no external binary/system dependency
  (chosen over WeasyPrint to avoid GTK/Cairo deps in the Docker image), and writes
  straight into an in-memory buffer — nothing touches disk.
- **slowapi**: simple in-memory, per-process rate limiting on the one generation
  endpoint — adequate for a single-instance deployment with no shared cache.
- **Next.js 15 (App Router) + shadcn/ui + TanStack Query**: the whole app is one form + one
  results view (`frontend/app/page.tsx`); React Query manages the mutation's
  loading/error state, Zod (`frontend/lib/validation.ts`) mirrors the backend's input
  validation client-side.
- **No database, no auth**: the product deliberately has no accounts or history — every
  report is generated fresh from the two files supplied in that request.

## 4. Excel parsing strategy

`ExcelParserService` (`app/services/excel_parser_service.py`) reads the workbook with no
assumptions about a fixed header row or column order:

1. Scans the first 30 rows for the one that best matches known column-name aliases for
   `invoice_number`, `invoice_date`, `party_name`, `party_tin`, `taxable_amount`,
   `vat_amount`, and `total_amount`. `taxable_amount` and `vat_amount` are mandatory; a
   file missing either raises a `FileProcessingError` with a user-facing message.
2. Because real RRA EBM headers like "Total Amount of Sales (VAT Exclusive)" or "Amount
   incl. VAT" both contain the substring "vat", qualifier hints (`exclusive`/`excl`/
   `without`/`before` vs `inclusive`/`incl`) are checked before generic alias matching so
   these aren't misclassified as the VAT column itself.
3. Company name and TIN are pulled from the free-form metadata rows above the detected
   header (label/value pairs or "Label: Value" cells), since EBM exports put them there
   rather than in the tabular columns. Reporting period is inferred from dates in that
   same metadata block, falling back to the min/max invoice date in the data if absent.
4. Data rows below the header are parsed with tolerant numeric/date coercion; rows blank
   in both amount columns (spacer/footer rows) are skipped.

## 5. VAT calculation formulas

Implemented in `CalculationService` (`app/services/calculation_service.py`), pure
function, no I/O:

```
total_taxable_sales      = Σ sales.taxable_amount
output_vat               = Σ sales.vat_amount
total_taxable_purchases  = Σ purchases.taxable_amount
input_vat                = Σ purchases.vat_amount

vat_difference = output_vat - input_vat

if vat_difference >= 0:
    vat_payable = vat_difference
    refund      = 0
else:
    vat_payable = 0
    refund      = abs(vat_difference)

# Refund carried forward from a prior period is absorbed by this period's
# VAT payable before being added to this period's own refund:
remaining_refund = refund + max(previous_remaining_refund - vat_payable, 0)

# A business with zero output VAT isn't VAT-registered on the sales side and
# so cannot claim a refund against input VAT paid on purchases:
if output_vat == 0:
    refund = 0
    remaining_refund = 0

# Additional (VAT-inclusive) sales whose output VAT would exactly clear the
# remaining refund, at the standard rate (e.g. 18%):
required_sales_to_clear_refund = remaining_refund * (1 + VAT_RATE) / VAT_RATE   if remaining_refund > 0 else 0

# Additional (VAT-inclusive) purchases whose input VAT would exactly offset
# the VAT payable:
required_purchases_to_clear_vat_payable = vat_payable * (1 + VAT_RATE) / VAT_RATE   if vat_payable > 0 else 0
```

`VAT_RATE` defaults to `0.18` and is configurable via the `VAT_RATE` environment
variable.

## 6. Missing-receipt detection

`ReceiptGapService` (`app/services/receipt_gap_service.py`) groups Sales invoice numbers
by their SDC device prefix (everything before the final `/<sequence>`, e.g.
`SDC010193518/10`) and reports any sequence numbers missing between the lowest and
highest seen for that prefix — a common indicator of a sale that wasn't recorded through
the EBM device. Results are surfaced in the API response as `missing_sales_receipts` and
flagged in the frontend UI when any group has missing receipts.

## 7. API contract

Full OpenAPI schema is generated at `/api/docs` (Swagger) and `/api/redoc`. Summary:

```
GET  /api/health                       liveness check

POST /api/reports/generate             multipart/form-data:
                                          company_name, tin, period_start, period_end,
                                          previous_remaining_refund (optional),
                                          sales_file, purchase_file
                                        →  VAT figures + missing_sales_receipts +
                                           whatsapp_text + pdf_base64
```

No authentication — the endpoint is public but rate-limited
(`RATE_LIMIT_GENERATE`, default `20/minute` per client IP, via `slowapi`).

## 8. Security

- Pydantic/form validation on every input (9-digit TIN, `period_end >= period_start`,
  non-empty business name).
- Upload validation: extension allow-list (`.xlsx`/`.xls`), size cap (`MAX_UPLOAD_SIZE_MB`,
  default 20 MB) enforced per file before parsing.
- Rate limiting on the generation endpoint via `slowapi`, keyed by remote address.
- Security response headers (`X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `X-XSS-Protection`, plus HSTS outside `development`) applied to every
  response via middleware in `app/main.py`.
- CORS restricted to `BACKEND_CORS_ORIGINS`.
- Domain errors (`app/core/exceptions.py`) are mapped to appropriate HTTP status codes;
  unhandled exceptions are logged (structlog) and returned as a generic 500 without
  leaking internals.
- No file, upload, or generated report is ever written to disk or a database — nothing to
  leak or clean up after the request completes.

## 9. Deployment

Two supported paths, both documented in the root [README](../README.md):

- **Vercel** (current primary path): frontend and backend deploy as two independent
  Vercel projects from this one repo. The backend's statelessness maps directly onto
  Vercel's Python serverless functions — `backend/api/index.py` re-exports the FastAPI
  ASGI `app`, and `backend/vercel.json` rewrites every request path to it so FastAPI's
  own router (not Vercel's file-based routing) resolves `/api/...`. No disk writes happen
  anywhere in the request path, so the read-only serverless filesystem is a non-issue;
  the one real caveat is that `slowapi`'s in-memory rate limiter is per-instance, not
  shared across a function's cold-started copies. See the README's
  [Deploying to Vercel](../README.md#deploying-to-vercel) section for setup steps and
  size/duration caveats.
- **Docker Compose** (alternative, self-hosted): `docker-compose.yml` at the repo root
  defines `backend`, `frontend`, and `nginx` services on one bridge network, with Nginx
  as the single exposed port (80) reverse-proxying to both. **As of this writing, the
  `backend/Dockerfile`, `frontend/Dockerfile`, and `nginx/nginx.conf` it references have
  not been added to the repo**, so `docker compose up` will fail until those are created.
