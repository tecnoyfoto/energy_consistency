# HACS distribution audit - 0.9.1

The starting point was the installed integration with its eData compatibility repair. This document describes public code and verification; it includes no installation history, credentials, entity identifiers or household readings.

## Addressed findings

| Area | Failure or risk | Change |
| --- | --- | --- |
| eData updates | A renamed daily sensor leaves an unavailable configured entity | Same-supply identity migration preserving comparison history |
| eData compatibility | Legacy hour attributes and historical layout changed | Both hour attributes and history layouts, with guarded sensor fallback |
| Recorder units | Live sensor units can differ from stored statistics units | Request energy statistics in kWh explicitly |
| Measurement migrations | Threshold-only reclassification falsely upgrades measurement versions | Preserve stored measurement versions and refresh available older days |
| Configuration | Temporary official outages prevent recovery through settings | Allow reconfiguration of unavailable sources, with translated errors |
| Options | Updating source data and options separately causes duplicate reloads | Commit both together |
| Diagnosis | A historical meter warning can hide the current source outage | Prioritize the current reason and identify unavailable sources |
| Privacy | Titles and difference pairs expose or reconstruct private readings | Redact custom titles, names, entity identifiers and energy differences |
| CSV export | A formula-like configured meter name may execute in a spreadsheet | Export such labels as text |
| Setup lifecycle | A failed setup leaves listeners or timers behind | Clean up on failures and cancellation |
| Storage resilience | An invalid integer field can interrupt historical loading | Skip an overflowing invalid record |
| Distribution | Working directories can accidentally include local backups | Ignore local material and build releases from an explicit public allowlist |

## Verification

- 93 Python regression tests, also run with Python 3.14.2.
- 5 badge diagnosis tests using Node's test runner and a minimal DOM.
- Ruff, Python syntax, JavaScript syntax, JSON, translation-key parity and version consistency checks.
- Installable archive contents checked independently of the working directory.
- Updated integration started in a real Home Assistant 2026.10.1 installation with eData 2026.10.4; configuration validation, duplicate prevention, options, diagnostics, history retention and application logs were checked.

## Limits and release gate

These checks do not promise compatibility with every device, Home Assistant version or future eData layout. The automated Python tests isolate rules and production methods against simulated Home Assistant APIs; the badge tests are not a browser accessibility or full frontend compatibility suite. Official HACS and Hassfest validators are configured in GitHub Actions and must pass on the proposed commit before publishing. The Python CI matrix covers 3.13 and 3.14.

Backfill uses optional eData internals and a bounded lookback window. Recorder bucket coverage does not prove uninterrupted measurements. The official reading's date must represent the same local calendar day and timezone used by Home Assistant; normalize it in the source/template if necessary. Historical CSV files contain private consumption and labels even though diagnostic downloads redact them.

This project supports installation as a custom HACS repository. Acceptance into HACS's default catalogue is a separate process. Release publication and tagging are separate from preparing these source changes.

References: [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/) and [Home Assistant Recorder statistics and unit conversion](https://www.home-assistant.io/actions/recorder.get_statistics/).
