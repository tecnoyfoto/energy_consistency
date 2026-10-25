"""Build an installable archive exclusively from public integration files."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "energy_consistency"


def public_files(root: Path = ROOT) -> list[Path]:
    """Never collect local installation storage, backups, reports, or work files."""
    component = root / "custom_components" / "energy_consistency"
    result = [
        p
        for p in component.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix in {".py", ".json", ".js", ".png"}
    ]
    for name in (
        "README.md",
        "README.es.md",
        "CHANGELOG.md",
        "CHANGELOG.es.md",
        "LICENSE",
        "AUDIT.md",
    ):
        if (root / name).is_file():
            result.append(root / name)
    return sorted(result)


def build_release(root: Path = ROOT) -> Path:
    version = json.loads(
        (root / "custom_components/energy_consistency/manifest.json").read_text(
            encoding="utf-8"
        )
    )["version"]
    output = root / "dist" / f"energy_consistency-{version}.zip"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in public_files(root):
            archive.write(path, path.relative_to(root).as_posix())
    return output


if __name__ == "__main__":
    print(build_release())
