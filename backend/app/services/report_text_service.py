"""Builds the exact WhatsApp-style Kinyarwanda report text accountants share with clients."""
from app.services.report_types import CompanyInfo, ReportData
from app.utils.formatting import format_amount, format_date

_HEADER = """{greeting}  {company_name} ({tin}),

Report yuko muhagaze kuva {start_date}  kujyeza {end_date}

1.Ibyo mwacuruje kuva {start_date} kujyeza {end_date} biri taxable bingana =  {total_sales} Frw

Bifite Vat =  {output_vat} frw

2.Ibyo mwaranguye turabona muri System kuva {start_date} kujyeza {end_date} biri taxable =  {total_purchases} frw

Na VAT = {input_vat} Frw"""

_FOOTER = """Nyuma yiyo mibare tubahaye ibyo mucuruje mukabirangurira

{closing}"""

_REFUND_BLOCK = """Kugeza ubu turabona muri muri refund ingana na {remaining_refund} frw
kugirango iyo refund ivemo mwacuruza amafaranga angana na {required_sales} frw"""

_PAYABLE_BLOCK = """Kugeza ubu turabona muri mumusoro wangana na {vat_payable} frw
kugirango uyu musoro uvemo mwaranguza amafaranga angana na {required_purchases} frw"""

_ZERO_BLOCK = """Kugeza ubu nta musoro wa TVA mufite wo kwishyura, kandi nta na refund mufite."""

# (greeting, closing) by hour-of-day, matching how Kinyarwanda greetings shift
# through the day: "Mwaramutse" (morning) -> "Mwiriwe" (from midday onward).
_MORNING = ("Mwaramutse neza!", "Murakoze mugire umunsi mwiza!")
_AFTERNOON = ("Mwiriwe neza!", "Murakoze mugire umunsi mwiza!")
_EVENING = ("Mwiriwe neza!", "Murakoze mugire umugoroba mwiza!")
_NIGHT = ("Mwiriwe neza!", "Murakoze mugire ijoro ryiza!")


def _greeting_and_closing(hour: int) -> tuple[str, str]:
    if 5 <= hour < 12:
        return _MORNING
    if 12 <= hour < 17:
        return _AFTERNOON
    if 17 <= hour < 21:
        return _EVENING
    return _NIGHT


class ReportTextService:
    def build(self, report: ReportData, company: CompanyInfo) -> str:
        greeting, closing = _greeting_and_closing(report.created_at.hour)

        header = _HEADER.format(
            greeting=greeting,
            company_name=company.name,
            tin=company.tin,
            start_date=format_date(report.period_start),
            end_date=format_date(report.period_end),
            total_sales=format_amount(report.total_taxable_sales),
            output_vat=format_amount(report.output_vat),
            total_purchases=format_amount(report.total_taxable_purchases),
            input_vat=format_amount(report.input_vat),
        )

        footer = _FOOTER.format(closing=closing)

        # A taxpayer with no VAT on sales isn't charging/filing VAT on their
        # output side, so a refund/payable position doesn't apply — the report
        # goes straight from the two sections to the closing.
        if report.output_vat == 0:
            return f"{header}\n\n{footer}"

        if report.remaining_refund > 0:
            position_block = _REFUND_BLOCK.format(
                remaining_refund=format_amount(report.remaining_refund),
                required_sales=format_amount(report.required_sales_to_clear_refund),
            )
        elif report.vat_payable > 0:
            position_block = _PAYABLE_BLOCK.format(
                vat_payable=format_amount(report.vat_payable),
                required_purchases=format_amount(report.required_purchases_to_clear_vat_payable),
            )
        else:
            position_block = _ZERO_BLOCK

        return f"{header}\n\n{position_block}\n\n{footer}"
