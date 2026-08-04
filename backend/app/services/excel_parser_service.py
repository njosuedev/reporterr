"""
Parses Rwanda EBM Sales/Purchase Excel exports.

Design goals (per spec): no hardcoded column *positions* — everything is resolved by
matching column *names* against alias dictionaries, so the parser tolerates EBM
template changes (renamed/reordered columns) as long as the semantic header text
is still recognizable. Company identity (name/TIN) and the reporting period are
read from free-form header rows above the data table, since in EBM exports those
live in a metadata block, not in the tabular columns.
"""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from typing import Any

import pandas as pd

from app.core.exceptions import FileProcessingError

# ── Column alias dictionaries (all lowercase, normalized) ───────────────────
_COLUMN_ALIASES: dict[str, list[str]] = {
    "invoice_number": [
        "invoice no", "invoice number", "invoice num", "receipt no", "receipt number",
        "sdc receipt number", "sdc receipt no", "invoice_no", "inv no", "document no", "no",
    ],
    "invoice_date": [
        "date", "invoice date", "sale date", "purchase date", "issue date",
        "transaction date", "receipt date", "sdc date",
    ],
    "party_name": [
        "customer name", "buyer name", "client name", "supplier name", "seller name",
        "vendor name", "name", "customer", "supplier",
    ],
    "party_tin": [
        "customer tin", "buyer tin", "client tin", "supplier tin", "seller tin",
        "vendor tin", "tin",
    ],
    "taxable_amount": [
        "taxable amount", "taxable value", "taxable amt", "tax base", "taxable",
        "amount excl vat", "amount excl. vat", "net amount", "amount before vat", "base amount",
    ],
    "vat_amount": [
        "vat amount", "vat amt", "vat", "tax amount", "tax amt", "value added tax",
    ],
    "total_amount": [
        "total amount", "gross amount", "total", "amount incl vat", "amount incl. vat",
        "total incl tax", "total incl. vat", "invoice total", "grand total",
    ],
    "exempted_amount": [
        "exempted sales amount", "exempted amount", "exempted sales", "amount exempted",
        "vat exempted amount", "exempted",
    ],
}

_MANDATORY_FIELDS = ("taxable_amount", "vat_amount")

# Real RRA EBM exports use headers like "Total Amount of Sales (VAT Exclusive)" or
# "Amount without VAT" for the taxable base, and "Amount incl. VAT" for the gross
# total. These all contain the literal substring "vat", which would otherwise make
# them collide with the vat_amount alias "vat" and get misclassified as the VAT
# column itself. Resolve these qualified phrases before falling back to generic
# alias/substring matching.
_VAT_EXCLUSIVE_HINTS = ("exclusive", "excl", "without", "before", "net of")
_VAT_INCLUSIVE_HINTS = ("inclusive", "incl", "with vat")


def _special_field_override(normalized_cell: str) -> str | None:
    if "vat" not in normalized_cell.split():
        return None
    if any(hint in normalized_cell for hint in _VAT_EXCLUSIVE_HINTS):
        return "taxable_amount"
    if any(hint in normalized_cell for hint in _VAT_INCLUSIVE_HINTS):
        return "total_amount"
    return None

_TIN_PATTERN = re.compile(r"\b\d{9}\b")
_HEADER_SCAN_ROWS = 30
_LABEL_HINTS = {
    "company_name": ["company name", "taxpayer name", "business name", "trader name"],
    "tin": ["tin", "taxpayer identification"],
    "period": ["period", "from", "to", "reporting period", "start date", "end date"],
}


@dataclass
class ParsedRow:
    invoice_number: str | None
    invoice_date: date | None
    party_name: str | None
    party_tin: str | None
    taxable_amount: float
    vat_amount: float
    total_amount: float
    exempted_amount: float
    raw_row: dict[str, Any]


@dataclass
class ParsedUpload:
    company_name: str | None
    tin: str | None
    period_start: date | None
    period_end: date | None
    rows: list[ParsedRow] = field(default_factory=list)
    file_hash: str = ""

    @property
    def total_taxable_amount(self) -> float:
        return sum(r.taxable_amount for r in self.rows)

    @property
    def total_vat_amount(self) -> float:
        return sum(r.vat_amount for r in self.rows)

    @property
    def total_exempted_amount(self) -> float:
        return sum(r.exempted_amount for r in self.rows)

    @property
    def total_reported_taxable_amount(self) -> float:
        """VAT-inclusive taxable total, excluding exempted sales/purchases —
        the figure used in the client-facing report (net taxable + VAT)."""
        return self.total_taxable_amount - self.total_exempted_amount + self.total_vat_amount


