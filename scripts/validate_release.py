"""Check release metadata, translations and public-source hygiene."""

from __future__ import annotations

import ast
import json
import re

from build_release import COMPONENT, ROOT, public_files


def key_paths(value: dict, prefix: str = "") -> set[str]:
    result = set()
    for key, child in value.items():
        path = f"{prefix}.{key}"
        result.add(path)
        if isinstance(child, dict):
            result.update(key_paths(child, path))
    return result


def validate() -> None:
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    assert {
        "domain",
        "name",
        "version",
        "documentation",
        "issue_tracker",
        "codeowners",
    } <= manifest.keys()
    assert manifest["domain"] == "energy_consistency"
    tree = ast.parse((COMPONENT / "const.py").read_text(encoding="utf-8"))
    version = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "FRONTEND_VERSION"
            for target in node.targets
        )
    )
    assert version == manifest["version"], (
        "Frontend cache version must match the release"
    )
    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    for path in COMPONENT.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    for language in ("en", "es"):
        translated = json.loads(
            (COMPONENT / "translations" / f"{language}.json").read_text(
                encoding="utf-8"
            )
        )
        assert key_paths(translated) == key_paths(strings), (
            f"Translation keys differ: {language}"
        )
    for name in ("README.md", "README.es.md"):
        assert f"`{version}`" in (ROOT / name).read_text(encoding="utf-8")
    patterns = [
        r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
        r"192\.168\.\d{1,3}\.\d{1,3}",
    ]
    for path in public_files():
        if path.suffix == ".png":
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            assert re.search(pattern, text) is None, (
                f"Possible private installation data in {path.relative_to(ROOT)}"
            )
    print(f"Release {version}: metadata, translations and public files validated")


if __name__ == "__main__":
    validate()
