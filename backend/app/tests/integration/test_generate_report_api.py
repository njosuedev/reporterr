import base64
from io import BytesIO

import openpyxl
import pytest
from httpx import AsyncClient

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _build_workbook_bytes(rows: list[tuple[str, str, float]], *, include_vat_column: bool = True) -> bytes:
    """rows: list of (invoice_no, date, taxable_amount)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Company Name:", "Test Traders Ltd", "", "", ""])
    ws.append(["TIN:", "123456789", "", "", ""])

    header = ["Invoice No", "Date", "Taxable Amount"]
    if include_vat_column:
        header.append("VAT Amount")
    ws.append(header)

    for invoice_no, invoice_date, taxable in rows:
        row = [invoice_no, invoice_date, taxable]
        if include_vat_column:
            row.append(round(taxable * 0.18, 2))
        ws.append(row)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _sales_bytes() -> bytes:
    return _build_workbook_bytes(
        [
            ("INV-001", "05/01/2026", 100_000),
            ("INV-002", "12/01/2026", 250_000),
            ("INV-003", "20/01/2026", 50_000),
        ]
    )


def _purchase_bytes() -> bytes:
    return _build_workbook_bytes(
        [
            ("PUR-001", "03/01/2026", 150_000),
            ("PUR-002", "18/01/2026", 150_000),
        ]
    )


def _form_data(**overrides: str) -> dict[str, str]:
    data = {
        "company_name": "Test Traders Ltd",
        "tin": "123456789",
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "previous_remaining_refund": "0",
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_generate_report_returns_calculated_figures_pdf_and_text(client: AsyncClient) -> None:
    response = await client.post(
        "/api/reports/generate",
        data=_form_data(),
        files={
            "sales_file": ("sales.xlsx", _sales_bytes(), _XLSX_CONTENT_TYPE),
            "purchase_file": ("purchase.xlsx", _purchase_bytes(), _XLSX_CONTENT_TYPE),
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["company_name"] == "Test Traders Ltd"
    assert body["tin"] == "123456789"
    assert body["period_start"] == "2026-01-01"
    assert body["period_end"] == "2026-01-31"
    assert body["total_taxable_sales"] == pytest.approx(472_000, abs=0.01)
    assert body["output_vat"] == pytest.approx(72_000, abs=0.01)
    assert body["total_taxable_purchases"] == pytest.approx(354_000, abs=0.01)
    assert body["input_vat"] == pytest.approx(54_000, abs=0.01)
    assert body["vat_difference"] == pytest.approx(18_000, abs=0.01)
    assert body["vat_payable"] == pytest.approx(18_000, abs=0.01)
    assert body["refund"] == pytest.approx(0, abs=0.01)

    assert "Test Traders Ltd" in body["whatsapp_text"]
    # "INV-00x" invoice numbers don't match the SDC "prefix/sequence" pattern
    assert body["missing_sales_receipts"] == []

    pdf_bytes = base64.b64decode(body["pdf_base64"])
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_generate_report_flags_missing_sdc_receipt_numbers(client: AsyncClient) -> None:
    sales_bytes = _build_workbook_bytes(
        [
            ("SDC010193518/10", "05/01/2026", 100_000),
            ("SDC010193518/11", "12/01/2026", 250_000),
            ("SDC010193518/13", "20/01/2026", 50_000),
        ]
    )
    response = await client.post(
        "/api/reports/generate",
        data=_form_data(),
        files={
            "sales_file": ("sales.xlsx", sales_bytes, _XLSX_CONTENT_TYPE),
            "purchase_file": ("purchase.xlsx", _purchase_bytes(), _XLSX_CONTENT_TYPE),
        },
    )

    assert response.status_code == 200
    body = response.json()
    groups = body["missing_sales_receipts"]
    assert len(groups) == 1
    assert groups[0]["prefix"] == "SDC010193518"
    assert groups[0]["missing_receipts"] == ["SDC010193518/12"]
    assert groups[0]["missing_count"] == 1


@pytest.mark.asyncio
async def test_rejects_wrong_file_extension(client: AsyncClient) -> None:
    response = await client.post(
        "/api/reports/generate",
        data=_form_data(),
        files={
            "sales_file": ("sales.txt", b"not an excel file", "text/plain"),
            "purchase_file": ("purchase.xlsx", _purchase_bytes(), _XLSX_CONTENT_TYPE),
        },
    )

    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rejects_file_missing_required_column(client: AsyncClient) -> None:
    response = await client.post(
        "/api/reports/generate",
        data=_form_data(),
        files={
            "sales_file": (
                "sales.xlsx",
                _build_workbook_bytes([("INV-001", "05/01/2026", 100_000)], include_vat_column=False),
                _XLSX_CONTENT_TYPE,
            ),
            "purchase_file": ("purchase.xlsx", _purchase_bytes(), _XLSX_CONTENT_TYPE),
        },
    )

    assert response.status_code == 422
    assert "VAT Amount" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rejects_period_end_before_period_start(client: AsyncClient) -> None:
    response = await client.post(
        "/api/reports/generate",
        data=_form_data(period_start="2026-01-31", period_end="2026-01-01"),
        files={
            "sales_file": ("sales.xlsx", _sales_bytes(), _XLSX_CONTENT_TYPE),
            "purchase_file": ("purchase.xlsx", _purchase_bytes(), _XLSX_CONTENT_TYPE),
        },
    )

    assert response.status_code == 422
    assert "Period end date" in response.json()["detail"]
