[Leer en español](README.es.md)

# Energy Consistency for Home Assistant

Energy Consistency is a custom Home Assistant integration that compares an
official daily electricity reading with the energy measured locally for the
exact same calendar day.

Its purpose is to monitor **energy consistency and data quality**. It reports
whether both sources tell a coherent story, but it does not attempt to infer
the cause of a discrepancy.

## Current status

Version `0.7.3` is the current public preview. It is already running in a real
Home Assistant installation, includes automated tests, preserves verified
history across restarts, and deliberately rejects partial days.

## Highlights

- Configuration and reconfiguration from the Home Assistant UI.
- Exact comparison of matching local calendar days.
- Complete 23, 24, and 25-hour day validation for daylight-saving changes.
- Local reconstruction from hourly Recorder statistics.
- Missing or partial days are skipped and can be recovered later.
- Automatic backfill of delayed complete eData readings.
- Safe fallback to the configured official sensor if eData's optional internal
  history is unavailable or changes structure.
- Persistent comparison history independent of Recorder retention.
- Conservative learning, review, and critical rules designed to avoid alerts
  from one isolated unusual day.
- Source health checks for unavailable, stale, incomplete, or possibly frozen
  data.
- Monthly CSV reports stored locally in Home Assistant.
- Privacy-aware downloadable diagnostics.
- English and Spanish translations.
- A native-looking traffic-light badge with interactive recent-day details.

## Requirements

You need three Home Assistant entities:

1. An official sensor containing daily energy in `Wh`, `kWh`, or `MWh`.
2. An entity whose state identifies the date represented by that official
   value.
3. A cumulative local energy sensor with the `energy` device class and the
   `total` or `total_increasing` state class.

The official source must provide enough information to prove that a day is
complete. The integration currently supports:

- eData complete daily consumption records;
- another official sensor exposing `last_registered_day_hours`.

Energy Consistency never assumes that an arbitrary daily value is complete.

## Installation

### HACS custom repository

1. Open **HACS > Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/tecnoyfoto/energy_consistency` as an
   **Integration**.
4. Install **Energy Consistency**.
5. Restart Home Assistant.
6. Open **Settings > Devices & services > Add integration** and search for
   **Energy Consistency**.

### Manual installation

Copy this directory into your Home Assistant configuration:

```text
config/
  custom_components/
    energy_consistency/
```

Restart Home Assistant and add the integration from **Settings > Devices &
services**.

## Configuration

For a typical eData setup, select:

- **Official daily energy:** the `Last registered consumption` sensor.
- **Date of the official reading:** the eData entity containing the represented
  date.
- **Local cumulative energy:** the single whole-home cumulative channel from
  the local meter.

Do not add several local channels unless the physical installation actually
requires their sum. Select the entity that represents the whole-home total.

Changing the display name preserves history. Changing any source entity starts
a new history so measurements from different source combinations are never
mixed.

## Status model

Default daily classification:

| Daily status | Rule |
| --- | --- |
| Correct | Absolute difference is at most `0.5 kWh` **or** relative difference is at most `5%` |
| Review | Outside the correct range without exceeding both critical thresholds |
| Critical day | Difference exceeds both `2 kWh` **and** `15%` |

The overall status is intentionally conservative:

| Overall status | Meaning |
| --- | --- |
| Learning | Fewer than seven valid complete days |
| Correct | Recent complete calendar days are coherent |
| Review | At least two anomalous days in three complete consecutive calendar days |
| Critical | Three consecutive critical days, or five critical days in the latest seven-day calendar window |
| Waiting | The next official complete day is not ready |
| Data issue | A source or the required local statistics are not reliable |

Missing dates break consecutive anomaly streaks. Thresholds, the learning
period, frozen-sensor timeout, and accepted official delay can be changed in
the integration options. Stored measurements are reclassified automatically
when thresholds change.

## Complete-day policy and delayed data

A comparison is saved only when:

- the official source contains exactly the expected 23, 24, or 25 hours;
- Recorder contains every expected local hourly statistics bucket;
- both energy values are valid and non-negative.

If either side is incomplete, the date is not counted. The integration keeps
looking back and can add that date later when both complete sources become
available.

For eData, historical daily data is used when its compatible internal history
is available. If that optional structure is missing or changes, the integration
falls back only to the latest configured official sensor and still requires its
complete hour count.

## Badge

The integration registers its badge automatically. Add **Energy Consistency**
from the dashboard badge picker, or use:

```yaml
type: custom:energy-consistency-badge
entity: sensor.energy_consistency_status
```

Colors:

- green: correct;
- orange: review;
- red: critical;
- grey: data issue;
- blue: learning or waiting.

Selecting the badge opens the diagnosis. Selecting a recent date replaces the
upper detail with that day's verified readings and highlights the chosen row.

## Entities

The integration creates diagnostic sensors for:

- overall status;
- official energy;
- local energy;
- signed difference in kWh;
- difference percentage;
- local data coverage;
- comparison date;
- official data delay.

## History and CSV reports

Verified comparisons are stored by the integration independently of Recorder
retention. Monthly CSV reports are generated under:

```text
/config/energy_consistency/reports/<config_entry_id>/
```

Reports include readings, signed differences, coverage, official-hour proof,
active thresholds, classification reason, and algorithm version. A report
write failure is logged but never interrupts the sensors.

## Privacy and diagnostics

Downloadable diagnostics redact configured entity identifiers, display names,
and absolute energy readings. The integration performs all comparisons locally
inside Home Assistant and does not send energy data to an external service.

## Known limitations

- Historical backfill is optimized for eData. Other official integrations can
  compare their latest complete day when they expose the required hour count.
- The eData historical adapter relies on an optional internal structure because
  eData does not currently expose those historical rows through a public Home
  Assistant API. A guarded sensor fallback prevents this dependency from
  blocking new complete comparisons.
- Local coverage proves that every hourly Recorder bucket exists; it cannot
  prove uninterrupted raw samples within each hour.
- The custom badge uses Home Assistant frontend APIs and may need maintenance
  after future frontend changes.

## Troubleshooting

- **Waiting for a complete official day:** the official source has not yet
  provided every expected hour.
- **Local statistics incomplete:** Recorder does not contain every hourly bucket
  for that date. The date is skipped and may be recovered later.
- **Data issue:** inspect the badge diagnosis for unavailable, invalid, stale, or
  possibly frozen sources.
- **Badge not found just after restarting:** wait until Home Assistant finishes
  starting and fully reload the browser page.
- **Reports not updating:** inspect the Home Assistant log for an Energy
  Consistency CSV error.

## Support

Use [GitHub Issues](https://github.com/tecnoyfoto/energy_consistency/issues) and
include the Home Assistant version, integration version, diagnosis text, and
redacted downloadable diagnostics when relevant.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
