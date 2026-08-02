from io import BytesIO

import openpyxl
import pytest

from app.core.exceptions import FileProcessingError
from app.services.excel_parser_service import ExcelParserService


def _build_workbook_bytes(*, include_vat_column: bool = True) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active

    ws.append(["Company Name:", "Test Traders Ltd", "", "", "", ""])
    ws.append(["TIN:", "123456789", "", "", "", ""])
    ws.append(["Period", "01/01/2026", "to", "31/01/2026", "", ""])
    ws.append([])

    header = ["Invoice No", "Date", "Customer Name", "Customer TIN", "Taxable Amount"]
    if include_vat_column:
        header.append("VAT Amount")
    header.append("Total Amount")
    ws.append(header)

    rows = [
        ("INV-001", "05/01/2026", "Acme Rwanda Ltd", "987654321", 100_000),
        ("INV-002", "12/01/2026", "Beta Supplies", "112233445", 250_000),
        ("INV-003", "20/01/2026", "Gamma Traders", "556677889", 50_000),
    ]
    for invoice_no, invoice_date, party, party_tin, taxable in rows:
        vat = round(taxable * 0.18, 2)
        row = [invoice_no, invoice_date, party, party_tin, taxable]
        if include_vat_column:
            row.append(vat)
        row.append(taxable + vat if include_vat_column else taxable)
        ws.append(row)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def parser() -> ExcelParserService:
    return ExcelParserService()


def test_parses_company_info_and_rows(parser: ExcelParserService) -> None:
    result = parser.parse(_build_workbook_bytes())

    assert result.company_name == "Test Traders Ltd"
    assert result.tin == "123456789"
    assert len(result.rows) == 3
    assert result.total_taxable_amount == pytest.approx(400_000, abs=0.01)
    assert result.total_vat_amount == pytest.approx(72_000, abs=0.01)


def test_row_fields_are_normalized(parser: ExcelParserService) -> None:
    result = parser.parse(_build_workbook_bytes())
    first = result.rows[0]

    assert first.invoice_number == "INV-001"
    assert first.party_name == "Acme Rwanda Ltd"
    assert first.party_tin == "987654321"
    assert first.taxable_amount == 100_000
    assert first.vat_amount == 18_000


def test_missing_vat_column_raises_friendly_error(parser: ExcelParserService) -> None:
    with pytest.raises(FileProcessingError, match="VAT Amount"):
        parser.parse(_build_workbook_bytes(include_vat_column=False))


def test_corrupted_file_raises_friendly_error(parser: ExcelParserService) -> None:
    with pytest.raises(FileProcessingError):
        parser.parse(b"this is not a real xlsx file")


def test_empty_file_raises_friendly_error(parser: ExcelParserService) -> None:
    with pytest.raises(FileProcessingError, match="empty"):
        parser.parse(b"")


def _build_rra_style_workbook_bytes() -> bytes:
    """Mirrors real RRA EBM export headers, where both the taxable-base and the
    VAT columns contain the literal word "VAT" (e.g. "Total Amount of Sales
    (VAT Exclusive)"), which previously caused the parser to swap them."""
    wb = openpyxl.Workbook()
    ws = wb.active

    ws.append(
        [
            "Buyer TIN", "Buyer Name", "Nature of Goods", "Receipt Number", "Invoice Date",
            "Total Amount of Sales (VAT Exclusive)", "Exempted Sales Amount",
            "Zero rated Sales Amount", "Exports Amount", "Taxble Sales", "VAT",
        ]
    )
    rows = [
        ("788730222", None, "SDC010186277/1000", "06/07/2026", 519_152.54, 93_447.46),
        ("129985843", "LIGHT GROUP Ltd", "SDC010186277/1004", "06/07/2026", 1_105_932.20, 199_067.80),
    ]
    for tin, name, receipt, invoice_date, taxable, vat in rows:
        ws.append([tin, name, "DIFFERENT GOODS", receipt, invoice_date, taxable, 0, 0, None, taxable + vat, vat])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_rra_vat_exclusive_header_is_not_mistaken_for_vat_column(parser: ExcelParserService) -> None:
    result = parser.parse(_build_rra_style_workbook_bytes())

    assert result.total_taxable_amount == pytest.approx(519_152.54 + 1_105_932.20, abs=0.01)
    assert result.total_vat_amount == pytest.approx(93_447.46 + 199_067.80, abs=0.01)
