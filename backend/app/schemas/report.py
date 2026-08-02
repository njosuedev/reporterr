from datetime import date

from pydantic import BaseModel


class MissingReceiptGroup(BaseModel):
    prefix: str
    lowest: int
    highest: int
    present_count: int
    missing_count: int
    missing_receipts: list[str]


class GenerateReportResponse(BaseModel):
    company_name: str
    tin: str
    period_start: date
    period_end: date
    total_taxable_sales: float
    output_vat: float
    total_taxable_purchases: float
    input_vat: float
    vat_difference: float
    vat_payable: float
    refund: float
    remaining_refund: float
    required_sales_to_clear_refund: float
    required_purchases_to_clear_vat_payable: float
    missing_sales_receipts: list[MissingReceiptGroup]
    whatsapp_text: str
    pdf_base64: str
