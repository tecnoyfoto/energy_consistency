"""Downloaded diagnostics redact identifiers and reconstructible consumption."""

import ast
import asyncio
import json
from dataclasses import asdict
from types import SimpleNamespace

from custom_components.energy_consistency.models import (
    CoordinatorSnapshot,
    DailyComparison,
)
from tests.support.source_loader import ROOT, load_methods


def test_private_titles_names_identifiers_and_consumption_are_redacted():
    ns = {"asdict": asdict}
    from custom_components.energy_consistency import const

    ns.update({key: getattr(const, key) for key in dir(const) if key.isupper()})
    tree = ast.parse((ROOT / "diagnostics.py").read_text(encoding="utf-8"))
    # Use the actual declared redaction fields, not a second copy in the test.
    for node in tree.body:
        if isinstance(node, ast.Assign):
            name = node.targets[0].id
            if name.startswith("TO_REDACT_"):
                ns[name] = set(
                    eval(
                        compile(ast.Expression(node.value), "diagnostics.py", "eval"),
                        ns,
                    )
                )

    def redact(value, keys):
        if isinstance(value, dict):
            return {
                k: "**REDACTED**" if k in keys else redact(v, keys)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [redact(v, keys) for v in value]
        return value

    ns["async_redact_data"] = redact
    load_methods("diagnostics.py", {"async_get_config_entry_diagnostics"}, ns)
    record = DailyComparison(
        date="2026-10-23",
        official_kwh=12.345,
        local_kwh=13.579,
        difference_kwh=1.234,
        difference_percent=9.996,
        coverage_percent=100,
        status="ok",
        reason="within_tolerance",
        primary_local_name="PRIVATE_LABEL",
        local_source_entity="sensor.private_meter",
    )
    data = CoordinatorSnapshot(
        status="ok",
        reason="recent_days_within_tolerance",
        official_kwh=12.345,
        local_kwh=13.579,
        difference_kwh=1.234,
        difference_percent=9.996,
    )
    entry = SimpleNamespace(
        title="PRIVATE_TITLE",
        data={
            "name": "PRIVATE_TITLE",
            "official_energy_entity": "sensor.private_official",
        },
        options={},
        runtime_data=SimpleNamespace(data=data, records=[record]),
    )
    result = asyncio.run(ns["async_get_config_entry_diagnostics"](None, entry))
    text = json.dumps(result)
    for private in [
        "PRIVATE_TITLE",
        "PRIVATE_LABEL",
        "sensor.private",
        "12.345",
        "13.579",
        "1.234",
        "9.996",
    ]:
        assert private not in text
    assert result["records"][0]["date"] == "2026-10-23"
    assert result["snapshot"]["status"] == "ok"
