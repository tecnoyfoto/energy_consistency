"""Load production methods for isolated tests without installing Home Assistant."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[2] / "custom_components" / "energy_consistency"


def load_methods(
    file: str, names: set[str], namespace: dict[str, Any]
) -> dict[str, Any]:
    """Compile named local methods; Home Assistant APIs are supplied by each test."""
    path = ROOT / file
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    assert {node.name for node in functions} == names
    for node in functions:
        node.decorator_list = []
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0
    )
    module = ast.fix_missing_locations(
        ast.Module(body=[future, *functions], type_ignores=[])
    )
    exec(compile(module, str(path), "exec"), namespace)  # noqa: S102 - trusted project source.
    return namespace
