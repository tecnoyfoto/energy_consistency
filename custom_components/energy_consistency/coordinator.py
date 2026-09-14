"""Coordinator for Energy Consistency."""

from __future__ import annotations

import csv
import logging
import math
import shutil
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    BACKFILL_LOOKBACK_DAYS,
    CONF_BACKUP_LOCAL_ENERGY_ENTITY,
    CONF_CRITICAL_ABS_KWH,
    CONF_CRITICAL_PERCENT,
    CONF_DAILY_ZERO_STREAK_HOURS,
    CONF_FROZEN_HOURS,
    CONF_GREEN_ABS_KWH,
    CONF_GREEN_PERCENT,
    CONF_LEARNING_DAYS,
    CONF_LOCAL_ENERGY_ENTITY,
    CONF_MAX_OFFICIAL_DELAY_DAYS,
    CONF_OFFICIAL_DATE_ENTITY,
    CONF_OFFICIAL_ENERGY_ENTITY,
    DAY_CRITICAL,
    DAY_INCOMPLETE,
    DAY_WARNING,
    DEFAULT_CRITICAL_ABS_KWH,
    DEFAULT_CRITICAL_PERCENT,
    DEFAULT_DAILY_ZERO_STREAK_HOURS,
    DEFAULT_FROZEN_HOURS,
    DEFAULT_GREEN_ABS_KWH,
    DEFAULT_GREEN_PERCENT,
    DEFAULT_LEARNING_DAYS,
    DEFAULT_MAX_OFFICIAL_DELAY_DAYS,
    DOMAIN,
    MAX_RECORDS,
    REFRESH_INTERVAL,
    SOURCE_STARTUP_GRACE,
    STATUS_DATA_ISSUE,
    STATUS_WAITING,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .edata_adapter import EDataAdapterState, resolve_edata_daily_rows
from .engine import (
    aggregate_status,
    cached_result_is_fresh,
    classify_day,
    expected_hours_for_day,
    official_day_is_complete,
    should_recalculate_day,
)
from .local_sources import (
    LocalDayReading,
    official_sources_changed,
    select_local_source,
)
from .models import CoordinatorSnapshot, DailyComparison

_LOGGER = logging.getLogger(__name__)
INVALID_STATES = {STATE_UNKNOWN, STATE_UNAVAILABLE, "none", ""}


