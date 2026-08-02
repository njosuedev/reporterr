"""Plain data carriers for a generated report — no ORM, no persistence."""
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class CompanyInfo:
    name: str
    tin: str


@dataclass(frozen=True)
class ReportData:
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
    created_at: datetime
