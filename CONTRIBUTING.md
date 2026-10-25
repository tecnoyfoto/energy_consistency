# Contributing

Use synthetic entity identifiers and readings in tests and examples. Do not commit installation storage, credentials, backups, reports or household screenshots. These are not part of a public release.

Run the checks from the repository root:

```sh
python -m pip install pytest ruff
python -m pytest -q tests/energy_consistency
python -m ruff check custom_components tests scripts
node --check custom_components/energy_consistency/www/energy-consistency-badge.js
node --test tests/frontend/test_badge.cjs
python scripts/validate_release.py
python scripts/build_release.py
```

The Python suite exercises pure rules and production methods against simulated Home Assistant APIs. The badge tests use a minimal DOM. They do not replace a real Home Assistant installation test. Before publishing, also check fresh configuration, upgrading an existing entry, a restart, an unavailable official source, a disabled backup and preserved comparison dates in a real installation. Check both supported eData layouts when changing the history adapter. Keep optional eData failures separate from the sensor fallback.

The GitHub workflow also runs the official HACS and Hassfest validators. Passing HACS custom-repository validation is different from being accepted into the default HACS catalogue.

See [the audit findings](AUDIT.md) for release checks and the remaining compatibility limits.

For a release, update manifest.json, FRONTEND_VERSION, both READMEs and both changelogs together. The archive builder uses an allowlist of component files and public documentation; never zip a working directory or its backups. Create a GitHub release tag matching the manifest only after checks pass. Release publication is a separate explicit action.
