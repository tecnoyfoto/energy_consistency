# Changelog

All notable changes to Energy Consistency are documented in this file.

## [0.7.2] - 2026-07-30

First public preview.

### Added

- UI setup, reconfiguration, and adjustable comparison thresholds.
- Exact complete-day comparison using official hour proof and Recorder hourly
  statistics, including 23 and 25-hour DST days.
- Conservative learning, review, critical, waiting, and data-health states.
- Persistent history, delayed eData backfill, and monthly CSV reports.
- Source availability, staleness, completeness, and frozen-meter checks.
- Privacy-aware downloadable diagnostics.
- English and Spanish translations.
- Interactive Lovelace badge with selectable recent-day details.
- Local custom-integration brand icon.
- Automated engine, persistence, and eData compatibility tests.

### Safety and reliability

- Partial official or local days are never counted as discrepancies.
- Missing days break consecutive anomaly sequences and can be recovered later.
- The latest verified result survives Home Assistant startup while sources
  restore.
- If eData's optional internal history is unavailable or incompatible, only a
  demonstrably complete configured official sensor is used as fallback.
