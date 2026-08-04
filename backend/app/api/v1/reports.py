"""Single stateless endpoint: upload a Sales + Purchase EBM export, pick a period, get a
VAT report back (figures + WhatsApp text + PDF). Nothing is persisted anywhere."""
import base64
from datetime import date, datetime

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.core.config import settings
from app.core.exceptions import FileProcessingError, ValidationFailedError
from app.core.rate_limit import limiter
from app.schemas.report import GenerateReportResponse, MissingReceiptGroup
from app.services.calculation_service import CalculationService
from app.services.excel_parser_service import ExcelParserService
from app.services.pdf_service import PdfService
from app.services.receipt_gap_service import ReceiptGapService
from app.services.report_text_service import ReportTextService
from app.services.report_types import CompanyInfo, ReportData

router = APIRouter(prefix="/reports", tags=["Reports"])

_parser = ExcelParserService()
_pdf_service = PdfService()
_text_service = ReportTextService()
_receipt_gap_service = ReceiptGapService()


def _validate_extension(filename: str | None) -> None:
    name = (filename or "").lower()
    if not name.endswith(settings.ALLOWED_UPLOAD_EXTENSIONS):
        raise FileProcessingError(
            f"Unsupported file type. Please upload one of: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}"
        )


async def _read_upload(file: UploadFile, label: str) -> bytes:
    _validate_extension(file.filename)
    contents = await file.read()
    if len(contents) > settings.max_upload_size_bytes:
        raise FileProcessingError(f"The {label} file exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit.")
    return contents


@router.post("/generate", response_model=GenerateReportResponse)
@limiter.limit(settings.RATE_LIMIT_GENERATE)
async def generate_report(
    request: Request,
    company_name: str = Form(...),
    tin: str = Form(...),
    period_start: date = Form(...),
    period_end: date = Form(...),
    previous_remaining_refund: float = Form(0.0, ge=0),
    sales_file: UploadFile = File(...),
    purchase_file: UploadFile = File(...),
) -> GenerateReportResponse:
    if not company_name.strip():
        raise ValidationFailedError("Business name is required")
    if not tin.strip().isdigit() or len(tin.strip()) != 9:
        raise ValidationFailedError("TIN must be exactly 9 digits")
    if period_end < period_start:
        raise ValidationFailedError("Period end date must be on or after the period start date")

    sales_bytes = await _read_upload(sales_file, "Sales")
    purchase_bytes = await _read_upload(purchase_file, "Purchase")

    sales_parsed = _parser.parse(sales_bytes)
    purchase_parsed = _parser.parse(purchase_bytes)

    calculator = CalculationService(vat_rate=settings.VAT_RATE)
    result = calculator.calculate(
        # Reported taxable totals are VAT-inclusive and exclude exempted sales/purchases:
        # (net taxable - exempted) + VAT. Matches the client-facing report format on both sides.
        total_taxable_sales=sales_parsed.total_reported_taxable_amount,
        output_vat=sales_parsed.total_vat_amount,
        total_taxable_purchases=purchase_parsed.total_reported_taxable_amount,
        input_vat=purchase_parsed.total_vat_amount,
        previous_remaining_refund=previous_remaining_refund,
    )

    company = CompanyInfo(name=company_name.strip(), tin=tin.strip())
    report = ReportData(
        period_start=period_start,
        period_end=period_end,
        total_taxable_sales=result.total_taxable_sales,
        output_vat=result.output_vat,
        total_taxable_purchases=result.total_taxable_purchases,
        input_vat=result.input_vat,
        vat_difference=result.vat_difference,
        vat_payable=result.vat_payable,
        refund=result.refund,
        remaining_refund=result.remaining_refund,
        required_sales_to_clear_refund=result.required_sales_to_clear_refund,
        required_purchases_to_clear_vat_payable=result.required_purchases_to_clear_vat_payable,
        created_at=datetime.now(),
    )

    whatsapp_text = _text_service.build(report, company)
    pdf_bytes = _pdf_service.generate(report, company)

    receipt_gap_groups = _receipt_gap_service.find_missing([r.invoice_number for r in sales_parsed.rows])
    missing_sales_receipts = [
        MissingReceiptGroup(
            prefix=g.prefix,
            lowest=g.lowest,
            highest=g.highest,
            present_count=g.present_count,
            missing_count=g.missing_count,
            missing_receipts=g.missing_receipt_numbers,
        )
        for g in receipt_gap_groups
    ]

    return GenerateReportResponse(
        company_name=company.name,
        tin=company.tin,
        period_start=report.period_start,
        period_end=report.period_end,
        total_taxable_sales=report.total_taxable_sales,
        output_vat=report.output_vat,
        total_taxable_purchases=report.total_taxable_purchases,
        input_vat=report.input_vat,
        vat_difference=report.vat_difference,
        vat_payable=report.vat_payable,
        refund=report.refund,
        remaining_refund=report.remaining_refund,
        required_sales_to_clear_refund=report.required_sales_to_clear_refund,
        required_purchases_to_clear_vat_payable=report.required_purchases_to_clear_vat_payable,
        missing_sales_receipts=missing_sales_receipts,
        whatsapp_text=whatsapp_text,
        pdf_base64=base64.b64encode(pdf_bytes).decode("ascii"),
    )
