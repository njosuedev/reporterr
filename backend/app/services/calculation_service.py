"""
VAT calculation engine — pure business logic, no I/O, no ORM/DB access.

Fully unit-testable in isolation (see app/tests/unit/test_calculation_service.py).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class VatCalculationResult:
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


class CalculationService:
    """Isolated VAT calculation engine. No business logic belongs in API routes."""

    def __init__(self, vat_rate: float) -> None:
        if vat_rate <= 0:
            raise ValueError("vat_rate must be a positive number, e.g. 0.18 for 18%")
        self.vat_rate = vat_rate

    def calculate(
        self,
        total_taxable_sales: float,
        output_vat: float,
        total_taxable_purchases: float,
        input_vat: float,
        previous_remaining_refund: float = 0.0,
    ) -> VatCalculationResult:
        # RWF has no subunits in these reports, so round to whole Frw immediately —
        # matching how the figures are rounded by hand — rather than carrying cents
        # through the refund/payable math and only rounding at the end.
        total_taxable_sales = round(total_taxable_sales)
        output_vat = round(output_vat)
        total_taxable_purchases = round(total_taxable_purchases)
        input_vat = round(input_vat)
        previous_remaining_refund = round(previous_remaining_refund)

        vat_difference = output_vat - input_vat

        if vat_difference >= 0:
            vat_payable = vat_difference
            refund = 0.0
        else:
            vat_payable = 0.0
            refund = abs(vat_difference)

        # Current-period refund plus any carried-forward refund not yet absorbed
        # by this period's VAT payable.
        remaining_refund = round(refund + max(previous_remaining_refund - vat_payable, 0.0))

        # A taxpayer with no VAT on sales isn't VAT-registered on the output side,
        # so they cannot claim a refund against input VAT paid on purchases —
        # zero it out regardless of what the raw difference would suggest.
        if output_vat == 0:
            refund = 0.0
            remaining_refund = 0.0

        # Sales needed (VAT-inclusive) to generate enough output VAT to absorb the
        # remaining refund: a taxable base of (remaining_refund / vat_rate) produces
        # that much VAT, and the gross/invoice sales total is base + VAT, i.e.
        # base * (1 + vat_rate) — e.g. remaining_refund * 118/18 at an 18% rate.
        required_sales_to_clear_refund = (
            round(remaining_refund * (1 + self.vat_rate) / self.vat_rate) if remaining_refund > 0 else 0.0
        )

        # Purchases needed (VAT-inclusive) to generate enough input VAT to offset
        # the VAT payable, using the same base-to-gross conversion as above.
        required_purchases_to_clear_vat_payable = (
            round(vat_payable * (1 + self.vat_rate) / self.vat_rate) if vat_payable > 0 else 0.0
        )

        return VatCalculationResult(
            total_taxable_sales=total_taxable_sales,
            output_vat=output_vat,
            total_taxable_purchases=total_taxable_purchases,
            input_vat=input_vat,
            vat_difference=vat_difference,
            vat_payable=vat_payable,
            refund=refund,
            remaining_refund=remaining_refund,
            required_sales_to_clear_refund=required_sales_to_clear_refund,
            required_purchases_to_clear_vat_payable=required_purchases_to_clear_vat_payable,
        )
