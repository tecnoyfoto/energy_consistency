"""Spreadsheet programs must treat user labels as text."""

import pytest

from custom_components.energy_consistency.reporting import csv_safe_text


@pytest.mark.parametrize(
    "label",
    ["=1+1", "+SUM(A1)", "-1+1", "@SUM(A1)", "  =1+1", "\tformula", "\nformula"],
)
def test_formula_like_labels_are_escaped(label):
    assert csv_safe_text(label) == "'" + label


@pytest.mark.parametrize("label", [None, "", "Main meter", "Kitchen / backup"])
def test_normal_labels_are_unchanged(label):
    assert csv_safe_text(label) == label
