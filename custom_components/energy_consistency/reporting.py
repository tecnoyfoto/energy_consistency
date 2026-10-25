"""Safe text cells for spreadsheet-compatible CSV reports."""

from __future__ import annotations


def csv_safe_text(value: str | None) -> str | None:
    """Keep a user label as text when a spreadsheet opens an exported report."""
    if value and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    if value and value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value