class EnergyConsistencyCoordinator(DataUpdateCoordinator[CoordinatorSnapshot]):
    """Compare an official daily value with local Recorder statistics."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            config_entry=entry,
            update_interval=REFRESH_INTERVAL,
            always_update=False,
        )
        self.entry = entry
        self.official_energy_entity = entry.data[CONF_OFFICIAL_ENERGY_ENTITY]
        self.official_date_entity = entry.data[CONF_OFFICIAL_DATE_ENTITY]
        self.local_energy_entity = entry.data[CONF_LOCAL_ENERGY_ENTITY]
        self.backup_local_energy_entity = entry.data.get(
            CONF_BACKUP_LOCAL_ENERGY_ENTITY
        )
        self.local_energy_entities = tuple(
            entity_id
            for entity_id in (
                self.local_energy_entity,
                self.backup_local_energy_entity,
            )
            if entity_id
        )
        self.records: list[DailyComparison] = []
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}{entry.entry_id}"
        )
        self._unsub_state = None
        self._unsub_delayed_refresh = None
        self._started_at = dt_util.now()
        self._startup_grace_enabled = not hass.is_running
        self._latest_local_issue: tuple[date, str] | None = None

    def option(self, key: str, default: Any) -> Any:
        """Return an option, falling back to the default."""
        return self.entry.options.get(key, default)

    async def async_initialize(self) -> None:
        """Load persisted records and start source monitoring."""
        stored = await self._store.async_load() or {}
        current_sources = self._source_storage_metadata()
        stored_sources = stored.get("sources")
        sources_changed = official_sources_changed(stored_sources, current_sources)
        local_sources_changed = (
            isinstance(stored_sources, dict)
            and not sources_changed
            and stored_sources != current_sources
        )
        loaded_records: dict[str, DailyComparison] = {}
        rejected_records = 0
        for item in () if sources_changed else stored.get("records", []):
            if not isinstance(item, dict):
                rejected_records += 1
                continue
            try:
                record = DailyComparison.from_dict(item)
            except (KeyError, TypeError, ValueError):
                rejected_records += 1
                _LOGGER.warning("Ignoring an invalid stored energy comparison")
                continue
            loaded_records[record.date] = record
        self.records = sorted(loaded_records.values(), key=lambda item: item.date)[
            -MAX_RECORDS:
        ]
        reclassified = self._reclassify_records()
        if sources_changed:
            _LOGGER.info(
                "Official energy sources changed; starting a new comparison history"
            )
            await self._async_clear_reports()
        elif local_sources_changed:
            _LOGGER.info(
                "Local meter configuration changed; preserving comparison history"
            )
        if sources_changed or local_sources_changed or rejected_records or reclassified:
            await self._async_persist()
            await self._async_write_reports()

        entities = {
            self.official_energy_entity,
            self.official_date_entity,
            *self.local_energy_entities,
        }

        async def _delayed_refresh(_: datetime) -> None:
            self._unsub_delayed_refresh = None
            await self.async_request_refresh()

        @callback
        def _source_changed(event: Event) -> None:
            # e-data and similar integrations update their date and value entities
            # sequentially. Debounce the pair so they are never compared crossed.
            # The local total can change frequently, so refresh for it only when
            # its availability changes (for example, after a restart).
            if event.data.get("entity_id") in self.local_energy_entities:
                old_state = event.data.get("old_state")
                new_state = event.data.get("new_state")
                old_invalid = (
                    old_state is None or old_state.state.lower() in INVALID_STATES
                )
                new_invalid = (
                    new_state is None or new_state.state.lower() in INVALID_STATES
                )
                if old_invalid == new_invalid:
                    return
            if self._unsub_delayed_refresh is not None:
                self._unsub_delayed_refresh()
            self._unsub_delayed_refresh = async_call_later(
                self.hass, 5, _delayed_refresh
            )

        self._unsub_state = async_track_state_change_event(
            self.hass, entities, _source_changed
        )

    async def async_shutdown(self) -> None:
        """Stop listeners owned by the coordinator."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_delayed_refresh is not None:
            self._unsub_delayed_refresh()
            self._unsub_delayed_refresh = None

    async def _async_update_data(self) -> CoordinatorSnapshot:
        """Refresh health and, when possible, compare the latest official day."""
        self._latest_local_issue = None
        official_state = self.hass.states.get(self.official_energy_entity)
        date_state = self.hass.states.get(self.official_date_entity)

        missing = [
            entity_id
            for entity_id, state in (
                (self.official_energy_entity, official_state),
                (self.official_date_entity, date_state),
            )
            if state is None or state.state.lower() in INVALID_STATES
        ]
        if missing:
            if self._within_startup_grace() and (
                cached := self._cached_snapshot(missing)
            ):
                return cached
            return self._snapshot(
                STATUS_DATA_ISSUE,
                "source_unavailable",
                extra_reason=", ".join(self._source_roles(missing)),
            )

        assert official_state is not None
        assert date_state is not None

        official_date = _parse_date(date_state.state)
        official_kwh = _energy_to_kwh(
            official_state.state,
            official_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
        )
        if official_date is None or official_kwh is None:
            invalid_sources = [
                entity_id
                for entity_id, invalid in (
                    (self.official_date_entity, official_date is None),
                    (self.official_energy_entity, official_kwh is None),
                )
                if invalid
            ]
            if self._within_startup_grace() and (
                cached := self._cached_snapshot(invalid_sources)
            ):
                return cached
            return self._snapshot(STATUS_DATA_ISSUE, "invalid_official_value")

        today = dt_util.now().date()
        delay_days = max((today - official_date).days, 0)
        max_delay = int(
            self.option(CONF_MAX_OFFICIAL_DELAY_DAYS, DEFAULT_MAX_OFFICIAL_DELAY_DAYS)
        )
        if delay_days > max_delay:
            return self._snapshot(
                STATUS_DATA_ISSUE,
                "official_data_too_old",
                official_delay_days=delay_days,
            )

        edata_adapter_state = await self._async_backfill_edata_days(today)
        using_edata_history = edata_adapter_state is EDataAdapterState.HISTORY_AVAILABLE

        official_hours = _optional_float(
            official_state.attributes.get("last_registered_day_hours")
        )
        expected_official_hours = expected_hours_for_day(
            official_date, dt_util.DEFAULT_TIME_ZONE
        )
        if not official_day_is_complete(official_hours, expected_official_hours):
            if cached := self._cached_snapshot(
                ["official_day_incomplete"],
                official_hours=official_hours,
                expected_official_hours=expected_official_hours,
            ):
                return cached
            return self._snapshot(
                STATUS_WAITING,
                "waiting_for_complete_official_day",
                official_delay_days=delay_days,
                official_hours=official_hours,
                expected_official_hours=expected_official_hours,
            )

        frozen_hours = float(self.option(CONF_FROZEN_HOURS, DEFAULT_FROZEN_HOURS))
        usable_local_states = []
        for entity_id in self.local_energy_entities:
            state = self.hass.states.get(entity_id)
            if state is None or state.state.lower() in INVALID_STATES:
                continue
            if dt_util.now() - state.last_changed <= timedelta(hours=frozen_hours):
                usable_local_states.append(state)
        if not usable_local_states:
            if self._within_startup_grace() and (
                cached := self._cached_snapshot(list(self.local_energy_entities))
            ):
                return cached
            return self._snapshot(
                STATUS_DATA_ISSUE,
                "local_sensor_may_be_frozen",
                official_delay_days=delay_days,
            )

        if official_date >= today:
            return self._snapshot(
                STATUS_WAITING,
                "waiting_for_complete_official_day",
                official_delay_days=delay_days,
            )

        date_key = official_date.isoformat()
        comparison = next(
            (record for record in self.records if record.date == date_key), None
        )
        if using_edata_history and comparison is None:
            if (
                self._latest_local_issue is not None
                and self._latest_local_issue[0] == official_date
                and self._latest_local_issue[1]
                in {"local_sensor_may_be_frozen", "local_sources_disagree"}
            ):
                return self._snapshot(
                    STATUS_DATA_ISSUE,
                    self._latest_local_issue[1],
                    official_delay_days=delay_days,
                    official_hours=official_hours,
                    expected_official_hours=expected_official_hours,
                )
            return self._snapshot(
                STATUS_WAITING,
                "waiting_for_complete_official_day",
                official_delay_days=delay_days,
                official_hours=official_hours,
                expected_official_hours=expected_official_hours,
            )

        if not using_edata_history and should_recalculate_day(comparison, official_kwh):
            comparison = await self._async_compare_day(
                official_date,
                official_kwh,
                official_hours=official_hours,
                expected_official_hours=expected_official_hours,
            )
            if comparison.status == DAY_INCOMPLETE:
                if comparison.reason in {
                    "local_sensor_may_be_frozen",
                    "local_sources_disagree",
                }:
                    return self._snapshot(
                        STATUS_DATA_ISSUE,
                        comparison.reason,
                        official_delay_days=delay_days,
                        official_hours=official_hours,
                        expected_official_hours=expected_official_hours,
                    )
                if cached := self._cached_snapshot(["recorder"]):
                    return cached
                return self._snapshot(
                    STATUS_DATA_ISSUE,
                    comparison.reason,
                    official_delay_days=delay_days,
                    official_hours=official_hours,
                    expected_official_hours=expected_official_hours,
                )
            changed = self._upsert_record(comparison)
            if changed:
                await self._async_persist()
                await self._async_write_reports()

        if comparison is None:
            return self._snapshot(
                STATUS_WAITING,
                "waiting_for_local_statistics",
                official_delay_days=delay_days,
            )

        status, reason = aggregate_status(
            self.records,
            int(self.option(CONF_LEARNING_DAYS, DEFAULT_LEARNING_DAYS)),
        )
        return self._snapshot(
            status,
            reason,
            official_delay_days=delay_days,
            official_hours=official_hours,
            expected_official_hours=expected_official_hours,
        )

    def _cached_snapshot(
        self,
        pending_sources: list[str],
        *,
        official_hours: float | None = None,
        expected_official_hours: int | None = None,
    ) -> CoordinatorSnapshot | None:
        """Return the last verified result while sources recover after startup."""
        valid = [record for record in self.records if record.status != DAY_INCOMPLETE]
        if not valid:
            return None

        latest = valid[-1]
        today = dt_util.now().date()
        latest_date = _parse_date(latest.date)
        if latest_date is None:
            return None
        age_days = max((today - latest_date).days, 0)
        max_delay = int(
            self.option(CONF_MAX_OFFICIAL_DELAY_DAYS, DEFAULT_MAX_OFFICIAL_DELAY_DAYS)
        )
        if not cached_result_is_fresh(latest.date, today, max_delay):
            return None

        status, _ = aggregate_status(
            valid,
            int(self.option(CONF_LEARNING_DAYS, DEFAULT_LEARNING_DAYS)),
        )
        recent = self._recent_calendar_records(valid)
        return CoordinatorSnapshot(
            status=status,
            reason="using_last_verified_result",
            official_kwh=latest.official_kwh,
            local_kwh=latest.local_kwh,
            difference_kwh=latest.difference_kwh,
            difference_percent=latest.difference_percent,
            coverage_percent=latest.coverage_percent,
            comparison_date=latest.date,
            official_delay_days=age_days,
            official_hours=latest.official_hours,
            expected_official_hours=latest.expected_official_hours,
            pending_official_hours=official_hours,
            pending_expected_official_hours=expected_official_hours,
            valid_days=len(valid),
            warning_days=sum(record.status == DAY_WARNING for record in recent),
            critical_days=sum(record.status == DAY_CRITICAL for record in recent),
            using_cached_result=True,
            pending_sources=tuple(self._source_roles(pending_sources)),
            local_source_entity=latest.local_source_entity,
            local_source_role=latest.local_source_role,
            fallback_used=latest.fallback_used,
            fallback_reason=latest.fallback_reason,
            primary_local_kwh=latest.primary_local_kwh,
            backup_local_kwh=latest.backup_local_kwh,
        )

    def _source_roles(self, sources: list[str]) -> list[str]:
        """Return privacy-safe names for source entities and internal waits."""
        roles = {
            self.official_energy_entity: "official_energy",
            self.official_date_entity: "official_date",
            self.local_energy_entity: "primary_local_energy",
            "recorder": "local_statistics",
            "official_day_incomplete": "official_day_incomplete",
        }
        if self.backup_local_energy_entity:
            roles[self.backup_local_energy_entity] = "backup_local_energy"
        return [roles.get(source, "source") for source in sources]

    @staticmethod
    def _recent_calendar_records(
        records: list[DailyComparison],
    ) -> list[DailyComparison]:
        """Return records in the seven-day window ending on the latest date."""
        if not records:
            return []
        latest_day = date.fromisoformat(records[-1].date)
        earliest_day = latest_day - timedelta(days=6)
        return [
            record
            for record in records
            if earliest_day <= date.fromisoformat(record.date) <= latest_day
        ]

    async def _async_backfill_edata_days(self, today: date) -> EDataAdapterState:
        """Recover eData days and report whether its history is authoritative."""
        entity_entry = er.async_get(self.hass).async_get(self.official_energy_entity)
        if entity_entry is None or entity_entry.config_entry_id is None:
            return EDataAdapterState.NOT_EDATA
        source_entry = self.hass.config_entries.async_get_entry(
            entity_entry.config_entry_id
        )
        if source_entry is None or source_entry.domain != "edata":
            return EDataAdapterState.NOT_EDATA

        scups = str(source_entry.data.get("scups", "")).lower()
        adapter_state, rows = resolve_edata_daily_rows(
            self.hass.data.get("edata"), scups
        )
        if adapter_state is EDataAdapterState.HISTORY_UNAVAILABLE:
            _LOGGER.debug(
                "eData history is unavailable; using the configured complete "
                "official sensor as a fallback"
            )
            return adapter_state
        lookback_days = max(
            BACKFILL_LOOKBACK_DAYS,
            int(
                self.option(
                    CONF_MAX_OFFICIAL_DELAY_DAYS,
                    DEFAULT_MAX_OFFICIAL_DELAY_DAYS,
                )
            ),
        )
        earliest = today - timedelta(days=lookback_days)
        changed = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_date = _parse_date_value(row.get("datetime"))
            official_kwh = _optional_float(row.get("value_kWh"))
            official_hours = _optional_float(row.get("delta_h"))
            if (
                row_date is None
                or official_kwh is None
                or official_hours is None
                or row_date >= today
                or row_date < earliest
                or not official_day_is_complete(
                    official_hours,
                    expected_hours_for_day(row_date, dt_util.DEFAULT_TIME_ZONE),
                )
            ):
                continue

            date_key = row_date.isoformat()
            existing = next(
                (record for record in self.records if record.date == date_key),
                None,
            )
            if not should_recalculate_day(existing, official_kwh):
                continue
            expected_hours = expected_hours_for_day(row_date, dt_util.DEFAULT_TIME_ZONE)
            comparison = await self._async_compare_day(
                row_date,
                official_kwh,
                official_hours=official_hours,
                expected_official_hours=expected_hours,
            )
            if comparison.status == DAY_INCOMPLETE:
                if (
                    self._latest_local_issue is None
                    or row_date > self._latest_local_issue[0]
                ):
                    self._latest_local_issue = (row_date, comparison.reason)
                continue
            changed |= self._upsert_record(comparison)

        if changed:
            await self._async_persist()
            await self._async_write_reports()
        return adapter_state

    async def _async_compare_day(
        self,
        official_date: date,
        official_kwh: float,
        *,
        official_hours: float | None = None,
        expected_official_hours: int | None = None,
    ) -> DailyComparison:
        """Build a comparison using exactly one healthy local meter."""
        primary = await self._async_local_day(
            self.local_energy_entity,
            "primary",
            official_date,
        )
        backup = (
            await self._async_local_day(
                self.backup_local_energy_entity,
                "backup",
                official_date,
            )
            if self.backup_local_energy_entity
            else None
        )
        thresholds = self._comparison_thresholds()
        selection = select_local_source(
            primary,
            backup,
            zero_streak_limit_hours=int(
                self.option(
                    CONF_DAILY_ZERO_STREAK_HOURS,
                    DEFAULT_DAILY_ZERO_STREAK_HOURS,
                )
            ),
            agreement_absolute_kwh=thresholds["green_abs_kwh"],
            agreement_percent=thresholds["green_percent"],
        )
        selected = selection.reading
        comparison = classify_day(
            date=official_date.isoformat(),
            official_kwh=official_kwh,
            local_kwh=selected.kwh if selected else None,
            coverage_percent=(
                selected.coverage_percent
                if selected
                else max(
                    primary.coverage_percent,
                    backup.coverage_percent if backup else 0.0,
                )
            ),
            **thresholds,
            official_hours=official_hours,
            expected_official_hours=expected_official_hours,
        )
        if selected is None:
            comparison.reason = selection.reason
        comparison.local_source_entity = selected.entity_id if selected else None
        comparison.local_source_role = selected.role if selected else None
        comparison.fallback_used = selection.fallback_used
        comparison.fallback_reason = selection.fallback_reason
        comparison.primary_local_kwh = primary.kwh
        comparison.backup_local_kwh = backup.kwh if backup else None
        comparison.primary_coverage_percent = primary.coverage_percent
        comparison.backup_coverage_percent = backup.coverage_percent if backup else None
        comparison.primary_zero_streak_hours = primary.zero_streak_hours
        comparison.backup_zero_streak_hours = (
            backup.zero_streak_hours if backup else None
        )
        return comparison

    async def _async_local_day(
        self,
        entity_id: str,
        role: str,
        day: date,
    ) -> LocalDayReading:
        """Return one meter's kWh, coverage, and frozen-hour evidence."""
        local_start = datetime.combine(day, time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE)
        local_end = datetime.combine(
            day + timedelta(days=1), time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE
        )
        start_utc = dt_util.as_utc(local_start)
        end_utc = dt_util.as_utc(local_end)
        expected_hours = int((end_utc - start_utc).total_seconds() // 3600)

        try:
            result = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_utc,
                end_utc,
                {entity_id},
                "hour",
                None,
                {"change"},
            )
        except Exception:
            _LOGGER.exception(
                "Unable to read Recorder statistics for %s",
                entity_id,
            )
            return LocalDayReading(
                entity_id,
                role,
                None,
                0.0,
                error="insufficient_local_coverage",
            )
        rows = result.get(entity_id, [])
        changes = [row.get("change") for row in rows if row.get("change") is not None]
        coverage = (
            min(len(changes) / expected_hours * 100, 100.0) if expected_hours else 0
        )
        if len(changes) != expected_hours:
            return LocalDayReading(
                entity_id,
                role,
                None,
                coverage,
                error="insufficient_local_coverage",
            )

        numeric_changes: list[float] = []
        for value in changes:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return LocalDayReading(
                    entity_id,
                    role,
                    None,
                    coverage,
                    error="invalid_local_value",
                )
            if not math.isfinite(number) or number < 0:
                return LocalDayReading(
                    entity_id,
                    role,
                    None,
                    coverage,
                    error="invalid_local_value",
                )
            numeric_changes.append(number)

        zero_streak = 0
        longest_zero_streak = 0
        for change in numeric_changes:
            if abs(change) <= 1e-9:
                zero_streak += 1
                longest_zero_streak = max(longest_zero_streak, zero_streak)
            else:
                zero_streak = 0

        state = self.hass.states.get(entity_id)
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
        local_value = _energy_to_kwh(sum(numeric_changes), unit)
        return LocalDayReading(
            entity_id,
            role,
            local_value,
            coverage,
            zero_streak_hours=longest_zero_streak,
            error=None if local_value is not None else "invalid_local_value",
        )

    def _within_startup_grace(self) -> bool:
        """Return whether a real Home Assistant startup is still settling."""
        return self._startup_grace_enabled and (
            dt_util.now() - self._started_at <= SOURCE_STARTUP_GRACE
        )

    def _reclassify_records(self) -> bool:
        """Apply current thresholds to persisted objective measurements."""
        changed = False
        updated: list[DailyComparison] = []
        thresholds = self._comparison_thresholds()
        for record in self.records:
            comparison = classify_day(
                date=record.date,
                official_kwh=record.official_kwh,
                local_kwh=record.local_kwh,
                coverage_percent=record.coverage_percent,
                **thresholds,
                official_hours=record.official_hours,
                expected_official_hours=record.expected_official_hours,
            )
            comparison.local_source_entity = record.local_source_entity
            comparison.local_source_role = record.local_source_role
            comparison.fallback_used = record.fallback_used
            comparison.fallback_reason = record.fallback_reason
            comparison.primary_local_kwh = record.primary_local_kwh
            comparison.backup_local_kwh = record.backup_local_kwh
            comparison.primary_coverage_percent = record.primary_coverage_percent
            comparison.backup_coverage_percent = record.backup_coverage_percent
            comparison.primary_zero_streak_hours = record.primary_zero_streak_hours
            comparison.backup_zero_streak_hours = record.backup_zero_streak_hours
            if comparison.status == DAY_INCOMPLETE:
                changed = True
                continue
            updated.append(comparison)
            changed |= comparison != record
        self.records = updated
        return changed

    def _comparison_thresholds(self) -> dict[str, float]:
        """Return validated thresholds, falling back safely if storage is corrupt."""
        values = {
            "min_coverage_percent": 100.0,
            "green_abs_kwh": float(
                self.option(CONF_GREEN_ABS_KWH, DEFAULT_GREEN_ABS_KWH)
            ),
            "green_percent": float(
                self.option(CONF_GREEN_PERCENT, DEFAULT_GREEN_PERCENT)
            ),
            "critical_abs_kwh": float(
                self.option(CONF_CRITICAL_ABS_KWH, DEFAULT_CRITICAL_ABS_KWH)
            ),
            "critical_percent": float(
                self.option(CONF_CRITICAL_PERCENT, DEFAULT_CRITICAL_PERCENT)
            ),
        }
        valid = (
            all(math.isfinite(value) and value >= 0 for value in values.values())
            and values["green_abs_kwh"] < values["critical_abs_kwh"]
            and values["green_percent"] < values["critical_percent"]
        )
        if valid:
            return values
        _LOGGER.error("Invalid comparison thresholds; using safe defaults")
        return {
            "min_coverage_percent": 100.0,
            "green_abs_kwh": DEFAULT_GREEN_ABS_KWH,
            "green_percent": DEFAULT_GREEN_PERCENT,
            "critical_abs_kwh": DEFAULT_CRITICAL_ABS_KWH,
            "critical_percent": DEFAULT_CRITICAL_PERCENT,
        }

    def _upsert_record(self, comparison: DailyComparison) -> bool:
        """Insert or replace a daily record and report whether it changed."""
        for index, current in enumerate(self.records):
            if current.date == comparison.date:
                if current == comparison:
                    return False
                self.records[index] = comparison
                break
        else:
            self.records.append(comparison)
        self.records.sort(key=lambda item: item.date)
        self.records = self.records[-MAX_RECORDS:]
        return True

    async def _async_persist(self) -> None:
        """Persist comparison records independently of Recorder retention."""
        await self._store.async_save(
            {
                "sources": self._source_storage_metadata(),
                "records": [record.as_dict() for record in self.records],
            }
        )

    def _source_storage_metadata(self) -> dict[str, str | None]:
        """Return source identity stored alongside comparisons."""
        return {
            "official_energy": self.official_energy_entity,
            "official_date": self.official_date_entity,
            "local_energy": self.local_energy_entity,
            "backup_local_energy": self.backup_local_energy_entity,
        }

    async def _async_clear_reports(self) -> None:
        """Remove reports that belong to a previous source combination."""
        report_dir = Path(self.hass.config.path(DOMAIN, "reports", self.entry.entry_id))
        try:
            await self.hass.async_add_executor_job(shutil.rmtree, report_dir, True)
        except OSError:
            _LOGGER.exception("Unable to remove reports for previous energy sources")

    async def _async_write_reports(self) -> None:
        """Write reports without allowing an optional export to break sensors."""
        try:
            await self.hass.async_add_executor_job(self._write_monthly_report)
        except OSError:
            _LOGGER.exception("Unable to write Energy Consistency CSV reports")

    def _write_monthly_report(self) -> None:
        """Write compact monthly CSV reports under the configuration folder."""
        report_dir = Path(self.hass.config.path(DOMAIN, "reports", self.entry.entry_id))
        report_dir.mkdir(parents=True, exist_ok=True)
        months = sorted({record.date[:7] for record in self.records})
        for month in months:
            path = report_dir / f"{month}.csv"
            temporary = path.with_suffix(".csv.tmp")
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "date",
                        "official_kwh",
                        "local_kwh",
                        "difference_kwh",
                        "difference_percent",
                        "coverage_percent",
                        "official_hours",
                        "expected_official_hours",
                        "status",
                        "reason",
                        "green_abs_kwh",
                        "green_percent",
                        "critical_abs_kwh",
                        "critical_percent",
                        "min_coverage_percent",
                        "local_source_entity",
                        "local_source_role",
                        "fallback_used",
                        "fallback_reason",
                        "primary_local_kwh",
                        "backup_local_kwh",
                        "primary_coverage_percent",
                        "backup_coverage_percent",
                        "primary_zero_streak_hours",
                        "backup_zero_streak_hours",
                        "algorithm_version",
                    ]
                )
                for record in self.records:
                    if record.date.startswith(month):
                        writer.writerow(
                            [
                                record.date,
                                record.official_kwh,
                                record.local_kwh,
                                record.difference_kwh,
                                record.difference_percent,
                                record.coverage_percent,
                                record.official_hours,
                                record.expected_official_hours,
                                record.status,
                                record.reason,
                                record.green_abs_kwh,
                                record.green_percent,
                                record.critical_abs_kwh,
                                record.critical_percent,
                                record.min_coverage_percent,
                                record.local_source_entity,
                                record.local_source_role,
                                record.fallback_used,
                                record.fallback_reason,
                                record.primary_local_kwh,
                                record.backup_local_kwh,
                                record.primary_coverage_percent,
                                record.backup_coverage_percent,
                                record.primary_zero_streak_hours,
                                record.backup_zero_streak_hours,
                                record.algorithm_version,
                            ]
                        )
            temporary.replace(path)

    def _snapshot(
        self,
        status: str,
        reason: str,
        *,
        official_delay_days: int | None = None,
        official_hours: float | None = None,
        expected_official_hours: int | None = None,
        extra_reason: str | None = None,
    ) -> CoordinatorSnapshot:
        """Build a snapshot from the latest stored record."""
        valid = [record for record in self.records if record.status != DAY_INCOMPLETE]
        latest = valid[-1] if valid else None
        recent = self._recent_calendar_records(valid)
        return CoordinatorSnapshot(
            status=status,
            reason=f"{reason}: {extra_reason}" if extra_reason else reason,
            official_kwh=latest.official_kwh if latest else None,
            local_kwh=latest.local_kwh if latest else None,
            difference_kwh=latest.difference_kwh if latest else None,
            difference_percent=latest.difference_percent if latest else None,
            coverage_percent=latest.coverage_percent if latest else None,
            comparison_date=latest.date if latest else None,
            official_delay_days=official_delay_days,
            official_hours=latest.official_hours if latest else None,
            expected_official_hours=(
                latest.expected_official_hours if latest else None
            ),
            pending_official_hours=official_hours,
            pending_expected_official_hours=expected_official_hours,
            valid_days=len(valid),
            warning_days=sum(record.status == DAY_WARNING for record in recent),
            critical_days=sum(record.status == DAY_CRITICAL for record in recent),
            using_cached_result=False,
            pending_sources=(),
            local_source_entity=latest.local_source_entity if latest else None,
            local_source_role=latest.local_source_role if latest else None,
            fallback_used=latest.fallback_used if latest else False,
            fallback_reason=latest.fallback_reason if latest else None,
            primary_local_kwh=latest.primary_local_kwh if latest else None,
            backup_local_kwh=latest.backup_local_kwh if latest else None,
        )


def _parse_date(value: str) -> date | None:
    """Parse an ISO date or datetime and return its calendar date."""
    try:
        return date.fromisoformat(value.strip()[:10])
    except (TypeError, ValueError):
        parsed = dt_util.parse_datetime(value)
        return parsed.date() if parsed is not None else None


def _parse_date_value(value: Any) -> date | None:
    """Parse a date from either an e-data datetime object or string."""
    if isinstance(value, datetime):
        return dt_util.as_local(value).date() if value.tzinfo else value.date()
    if isinstance(value, str):
        return _parse_date(value)
    return None


def _energy_to_kwh(value: str | float, unit: str | None) -> float | None:
    """Convert a supported energy value to kWh."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    normalized = (unit or "kWh").strip().lower()
    if normalized == "wh":
        return number / 1000
    if normalized == "mwh":
        return number * 1000
    if normalized == "kwh":
        return number
    return None


def _optional_float(value: Any) -> float | None:
    """Convert an optional numeric attribute to float."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
