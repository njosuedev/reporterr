from datetime import date, datetime

from app.services.report_text_service import ReportTextService
from app.services.report_types import CompanyInfo, ReportData


def _report(**overrides) -> ReportData:
    defaults = dict(
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        total_taxable_sales=185_823_737.31,
        output_vat=33_448_272.69,
        total_taxable_purchases=209_793_822.05,
        input_vat=37_762_887.95,
        vat_difference=-4_314_615.26,
        vat_payable=0.0,
        refund=4_314_615.26,
        remaining_refund=4_314_615.26,
        required_sales_to_clear_refund=28_284_700.04,
        required_purchases_to_clear_vat_payable=0.0,
        created_at=datetime(2026, 8, 2, 19, 0, 0),
    )
    defaults.update(overrides)
    return ReportData(**defaults)


def test_refund_case_matches_expected_kinyarwanda_format() -> None:
    company = CompanyInfo(name="JOSELYNE", tin="121302342")
    text = ReportTextService().build(_report(), company)

    assert "Mwiriwe neza!  JOSELYNE (121302342)," in text
    assert "Report yuko muhagaze kuva 01/07/2026  kujyeza 31/07/2026" in text
    assert "biri taxable bingana =  185,823,737 Frw" in text
    assert "Bifite Vat =  33,448,273 frw" in text
    assert "biri taxable =  209,793,822 frw" in text
    assert "Na VAT = 37,762,888 Frw" in text
    assert "turabona muri muri refund ingana na 4,314,615 frw" in text
    assert "mwacuruza amafaranga angana na 28,284,700 frw" in text
    assert text.strip().endswith("Murakoze mugire umugoroba mwiza!")


def test_vat_payable_case_has_no_refund_wording() -> None:
    company = CompanyInfo(name="JOSELYNE", tin="121302342")
    report = _report(
        output_vat=50_000_000,
        input_vat=10_000_000,
        vat_difference=40_000_000,
        vat_payable=40_000_000,
        refund=0.0,
        remaining_refund=0.0,
        required_sales_to_clear_refund=0.0,
        required_purchases_to_clear_vat_payable=262_222_222.22,
    )
    text = ReportTextService().build(report, company)

    assert "muri mumusoro wangana na 40,000,000 frw" in text
    assert "uyu musoro uvemo mwaranguza amafaranga angana na 262,222,222 frw" in text
    assert "refund" not in text.lower()


def test_vat_payable_case_matches_reference_kinyarwanda_format() -> None:
    """Pinned to a real accountant-shared example (VAT-payable position, morning)."""
    company = CompanyInfo(name="TWAGIRA-HOMELAND Ltd", tin="120910947")
    report = _report(
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 29),
        total_taxable_sales=5_218_500,
        output_vat=796_042,
        total_taxable_purchases=2_788_950,
        input_vat=425_433,
        vat_difference=370_609,
        vat_payable=370_609,
        refund=0.0,
        remaining_refund=0.0,
        required_sales_to_clear_refund=0.0,
        required_purchases_to_clear_vat_payable=2_429_548,
        created_at=datetime(2026, 8, 2, 7, 42, 0),
    )
    text = ReportTextService().build(report, company)

    assert "Mwaramutse neza!  TWAGIRA-HOMELAND Ltd (120910947)," in text
    assert "Report yuko muhagaze kuva 01/07/2026  kujyeza 29/07/2026" in text
    assert "biri taxable bingana =  5,218,500 Frw" in text
    assert "Bifite Vat =  796,042 frw" in text
    assert "biri taxable =  2,788,950 frw" in text
    assert "Na VAT = 425,433 Frw" in text
    assert "Kugeza ubu turabona muri mumusoro wangana na 370,609 frw" in text
    assert "kugirango uyu musoro uvemo mwaranguza amafaranga angana na 2,429,548 frw" in text
    assert text.strip().endswith("Murakoze mugire umunsi mwiza!")


def test_zero_output_vat_omits_refund_payable_section() -> None:
    """Pinned to a real accountant-shared example: taxpayer not VAT-registered on
    sales (Bifite Vat = 0) — the refund/payable block is skipped entirely."""
    company = CompanyInfo(name="NDINDABO VENUSTE", tin="102046788")
    report = _report(
        period_start=date(2026, 1, 1),
        period_end=date(2026, 7, 30),
        total_taxable_sales=1_788_620,
        output_vat=0,
        total_taxable_purchases=7_410_050,
        input_vat=1_116_389,
        vat_difference=-1_116_389,
        vat_payable=0.0,
        refund=1_116_389,
        remaining_refund=1_116_389,
        required_sales_to_clear_refund=7_318_998.94,
        required_purchases_to_clear_vat_payable=0.0,
        created_at=datetime(2026, 8, 2, 20, 33, 0),
    )
    text = ReportTextService().build(report, company)

    assert "Mwiriwe neza!  NDINDABO VENUSTE (102046788)," in text
    assert "Report yuko muhagaze kuva 01/01/2026  kujyeza 30/07/2026" in text
    assert "biri taxable bingana =  1,788,620 Frw" in text
    assert "Bifite Vat =  0 frw" in text
    assert "biri taxable =  7,410,050 frw" in text
    assert "Na VAT = 1,116,389 Frw" in text
    assert "refund" not in text.lower()
    assert "musoro" not in text.lower()
    assert text.strip().endswith("Murakoze mugire umugoroba mwiza!")

    # goes straight from "Na VAT" line to the closing section
    assert "Na VAT = 1,116,389 Frw\n\nNyuma yiyo mibare" in text


def test_morning_greeting_and_closing() -> None:
    company = CompanyInfo(name="JOSELYNE", tin="121302342")
    report = _report(created_at=datetime(2026, 8, 2, 7, 30, 0))
    text = ReportTextService().build(report, company)

    assert text.startswith("Mwaramutse neza!  JOSELYNE (121302342),")
    assert text.strip().endswith("Murakoze mugire umunsi mwiza!")


def test_afternoon_greeting_and_closing() -> None:
    company = CompanyInfo(name="JOSELYNE", tin="121302342")
    report = _report(created_at=datetime(2026, 8, 2, 14, 0, 0))
    text = ReportTextService().build(report, company)

    assert text.startswith("Mwiriwe neza!  JOSELYNE (121302342),")
    assert text.strip().endswith("Murakoze mugire umunsi mwiza!")


def test_evening_greeting_and_closing() -> None:
    company = CompanyInfo(name="JOSELYNE", tin="121302342")
    report = _report(created_at=datetime(2026, 8, 2, 18, 30, 0))
    text = ReportTextService().build(report, company)

    assert text.startswith("Mwiriwe neza!  JOSELYNE (121302342),")
    assert text.strip().endswith("Murakoze mugire umugoroba mwiza!")


def test_night_greeting_and_closing() -> None:
    company = CompanyInfo(name="JOSELYNE", tin="121302342")
    report = _report(created_at=datetime(2026, 8, 2, 23, 0, 0))
    text = ReportTextService().build(report, company)

    assert text.startswith("Mwiriwe neza!  JOSELYNE (121302342),")
    assert text.strip().endswith("Murakoze mugire ijoro ryiza!")


def test_early_morning_before_5am_is_night() -> None:
    company = CompanyInfo(name="JOSELYNE", tin="121302342")
    report = _report(created_at=datetime(2026, 8, 2, 3, 0, 0))
    text = ReportTextService().build(report, company)

    assert text.strip().endswith("Murakoze mugire ijoro ryiza!")