def _normalize(text: Any) -> str:
    if text is None:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[^a-z0-9%.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _match_score(header_cell: str, aliases: list[str]) -> int:
    """Higher is better; 0 = no match."""
    normalized = _normalize(header_cell)
    if not normalized:
        return 0
    for alias in aliases:
        if normalized == alias:
            return 100
    for alias in aliases:
        if alias in normalized or normalized in alias:
            return 50
    return 0


class ExcelParserService:
    """Stateless service — safe to instantiate per-request or as a singleton."""

    def parse(self, raw_bytes: bytes) -> ParsedUpload:
        if not raw_bytes:
            raise FileProcessingError("The uploaded file is empty.")

        try:
            raw_df = pd.read_excel(BytesIO(raw_bytes), header=None, engine=None)
        except Exception as exc:
            raise FileProcessingError(
                "This file could not be read as an Excel workbook. It may be corrupted "
                "or in an unsupported format. Please re-export it from EBM and try again."
            ) from exc

        if raw_df.empty:
            raise FileProcessingError("The uploaded file has no data.")

        header_row_idx, column_map = self._locate_header_and_columns(raw_df)

        missing = [f for f in _MANDATORY_FIELDS if f not in column_map]
        if missing:
            friendly = {"taxable_amount": "Taxable Amount", "vat_amount": "VAT Amount"}
            missing_names = ", ".join(friendly.get(m, m) for m in missing)
            raise FileProcessingError(
                f"Could not find required column(s) in the file: {missing_names}. "
                "Please make sure you exported the correct EBM report."
            )

        company_name, tin = self._extract_company_info(raw_df, header_row_idx)

        data_df = raw_df.iloc[header_row_idx + 1 :].reset_index(drop=True)
        data_df = data_df.dropna(how="all")

        rows = self._build_rows(data_df, column_map)
        if not rows:
            raise FileProcessingError(
                "No transaction rows were found below the header. The file may be empty "
                "or use an unrecognized layout."
            )

        period_start, period_end = self._detect_period(raw_df, header_row_idx, rows)

        return ParsedUpload(
            company_name=company_name,
            tin=tin,
            period_start=period_start,
            period_end=period_end,
            rows=rows,
            file_hash=hashlib.sha256(raw_bytes).hexdigest(),
        )

    # ── internals ────────────────────────────────────────────────────────

    def _locate_header_and_columns(self, raw_df: pd.DataFrame) -> tuple[int, dict[str, int]]:
        best_row_idx = -1
        best_score = 0
        best_map: dict[str, int] = {}

        scan_limit = min(_HEADER_SCAN_ROWS, len(raw_df))
        for row_idx in range(scan_limit):
            row_values = raw_df.iloc[row_idx].tolist()
            column_map: dict[str, int] = {}
            score = 0
            for col_idx, cell in enumerate(row_values):
                override_field = _special_field_override(_normalize(cell))
                if override_field and override_field not in column_map:
                    column_map[override_field] = col_idx
                    score += 90
                    continue

                best_field, best_field_score = None, 0
                for field_name, aliases in _COLUMN_ALIASES.items():
                    if field_name in column_map:
                        continue
                    s = _match_score(cell, aliases)
                    if s > best_field_score:
                        best_field, best_field_score = field_name, s
                if best_field and best_field_score > 0:
                    column_map[best_field] = col_idx
                    score += best_field_score

            has_mandatory = all(f in column_map for f in _MANDATORY_FIELDS)
            if has_mandatory and score > best_score:
                best_score = score
                best_row_idx = row_idx
                best_map = column_map

        if best_row_idx == -1:
            raise FileProcessingError(
                "Could not detect a valid header row with recognizable columns "
                "(Taxable Amount, VAT Amount, etc.) in the first "
                f"{scan_limit} rows of the file."
            )

        return best_row_idx, best_map

    def _extract_company_info(self, raw_df: pd.DataFrame, header_row_idx: int) -> tuple[str | None, str | None]:
        company_name: str | None = None
        tin: str | None = None

        search_rows = raw_df.iloc[: max(header_row_idx, 1)]
        for row in search_rows.itertuples(index=False):
            cells = [c for c in row if pd.notna(c)]
            for i, cell in enumerate(cells):
                normalized = _normalize(cell)

                if tin is None:
                    tin_match = _TIN_PATTERN.search(str(cell))
                    if tin_match and any(hint in normalized for hint in _LABEL_HINTS["tin"]):
                        tin = tin_match.group(0)
                    elif tin_match and normalized == tin_match.group(0):
                        # standalone TIN value with a label in the preceding cell
                        if i > 0 and any(h in _normalize(cells[i - 1]) for h in _LABEL_HINTS["tin"]):
                            tin = tin_match.group(0)

                if company_name is None and any(hint in normalized for hint in _LABEL_HINTS["company_name"]):
                    if i + 1 < len(cells) and pd.notna(cells[i + 1]):
                        candidate = str(cells[i + 1]).strip()
                        if candidate and not _TIN_PATTERN.fullmatch(candidate):
                            company_name = candidate
                    else:
                        # "Company Name: Acme Ltd" in a single cell
                        parts = re.split(r"[:\-]", str(cell), maxsplit=1)
                        if len(parts) == 2 and parts[1].strip():
                            company_name = parts[1].strip()

        return company_name, tin

    def _build_rows(self, data_df: pd.DataFrame, column_map: dict[str, int]) -> list[ParsedRow]:
        rows: list[ParsedRow] = []
        for _, row in data_df.iterrows():
            values = row.tolist()

            def get(field_name: str) -> Any:
                idx = column_map.get(field_name)
                if idx is None or idx >= len(values):
                    return None
                v = values[idx]
                return None if pd.isna(v) else v

            taxable_raw = get("taxable_amount")
            vat_raw = get("vat_amount")

            # skip rows that are entirely blank in the amount columns (e.g. spacer/footer rows)
            if taxable_raw is None and vat_raw is None:
                continue

            taxable_amount = self._to_float(taxable_raw)
            vat_amount = self._to_float(vat_raw)
            total_raw = get("total_amount")
            total_amount = self._to_float(total_raw) if total_raw is not None else round(taxable_amount + vat_amount, 2)
            exempted_amount = self._to_float(get("exempted_amount"))

            invoice_date_raw = get("invoice_date")
            invoice_date = self._to_date(invoice_date_raw)

            party_tin_raw = get("party_tin")
            party_tin = str(int(party_tin_raw)) if isinstance(party_tin_raw, float) and not pd.isna(party_tin_raw) else (
                str(party_tin_raw).strip() if party_tin_raw is not None else None
            )

            rows.append(
                ParsedRow(
                    invoice_number=str(get("invoice_number")).strip() if get("invoice_number") is not None else None,
                    invoice_date=invoice_date,
                    party_name=str(get("party_name")).strip() if get("party_name") is not None else None,
                    party_tin=party_tin,
                    taxable_amount=taxable_amount,
                    vat_amount=vat_amount,
                    total_amount=total_amount,
                    exempted_amount=exempted_amount,
                    raw_row={str(k): (None if pd.isna(v) else str(v)) for k, v in zip(data_df.columns, values)},
                )
            )
        return rows

    def _detect_period(
        self, raw_df: pd.DataFrame, header_row_idx: int, rows: list[ParsedRow]
    ) -> tuple[date | None, date | None]:
        dates_from_header: list[date] = []
        search_rows = raw_df.iloc[: max(header_row_idx, 1)]
        for row in search_rows.itertuples(index=False):
            for cell in row:
                if pd.isna(cell):
                    continue
                parsed = self._to_date(cell)
                if parsed:
                    dates_from_header.append(parsed)

        if dates_from_header:
            return min(dates_from_header), max(dates_from_header)

        row_dates = [r.invoice_date for r in rows if r.invoice_date is not None]
        if row_dates:
            return min(row_dates), max(row_dates)

        return None, None

    @staticmethod
    def _to_float(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        cleaned = re.sub(r"[^\d.\-]", "", str(value))
        if not cleaned or cleaned in {"-", "."}:
            return 0.0
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return 0.0

    @staticmethod
    def _to_date(value: Any) -> date | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            ts = pd.to_datetime(value, dayfirst=True, errors="coerce")
        except Exception:
            return None
        if pd.isna(ts):
            return None
        return ts.date()
