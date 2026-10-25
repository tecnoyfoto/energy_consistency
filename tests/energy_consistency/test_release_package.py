"""Only the public integration belongs in a distributable package."""

from scripts.build_release import public_files


def test_packaging_excludes_installation_data_and_backups(tmp_path):
    component = tmp_path / "custom_components/energy_consistency"
    component.mkdir(parents=True)
    (component / "sensor.py").write_text("# public")
    (component / "__pycache__").mkdir()
    (component / "__pycache__/sensor.pyc").write_bytes(b"private-cache")
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups/config_entry.json").write_text("private-installation")
    (tmp_path / "REPARACION-local.md").write_text("private-report")
    names = {p.relative_to(tmp_path).as_posix() for p in public_files(tmp_path)}
    assert names == {"custom_components/energy_consistency/sensor.py"}
