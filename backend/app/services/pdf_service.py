"""Generates a professional branded VAT report PDF using reportlab (pure-Python, no
system-level dependencies) directly into memory — nothing is written to disk."""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from app.services.report_types import CompanyInfo, ReportData
from app.utils.formatting import format_date, format_rwf

_BRAND_PRIMARY = colors.HexColor("#0F4C81")
_BRAND_ACCENT = colors.HexColor("#F5A623")
_BRAND_LIGHT = colors.HexColor("#EFF4FA")


class PdfService:
    def generate(self, report: ReportData, company: CompanyInfo) -> bytes:
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            title=f"VAT Report - {company.name}",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleBrand", parent=styles["Title"], textColor=_BRAND_PRIMARY, fontSize=20, spaceAfter=2,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle", parent=styles["Normal"], textColor=colors.grey, fontSize=10, spaceAfter=10,
        )
        section_style = ParagraphStyle(
            "Section", parent=styles["Heading2"], textColor=_BRAND_PRIMARY, fontSize=13, spaceBefore=14, spaceAfter=6,
        )
        normal = styles["Normal"]

        elements = []

        elements.append(Paragraph("VAT Analysis Report", title_style))
        elements.append(Paragraph(company.name, subtitle_style))
        elements.append(
            Paragraph(
                f"TIN: {company.tin} &nbsp;|&nbsp; Period: {format_date(report.period_start)} "
                f"&mdash; {format_date(report.period_end)} &nbsp;|&nbsp; "
                f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                subtitle_style,
            )
        )
        elements.append(Spacer(1, 6))

        # Summary cards (as a table)
        summary_data = [
            ["Taxable Sales", "VAT on Sales", "Taxable Purchases", "VAT on Purchase"],
            [
                format_rwf(float(report.total_taxable_sales)),
                format_rwf(float(report.output_vat)),
                format_rwf(float(report.total_taxable_purchases)),
                format_rwf(float(report.input_vat)),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[42 * mm] * 4)
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _BRAND_PRIMARY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 1), (-1, 1), _BRAND_LIGHT),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 10))

        elements.append(Paragraph("VAT Position", section_style))
        position_rows = [
            ["Metric", "Amount (RWF)"],
            ["VAT on Sales", format_rwf(float(report.output_vat))],
            ["VAT on Purchase", format_rwf(float(report.input_vat))],
            ["VAT Difference (Output − Input)", format_rwf(float(report.vat_difference))],
            ["VAT Payable", format_rwf(float(report.vat_payable))],
            ["Refund (this period)", format_rwf(float(report.refund))],
            ["Remaining Refund (carried forward)", format_rwf(float(report.remaining_refund))],
            ["Required Additional Sales to Clear Refund", format_rwf(float(report.required_sales_to_clear_refund))],
            [
                "Required Purchases to Clear VAT Payable",
                format_rwf(float(report.required_purchases_to_clear_vat_payable)),
            ],
        ]
        position_table = Table(position_rows, colWidths=[110 * mm, 50 * mm])
        position_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _BRAND_PRIMARY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _BRAND_LIGHT]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E2EC")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TEXTCOLOR", (0, -2), (-1, -2), _BRAND_ACCENT if float(report.refund) > 0 else colors.black),
                    ("FONTNAME", (0, -2), (-1, -2), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, -1), (-1, -1), _BRAND_ACCENT if float(report.vat_payable) > 0 else colors.black),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        elements.append(position_table)
        elements.append(Spacer(1, 18))

        elements.append(Paragraph("Notes", section_style))
        elements.append(
            Paragraph(
                "This report was generated automatically from the Sales and Purchase reports "
                "exported from the Rwanda EBM system. Please verify figures against your EBM "
                "portal before filing.",
                normal,
            )
        )
        elements.append(Spacer(1, 30))

        signature_table = Table(
            [["_____________________________", "_____________________________"], ["Prepared by", "Approved by"]],
            colWidths=[80 * mm, 80 * mm],
        )
        signature_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 1), (-1, 1), colors.grey),
                    ("TOPPADDING", (0, 1), (-1, 1), 2),
                ]
            )
        )
        elements.append(signature_table)

        def _footer(canvas, doc_):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.grey)
            canvas.drawString(16 * mm, 10 * mm, "VAT Report Analyzer Rwanda — automatically generated document")
            canvas.drawRightString(
                A4[0] - 16 * mm, 10 * mm, f"Page {doc_.page}"
            )
            canvas.restoreState()

        doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
        return buffer.getvalue()
