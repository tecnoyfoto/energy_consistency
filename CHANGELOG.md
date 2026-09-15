# Changelog

All notable changes to Energy Consistency are documented in this file.

## [0.8.1] - 2026-09-15

### Fixed

- Allow an existing local cumulative energy entity to be reconfigured while
  its live state is temporarily `unavailable` or `unknown`. Its energy device
  class and total state class are still validated, so a backup can be assigned
  precisely while the primary meter is down.

## [0.8.0] - 2026-09-14

### Added

- Optional prioritized backup local meter; local readings are selected and
  never summed.
- Automatic failover for incomplete, invalid, unavailable, or frozen primary
  meter days.
- A conservative data issue when two healthy complete meters disagree.
- Configurable completed-day frozen detection.

### Changed

- Preserve verified history when local meters are added, removed, or reordered.
- Store the selected meter, fallback reason, per-meter readings, coverage, and
  zero-hour streaks with each new comparison.
- Migrate existing single-meter configurations without losing records.

## [0.7.3] - 2026-07-31

### Fixed

- Register the interactive badge as a persistent Lovelace resource so Android
  remote connections do not depend on a separately cached frontend index.
- Retain automatic extra-module registration as a fallback for YAML-managed
  Lovelace resources.

## [0.7.2] - 2026-07-30

First public release.

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
