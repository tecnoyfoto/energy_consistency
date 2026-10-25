"""Load the standalone rules without importing Home Assistant's integration entrypoint."""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).parents[2] / "custom_components"
for name, path in [
    ("custom_components", ROOT),
    ("custom_components.energy_consistency", ROOT / "energy_consistency"),
]:
    package = sys.modules.setdefault(name, types.ModuleType(name))
    package.__path__ = [str(path)]
