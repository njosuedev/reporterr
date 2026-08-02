"""Shared number/date formatting helpers used by the PDF and text report builders."""
from datetime import date


def format_rwf(amount: float) -> str:
    """e.g. 1234567.5 -> 'RWF 1,234,568'"""
    return f"RWF {round(amount):,}"


def format_amount(amount: float) -> str:
    """e.g. 1234567.5 -> '1,234,568' (no currency prefix, for the Frw-suffixed WhatsApp text)"""
    return f"{round(amount):,}"


def format_date(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "N/A"
