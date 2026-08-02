import pytest

from app.services.calculation_service import CalculationService


@pytest.fixture
def calc() -> CalculationService:
    return CalculationService(vat_rate=0.18)


def test_vat_payable_when_output_exceeds_input(calc: CalculationService) -> None:
    result = calc.calculate(
        total_taxable_sales=1_000_000,
        output_vat=180_000,
        total_taxable_purchases=400_000,
        input_vat=72_000,
    )
    assert result.vat_difference == 108_000
    assert result.vat_payable == 108_000
    assert result.refund == 0
    assert result.remaining_refund == 0
    assert result.required_sales_to_clear_refund == 0
    # 108,000 * 118/18 = 708,000 (VAT-inclusive purchases needed to offset the payable)
    assert result.required_purchases_to_clear_vat_payable == pytest.approx(708_000, abs=0.01)


def test_refund_when_input_exceeds_output(calc: CalculationService) -> None:
    result = calc.calculate(
        total_taxable_sales=200_000,
        output_vat=36_000,
        total_taxable_purchases=900_000,
        input_vat=162_000,
    )
    assert result.vat_difference == -126_000
    assert result.vat_payable == 0
    assert result.refund == 126_000
    assert result.remaining_refund == 126_000
    # 126,000 * 118/18 = 826,000 (VAT-inclusive sales needed to absorb the refund)
    assert result.required_sales_to_clear_refund == pytest.approx(826_000, abs=0.01)
    assert result.required_purchases_to_clear_vat_payable == 0


def test_exact_break_even(calc: CalculationService) -> None:
    result = calc.calculate(
        total_taxable_sales=500_000,
        output_vat=90_000,
        total_taxable_purchases=500_000,
        input_vat=90_000,
    )
    assert result.vat_difference == 0
    assert result.vat_payable == 0
    assert result.refund == 0
    assert result.remaining_refund == 0


def test_carried_forward_refund_partially_absorbed(calc: CalculationService) -> None:
    result = calc.calculate(
        total_taxable_sales=1_000_000,
        output_vat=180_000,
        total_taxable_purchases=400_000,
        input_vat=72_000,
        previous_remaining_refund=50_000,
    )
    # this period is in a payable position (108,000), which fully absorbs the
    # 50,000 carried-forward refund
    assert result.vat_payable == 108_000
    assert result.refund == 0
    assert result.remaining_refund == 0


def test_carried_forward_refund_not_absorbed_when_still_in_refund(calc: CalculationService) -> None:
    result = calc.calculate(
        total_taxable_sales=100_000,
        output_vat=18_000,
        total_taxable_purchases=200_000,
        input_vat=36_000,
        previous_remaining_refund=10_000,
    )
    assert result.vat_payable == 0
    assert result.refund == 18_000
    assert result.remaining_refund == 28_000  # 18,000 new + 10,000 carried forward


def test_no_refund_when_no_output_vat(calc: CalculationService) -> None:
    """Non-VAT-registered sales side (VAT on sales = 0): no refund can be claimed
    against input VAT paid on purchases, even though the raw difference is negative."""
    result = calc.calculate(
        total_taxable_sales=1_788_620,
        output_vat=0,
        total_taxable_purchases=7_410_050,
        input_vat=1_116_389,
    )
    assert result.vat_difference == -1_116_389
    assert result.vat_payable == 0
    assert result.refund == 0
    assert result.remaining_refund == 0
    assert result.required_sales_to_clear_refund == 0


def test_no_refund_when_no_output_vat_even_with_carried_forward_refund(calc: CalculationService) -> None:
    result = calc.calculate(
        total_taxable_sales=100_000,
        output_vat=0,
        total_taxable_purchases=200_000,
        input_vat=36_000,
        previous_remaining_refund=10_000,
    )
    assert result.refund == 0
    assert result.remaining_refund == 0
    assert result.required_sales_to_clear_refund == 0


def test_invalid_vat_rate_raises() -> None:
    with pytest.raises(ValueError):
        CalculationService(vat_rate=0)
