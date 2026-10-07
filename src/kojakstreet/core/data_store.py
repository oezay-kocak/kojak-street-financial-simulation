"""DuckDB-backed daily history store for the economic simulation."""

from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from kojakstreet.core.data_store_schema import create_schema, migrate_schema
from kojakstreet.core.history import (
    DEFAULT_PIXEL_BUDGET,
    ECONOMIC_MODEL_VERSION,
    HISTORY_SCHEMA_VERSION,
    LEGACY_ECONOMIC_MODEL_VERSION,
    MAX_PIXEL_BUDGET,
    RAW_RETENTION_DAYS,
    SemanticType,
)
from kojakstreet.core.player_accounting import visible_news
from kojakstreet.core.runtime_context import SimulationDelta
from kojakstreet.core.store_health import structured_store_health


class EconomicDataStore:
    """Append compact daily simulation facts to DuckDB when it is available.

    The live Python state remains the source of truth for the current day. This
    store is the durable analytical layer used for histories, charts and later
    larger table queries.
    """

    def __init__(self, path: Path, *, flush_interval_days: int = 10, auto_flush: bool = True) -> None:
        self.path = path
        self.enabled = False
        self.flush_interval_days = max(1, int(flush_interval_days))
        self.auto_flush = auto_flush
        self._pending_rows: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
        self._pending_days: set[str] = set()
        self._current_rows: dict[str, list[tuple[Any, ...]]] = {}
        self._current_dict_rows: dict[str, list[dict[str, object]]] = {}
        self._session_rows: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
        self._current_version = 0
        self._current_delta = SimulationDelta(0, "", frozenset())
        self._duckdb = None
        self._connection = None
        self._writer = None
        self.transient = False
        try:
            import duckdb
        except ImportError:
            return
        self._duckdb = duckdb
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._connection = duckdb.connect(str(self.path))
        except Exception:  # noqa: BLE001 - DuckDB exposes backend-specific open failures
            self._connection = duckdb.connect(":memory:")
            self.transient = True
        self._create_schema()
        self._history_id = self._ensure_history_metadata()
        try:
            self._recover_row_journal()
        except BaseException:
            self._connection.close()
            self._connection = None
            raise
        self.enabled = True

    def _recover_row_journal(self) -> None:
        from kojakstreet.core.persistence_writer import RowJournal

        if self.transient and any(Path(str(self.path) + f".row-journal-{i}").exists() for i in range(2)):
            raise RuntimeError("Durable history cannot be recovered into a transient store")
        journal = RowJournal(self.path, self._history_id, create=False)
        for slot, batch in journal.pending:
            self._write_row_batch(batch, self._connection)
            journal.acknowledge(slot, batch.sequence)

    def enable_background_flush(self, *, on_error=None) -> None:
        """Transfer analytical SQL ownership after initialization; never copy the world."""
        from kojakstreet.core.persistence_writer import OrderedConnection, OrderedWriter

        if self._writer is not None or not self.enabled or self.transient:
            return
        threads = int(self._connection.execute("SELECT current_setting('threads')").fetchone()[0])
        backend = self._duckdb
        self._connection.close()
        self._connection = None

        def connect(path):
            connection = backend.connect(path)
            connection.execute(f"SET threads={threads}")
            return connection

        self._writer = OrderedWriter(self.path, self._history_id, connect, self._write_row_batch, on_error)
        self._connection = OrderedConnection(self._writer)

    def check_persistence_health(self) -> None:
        if self._writer is not None:
            self._writer.check()

    def wait_for_persistence(self) -> None:
        if self._writer is not None:
            self._writer.barrier()

    @staticmethod
    def _write_row_batch(batch, connection) -> None:
        # This target owns only a SQL connection. It has no world, player,
        # current-table cache, pending buffer or session-history references.
        target = object.__new__(EconomicDataStore)
        target._connection = connection
        connection.execute("BEGIN TRANSACTION")
        try:
            for table, rows in batch.pending:
                target._replace_buffered_rows(table, rows)
            target._upsert_structural_events(dict(batch.pending).get("event_log", ()))
            target._compact_completed_history()
            for table, rows in batch.current:
                target._replace_current_rows(table, rows)
            connection.execute("COMMIT")
        except BaseException as error:
            try:
                connection.execute("ROLLBACK")
            except Exception as rollback_error:  # noqa: BLE001 -- keep the original transaction failure
                error.add_note(f"Rollback also failed: {rollback_error}")
            raise

    def close(self) -> None:
        if self._connection is None:
            return
        if self._writer is not None:
            try:
                self.flush()
            finally:
                try:
                    self._connection.close()
                finally:
                    self._connection = None
            return
        self.flush()
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def reset_session(self) -> None:
        """Drop analytics from the abandoned timeline when loading a checkpoint."""
        self.wait_for_persistence()
        self._pending_rows.clear()
        self._pending_days.clear()
        self._current_rows.clear()
        self._current_dict_rows.clear()
        self._session_rows.clear()
        if self._connection is not None:
            for (table,) in self._connection.execute("SHOW TABLES").fetchall():
                if table == "history_metadata":
                    continue
                self._connection.execute(f'DELETE FROM "{_safe_identifier(table)}"')
            self._connection.execute("DELETE FROM history_metadata WHERE key LIKE 'last_%_compaction'")

    def checkpoint_session(self) -> dict:
        # Durable history already lives in DuckDB. Embedding it again in JSON
        # would make checkpoint size depend on world age.
        return {"manifest": self.history_manifest(), "recent_rows": {}}

    def restore_checkpoint_session(self, session: dict) -> None:
        # V4 saves stored the two row lists directly.  V5-style checkpoints
        # carry a manifest and only bounded recent rows.
        self.wait_for_persistence()
        self._pending_rows.clear()
        self._pending_days.clear()
        self._current_rows.clear()
        self._current_dict_rows.clear()
        self._session_rows.clear()
        rows_by_table = session.get("recent_rows", session)
        manifest = session.get("manifest")
        if manifest:
            self.bind_history_manifest(manifest)
        for table in ("product_daily", "bond_daily"):
            rows = rows_by_table.get(table, [])
            self._session_rows[table] = list(rows)
            self._pending_rows[table] = list(rows)
            self._pending_days.update(str(row[0]) for row in rows)

    def history_manifest(self) -> dict[str, object]:
        latest = None
        earliest = None
        markers: dict[str, str] = {}
        if self._connection is not None:
            row = self._connection.execute("SELECT min(date), max(date) FROM asset_daily").fetchone()
            aggregate = self._connection.execute("SELECT min(bucket_start), max(bucket_end) FROM history_aggregate").fetchone()
            starts = [value for value in ((row or (None, None))[0], (aggregate or (None, None))[0]) if value is not None]
            ends = [value for value in ((row or (None, None))[1], (aggregate or (None, None))[1]) if value is not None]
            earliest = str(min(starts)) if starts else None
            latest = str(max(ends)) if ends else None
            markers = {str(key): str(value) for key, value in self._connection.execute("SELECT key, value FROM history_metadata WHERE key LIKE 'last_%_compaction'").fetchall()}
        result = {
            "history_schema_version": HISTORY_SCHEMA_VERSION,
            "economic_model_version": ECONOMIC_MODEL_VERSION,
            "history_id": self._history_id,
            "store_name": self.path.name,
            "earliest_date": earliest,
            "latest_date": latest,
            "completed_buckets": markers,
        }
        if self._connection is not None:
            provenance = self._connection.execute(
                "SELECT key, value FROM history_metadata WHERE key LIKE 'origin_%'"
            ).fetchall()
            if provenance:
                result["origin"] = dict(provenance)
        return result

    def bind_history_manifest(self, manifest: dict[str, object]) -> None:
        expected = str(manifest.get("history_id", ""))
        if expected and expected != self._history_id:
            raise ValueError("Savegame history ID does not match this analytical store")
        if int(manifest.get("history_schema_version", HISTORY_SCHEMA_VERSION)) not in {1, 2, HISTORY_SCHEMA_VERSION}:
            raise ValueError("Unsupported history schema version")
        if str(manifest.get("economic_model_version", ECONOMIC_MODEL_VERSION)) not in {LEGACY_ECONOMIC_MODEL_VERSION, ECONOMIC_MODEL_VERSION}:
            raise ValueError("Savegame economic model version does not match this runtime")

    def seed_history_aggregates(
        self,
        rows: Iterable[tuple[Any, ...]],
        *,
        last_yearly: date | None = None,
        last_monthly: date | None = None,
    ) -> None:
        """Insert deterministic prehistory buckets produced outside the daily engine."""
        if not self.enabled or self._connection is None:
            return
        materialized = list(rows)
        temporary_path: Path | None = None
        if materialized:
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="",
                    suffix=".csv",
                    delete=False,
                ) as stream:
                    temporary_path = Path(stream.name)
                    csv.writer(stream).writerows(materialized)
                quoted_path = str(temporary_path).replace("'", "''")
                self._connection.execute(
                    f"COPY history_aggregate FROM '{quoted_path}' (FORMAT CSV, HEADER FALSE)"
                )
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        for resolution, marker in (("yearly", last_yearly), ("monthly", last_monthly)):
            if marker is None:
                continue
            key = f"last_{resolution}_compaction"
            self._connection.execute("DELETE FROM history_metadata WHERE key=?", [key])
            self._connection.execute("INSERT INTO history_metadata VALUES (?, ?)", [key, marker.isoformat()])

    def current_version(self) -> int:
        """Return a monotonically increasing version for the in-memory current tables."""

        return self._current_version

    def current_delta(self) -> SimulationDelta:
        return self._current_delta

    def record_day(self, daten_module, *, flush: bool = False, current_scope: str = "daily") -> None:
        """Persist one complete current-day snapshot into daily fact tables."""

        if not self.enabled or self._connection is None:
            return
        self.check_persistence_health()
        record_date = (
            getattr(daten_module, "datum", None)
            if current_scope == "full"
            else getattr(daten_module, "last_completed_simulation_date", getattr(daten_module, "datum", None))
        )
        date_text = _date_text(record_date)
        if date_text in self._pending_days:
            self._drop_pending_date(date_text)
        self._pending_days.add(date_text)
        for table, rows in self._session_rows.items():
            if rows and str(rows[-1][0]) == date_text:
                self._session_rows[table] = [row for row in rows if str(row[0]) != date_text]
        report_scope = current_scope == "full" or _is_macro_report_day(record_date)
        asset_rows = self._asset_rows(daten_module, date_text)
        product_rows = self._product_rows(daten_module, date_text)
        company_rows = (
            self._company_rows(daten_module, date_text)
            if report_scope or "company_current" not in self._current_rows
            else self._current_rows.get("company_current", [])
        )
        company_output_rows = (
            self._company_output_rows(daten_module, date_text)
            if report_scope or "company_output_current" not in self._current_rows
            else self._current_rows.get("company_output_current", [])
        )
        country_trade_rows = (
            self._country_trade_rows(daten_module, date_text)
            if report_scope or "country_trade_current" not in self._current_rows
            else self._current_rows.get("country_trade_current", [])
        )
        fund_allocation_rows = (
            self._fund_allocation_rows(daten_module, date_text)
            if report_scope or "fund_allocation_current" not in self._current_rows
            else self._current_rows.get("fund_allocation_current", [])
        )
        country_rows = (
            self._country_rows(daten_module, date_text)
            if report_scope or "country_current" not in self._current_rows
            else self._current_rows.get("country_current", [])
        )
        workforce_rows = (
            self._workforce_rows(daten_module)
            if report_scope or "country_workforce_current" not in self._current_rows
            else self._current_rows.get("country_workforce_current", [])
        )
        global_macro_rows = self._global_macro_rows(daten_module, date_text)
        forex_rows = self._forex_rows(daten_module, date_text)
        portfolio_rows = self._portfolio_rows(daten_module, date_text)
        news_rows = self._news_rows(daten_module, date_text)
        event_rows = self._event_rows(news_rows)
        phase_metric_rows = self._phase_metric_rows(daten_module, date_text)
        next_current_rows = {
            "asset_current": asset_rows,
            "product_current": product_rows,
            "company_current": company_rows,
            "company_output_current": company_output_rows,
            "country_trade_current": country_trade_rows,
            "fund_allocation_current": fund_allocation_rows,
            "country_current": country_rows,
            "country_workforce_current": workforce_rows,
            "global_macro_current": global_macro_rows,
            "forex_current": forex_rows,
            "portfolio_current": portfolio_rows,
            "news_current": news_rows,
            "event_current": event_rows,
            "phase_metric_current": phase_metric_rows,
        }
        politics_changed = bool(getattr(daten_module, "_politics_dirty", False)) or "country_politics_current" not in self._current_rows
        politics_rows = self._current_rows.get("country_politics_current", [])
        if politics_changed:
            from kojakstreet.core.politics import json_text
            politics_rows = [(date_text, c, m["politics"]["revision"], json_text(m["politics"]))
                             for c, m in sorted(daten_module.makro.items()) if "politics" in m]
        next_current_rows["country_politics_current"] = politics_rows
        self._pending_rows["country_politics_monthly"].extend(getattr(daten_module, "_politics_months", []))
        self._pending_rows["politics_events"].extend(getattr(daten_module, "_politics_events", []))
        daten_module._politics_months = []
        daten_module._politics_events = []
        daten_module._politics_dirty = False
        changed_tables = {"asset_current", "phase_metric_current"}
        if politics_changed:
            changed_tables.add("country_politics_current")
        for table, rows in (
            ("product_current", product_rows),
            ("global_macro_current", global_macro_rows),
            ("forex_current", forex_rows),
            ("portfolio_current", portfolio_rows),
        ):
            if table not in self._current_rows or not _same_current_rows(self._current_rows.get(table, []), rows):
                changed_tables.add(table)
        if report_scope:
            changed_tables.update(
                {
                    "company_current",
                    "company_output_current",
                    "country_trade_current",
                    "fund_allocation_current",
                    "country_current",
                    "country_workforce_current",
                }
            )
        if "news_current" not in self._current_rows or not _same_current_rows(self._current_rows.get("news_current", []), news_rows):
            changed_tables.update({"news_current", "event_current"})
        self._current_rows.update(next_current_rows)
        self._pending_rows["asset_daily"].extend(asset_rows)
        self._pending_rows["product_daily"].extend(product_rows)
        self._session_rows["product_daily"].extend(product_rows)
        self._trim_session_rows("product_daily")
        self._pending_rows["global_macro_daily"].extend(global_macro_rows)
        self._pending_rows["forex_daily"].extend(forex_rows)
        self._pending_rows["phase_metric_daily"].extend(phase_metric_rows)
        if report_scope:
            self._pending_rows["company_daily"].extend(company_rows)
            self._pending_rows["country_daily"].extend(country_rows)
            # Full Save/Load refreshes current roots, but never creates daily
            # workforce facts between aggregation dates.
            self._pending_rows["country_workforce_monthly"].extend(
                row for row in workforce_rows if str(row[0]) == date_text and row[8] > 0
            )
            self._pending_rows["company_output_daily"].extend(company_output_rows)
            self._pending_rows["country_trade_daily"].extend(country_trade_rows)
            self._pending_rows["fund_allocation_daily"].extend(fund_allocation_rows)
        current_tables = {}
        if current_scope == "full":
            current_tables = {
                "asset_current": asset_rows,
                "product_current": product_rows,
                "company_current": company_rows,
                "company_output_current": company_output_rows,
                "country_trade_current": country_trade_rows,
                "fund_allocation_current": fund_allocation_rows,
                "country_current": country_rows,
                "country_workforce_current": workforce_rows,
                "global_macro_current": global_macro_rows,
                "forex_current": forex_rows,
                "portfolio_current": portfolio_rows,
                "news_current": news_rows,
                "event_current": event_rows,
                "phase_metric_current": phase_metric_rows,
                "country_politics_current": politics_rows,
        }
        if self._should_record_bonds(daten_module):
            bond_current_rows, bond_rows = self._bond_row_sets(daten_module, date_text)
            if "bond_current" not in self._current_rows or not _same_current_rows(self._current_rows.get("bond_current", []), bond_current_rows):
                changed_tables.add("bond_current")
            self._current_rows["bond_current"] = bond_current_rows
            self._pending_rows["bond_daily"].extend(bond_rows)
            self._session_rows["bond_daily"].extend(bond_rows)
            self._trim_session_rows("bond_daily")
            if current_tables:
                current_tables["bond_current"] = bond_current_rows
        self._current_dict_rows.clear()
        self._current_version += 1
        self._current_delta = SimulationDelta(
            self._current_version,
            date_text,
            frozenset(changed_tables),
        )
        self._replace_current_tables(current_tables)
        self._pending_rows["portfolio_daily"].extend(portfolio_rows)
        self._pending_rows["news_events"].extend(news_rows)
        self._pending_rows["event_log"].extend(event_rows)
        if flush or (self.auto_flush and len(self._pending_days) >= self.flush_interval_days):
            self.flush(defer=not flush and current_scope != "full")

    def flush(self, *, defer: bool = False) -> None:
        """Write all buffered daily rows to DuckDB."""

        if not self.enabled or self._connection is None:
            return
        if self._writer is not None:
            from kojakstreet.core.persistence_writer import BatchTooLarge, RowBatch

            self.check_persistence_health()
            if self._pending_rows:
                try:
                    self._writer.submit(self._pending_rows, self._current_rows, self._pending_days)
                except BatchTooLarge:
                    # Oversized batches keep the original durable publication
                    # barrier instead of growing the bounded journal/queue.
                    batch = RowBatch.freeze(0, self._history_id, self._pending_rows,
                                            self._current_rows, self._pending_days)
                    self._writer.call(lambda raw: EconomicDataStore._write_row_batch(batch, raw))
                self._pending_rows.clear()
                self._pending_days.clear()
            if not defer:
                self.wait_for_persistence()
            return
        if not self._pending_rows:
            return
        connection = self._connection
        connection.execute("BEGIN TRANSACTION")
        committed = False
        try:
            for table, rows in list(self._pending_rows.items()):
                self._replace_buffered_rows(table, rows)
            self._upsert_structural_events(self._pending_rows.get("event_log", []))
            self._compact_completed_history()
            for table, rows in self._current_rows.items():
                self._replace_current_rows(table, rows)
            connection.execute("COMMIT")
            committed = True
        except Exception as error:
            try:
                connection.execute("ROLLBACK")
            except Exception as rollback_error:  # noqa: BLE001 -- preserve ambiguous COMMIT failure
                error.add_note(f"Rollback also failed: {rollback_error}")
            raise
        finally:
            if committed:
                self._pending_rows.clear()
                self._pending_days.clear()

    def history_series(
        self,
        table: str,
        key_column: str,
        key: str,
        value_column: str,
        *,
        from_date: date | datetime | str | None = None,
        to_date: date | datetime | str | None = None,
        pixel_budget: int = DEFAULT_PIXEL_BUDGET,
        semantic_type: SemanticType | str = SemanticType.LEVEL,
    ) -> list[dict[str, object]]:
        """Return a bounded series spanning the requested available history."""

        if not self.enabled or self._connection is None:
            return []
        if self._pending_rows:
            self.flush()
        budget = max(2, min(MAX_PIXEL_BUDGET, int(pixel_budget)))
        semantic = SemanticType(str(semantic_type))
        entity = _history_entity(table, key_column, key)
        query_key = str(key).split(":", 1)[1] if table == "asset_daily" and ":" in str(key) else key
        bounds = self._connection.execute(
            f"SELECT min(date), max(date) FROM {_safe_identifier(table)} WHERE {_safe_identifier(key_column)} = ?",
            [query_key],
        ).fetchone()
        aggregate_bounds = self._connection.execute(
            "SELECT min(bucket_start), max(bucket_end) FROM history_aggregate WHERE source_table=? AND entity=? AND field=?",
            [table, entity, value_column],
        ).fetchone()
        starts = [item for item in ((bounds or (None, None))[0], (aggregate_bounds or (None, None))[0]) if item is not None]
        ends = [item for item in ((bounds or (None, None))[1], (aggregate_bounds or (None, None))[1]) if item is not None]
        if not starts or not ends:
            return []
        start = _coerce_date(from_date) if from_date is not None else min(starts)
        end = _coerce_date(to_date) if to_date is not None else max(ends)
        span_days = max(1, (end - start).days + 1)
        resolution = "raw" if span_days <= budget and span_days <= RAW_RETENTION_DAYS else ("monthly" if span_days <= budget * 31 else "yearly")
        if resolution == "monthly":
            available = self._connection.execute(
                "SELECT count(*) FROM history_aggregate WHERE source_table=? AND entity=? AND field=? AND semantic_type=? AND resolution='monthly'",
                [table, entity, value_column, semantic.value],
            ).fetchone()[0]
            if not available:
                resolution = "yearly"
        if resolution == "raw":
            rows = self._connection.execute(
                f"SELECT date, {_safe_identifier(value_column)} FROM {_safe_identifier(table)} WHERE {_safe_identifier(key_column)}=? AND date BETWEEN ? AND ? ORDER BY date",
                [query_key, start, end],
            ).fetchall()
            result = [{"date": str(day), "value": float(value), "open": float(value), "high": float(value), "low": float(value), "close": float(value), "resolution": "raw"} for day, value in rows if value is not None]
        else:
            value_expr = "sum_value" if semantic is SemanticType.FLOW else ("mean_value" if semantic is SemanticType.RATE else "close_value")
            rows = self._connection.execute(
                f"SELECT bucket_start, bucket_end, open_value, high_value, low_value, close_value, {value_expr} FROM history_aggregate WHERE source_table=? AND entity=? AND field=? AND semantic_type=? AND resolution=? AND bucket_end>=? AND bucket_start<=? ORDER BY bucket_start",
                [table, entity, value_column, semantic.value, resolution, start, end],
            ).fetchall()
            result = [
                {"date": str(bucket_end), "start": str(bucket_start), "value": float(value), "open": float(open_v), "high": float(high_v), "low": float(low_v), "close": float(close_v), "resolution": resolution}
                for bucket_start, bucket_end, open_v, high_v, low_v, close_v, value in rows
            ]
            if resolution == "monthly" and rows:
                first_monthly = _coerce_date(rows[0][0])
                yearly_rows = self._connection.execute(
                    f"SELECT bucket_start, bucket_end, open_value, high_value, low_value, close_value, {value_expr} FROM history_aggregate WHERE source_table=? AND entity=? AND field=? AND semantic_type=? AND resolution='yearly' AND bucket_end>=? AND bucket_end<? ORDER BY bucket_start",
                    [table, entity, value_column, semantic.value, start, first_monthly],
                ).fetchall()
                yearly_prefix = [
                    {"date": str(bucket_end), "start": str(bucket_start), "value": float(value), "open": float(open_v), "high": float(high_v), "low": float(low_v), "close": float(close_v), "resolution": "yearly"}
                    for bucket_start, bucket_end, open_v, high_v, low_v, close_v, value in yearly_rows
                ]
                result = yearly_prefix + result
            # Keep a dense recent tail so 1M/6M/1Y remain high resolution even
            # when the same payload also represents centuries in ALL/MAX.
            raw_tail_start = max(start, end - timedelta(days=519))
            tail = self._connection.execute(
                f"SELECT date, {_safe_identifier(value_column)} FROM {_safe_identifier(table)} WHERE {_safe_identifier(key_column)}=? AND date>=? AND date<=? ORDER BY date",
                [query_key, raw_tail_start, end],
            ).fetchall()
            if tail:
                result = [point for point in result if _coerce_date(point["date"]) < raw_tail_start]
            result.extend({"date": str(day), "value": float(value), "open": float(value), "high": float(value), "low": float(value), "close": float(value), "resolution": "raw"} for day, value in tail if value is not None)
        return _bounded_points(result, budget)

    def recent_series(self, table: str, key_column: str, key: str, value_column: str, limit: int = 520) -> list[float]:
        """Return a recent numeric series ordered from oldest to newest."""

        if not self.enabled or self._connection is None:
            return []
        safe_table = _safe_identifier(table)
        safe_key_column = _safe_identifier(key_column)
        safe_value_column = _safe_identifier(value_column)
        rows = self._connection.execute(
            f"""
            SELECT {safe_value_column}
            FROM (
                SELECT date, {safe_value_column}
                FROM {safe_table}
                WHERE {safe_key_column} = ?
                ORDER BY date DESC
                LIMIT ?
            )
            ORDER BY date ASC
            """,
            [key, int(limit)],
        ).fetchall()
        values = [(index, float(row[0])) for index, row in enumerate(rows) if row[0] is not None]
        pending = []
        for row in self._pending_rows.get(table, []):
            if len(row) <= 1:
                continue
            if str(row[_column_index(table, key_column)]) == str(key):
                pending.append((str(row[0]), _float(row[_column_index(table, value_column)])))
        if pending:
            offset = len(values)
            values.extend((offset + index, value) for index, (_date, value) in enumerate(sorted(pending)))
        return [value for _order, value in values[-limit:]]

    def session_series(self, table: str, key_column: str, key: str, value_column: str, limit: int = 520) -> list[float]:
        """Return values recorded since this runtime instance started."""

        rows = self._session_rows.get(table, [])
        if not rows:
            return []
        key_index = _column_index(table, key_column)
        value_index = _column_index(table, value_column)
        values = [
            (str(row[0]), _float(row[value_index]))
            for row in rows
            if len(row) > value_index and str(row[key_index]) == str(key)
        ]
        return [value for _date, value in sorted(values)[-limit:]]

    def asset_history(self, asset_type: str, ticker: str, limit: int = 520) -> list[tuple[float, str, str]]:
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT price
            FROM (
                SELECT date, price
                FROM asset_daily
                WHERE ticker = ? AND asset_type = ?
                ORDER BY date DESC
                LIMIT ?
            )
            ORDER BY date ASC
            """,
            [ticker, asset_type, int(limit)],
        ).fetchall()
        values = [float(row[0]) for row in rows if row[0] is not None]
        pending = []
        for row in self._pending_rows.get("asset_daily", []):
            if str(row[_column_index("asset_daily", "ticker")]) == str(ticker) and str(row[_column_index("asset_daily", "asset_type")]) == str(asset_type):
                pending.append((str(row[0]), _float(row[_column_index("asset_daily", "price")])))
        if pending:
            values.extend(value for _date, value in sorted(pending))
        return [(value, "", "") for value in values]

    def bond_history(self, symbol: str, limit: int = 520) -> list[tuple[float, str, str]]:
        values = self.recent_series("bond_daily", "symbol", symbol, "price", limit)
        return [(value, "", "") for value in values]

    def product_history(self, code: str, metric: str, limit: int = 520) -> list[float]:
        column = {
            "produced": "produced",
            "demanded": "demanded",
            "inventories": "inventories",
            "shortage": "shortage",
            "pressure": "pressure",
            "price": "price",
        }.get(metric, metric)
        return self.recent_series("product_daily", "code", code, column, limit)

    def forex_history(self, pair: str, limit: int = 520) -> list[float]:
        return self.recent_series("forex_daily", "pair", pair, "rate", limit)

    def country_history(self, region: str, metric: str, limit: int = 520) -> list[float]:
        column = {
            "inflation": "inflation",
            "growth": "growth",
            "unemployment": "unemployment",
            "rate": "rate",
            "gdp": "gdp",
            "trade_balance": "trade_balance",
            "import_dependency": "import_dependency",
            "export_strength": "export_strength",
            "debt_gdp": "debt_to_gdp",
            "debt_to_gdp": "debt_to_gdp",
            "credit": "credit_growth",
            "credit_growth": "credit_growth",
            "expected_growth": "expected_growth",
            "expected_inflation": "expected_inflation",
            "expected_rate": "expected_rate",
            "macro_surprise": "macro_surprise",
        }.get(metric, metric)
        return self.recent_series("country_daily", "region", region, column, limit)

    def asset_quote_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("asset_current", [])
        if cached:
            return self._current_dict_cache("asset_quote_rows", lambda: [
                {
                    "ticker": str(row[1]),
                    "asset_type": str(row[2]),
                    "price": _float(row[6]),
                    "change": _float(row[7]),
                    "market_cap": _float(row[8]),
                    "region": str(row[4]),
                }
                for row in cached
            ])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT ticker, asset_type, price, change_pct, market_cap, region
            FROM asset_current
            ORDER BY
                CASE asset_type
                    WHEN 'Stock' THEN 1
                    WHEN 'Commodity' THEN 2
                    WHEN 'Crypto' THEN 3
                    WHEN 'Fund' THEN 4
                    WHEN 'Index' THEN 5
                    ELSE 99
                END,
                ticker
            """
        ).fetchall()
        return [
            {
                "ticker": str(ticker),
                "asset_type": str(asset_type),
                "price": _float(price),
                "change": _float(change),
                "market_cap": _float(market_cap),
                "region": str(region),
            }
            for ticker, asset_type, price, change, market_cap, region in rows
        ]

    def product_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("product_current", [])
        if cached:
            return self._current_dict_cache("product_current", lambda: [_product_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT code, item_type, name, category, produced, demanded, inventories, shortage, pressure, price
            FROM product_current
            ORDER BY item_type, code
            """
        ).fetchall()
        return [_product_row_dict(row) for row in rows]

    def company_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("company_current", [])
        if cached:
            return self._current_dict_cache("company_current", lambda: [_company_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT ticker, name, region, sector, rating, price, market_cap, revenue, free_cash_flow,
                   production_capacity, capacity_utilization, production_score, input_availability,
                   supply_chain_shortage
            FROM company_current
            ORDER BY region, sector, ticker
            """
        ).fetchall()
        return [_company_row_dict((None, *row)) for row in rows]

    def company_output_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("company_output_current", [])
        if cached:
            return self._current_dict_cache("company_output_current", lambda: [_company_output_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT ticker, role, code, share, quantity
            FROM company_output_current
            ORDER BY ticker, role, code
            """
        ).fetchall()
        return [_company_output_row_dict((None, *row)) for row in rows]

    def country_trade_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("country_trade_current", [])
        if cached:
            return self._current_dict_cache("country_trade_current", lambda: [_country_trade_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT region, code, produced, demanded, exports, imports, net, shortage, pressure
            FROM country_trade_current
            ORDER BY region, code
            """
        ).fetchall()
        return [_country_trade_row_dict((None, *row)) for row in rows]

    def fund_allocation_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("fund_allocation_current", [])
        if cached:
            return self._current_dict_cache("fund_allocation_current", lambda: [_fund_allocation_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT fund_ticker, ticker, asset_type, weight
            FROM fund_allocation_current
            ORDER BY fund_ticker, weight DESC, ticker
            """
        ).fetchall()
        return [_fund_allocation_row_dict((None, *row)) for row in rows]

    def architecture_health(self) -> dict[str, int | bool]:
        return structured_store_health(self._current_rows)

    def portfolio_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("portfolio_current", [])
        if cached:
            return self._current_dict_cache("portfolio_current", lambda: [_portfolio_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT cash, net_worth, positions, futures
            FROM portfolio_current
            """
        ).fetchall()
        return [_portfolio_row_dict((None, *row)) for row in rows]

    def event_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("event_current", [])
        if cached:
            return self._current_dict_cache("event_current", lambda: [_event_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT event_type, scope, entity, summary, severity
            FROM event_current
            ORDER BY event_type, entity
            """
        ).fetchall()
        return [_event_row_dict((None, *row)) for row in rows]

    def structural_events(self, *, limit: int = 2000) -> list[dict[str, object]]:
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            "SELECT event_id, date, event_type, scope, entity, summary, severity, metadata_json FROM structural_event ORDER BY date, event_id LIMIT ?",
            [max(1, min(10000, int(limit)))],
        ).fetchall()
        return [
            {"event_id": str(event_id), "date": str(day), "event_type": str(event_type), "scope": str(scope), "entity": str(entity), "summary": str(summary), "severity": str(severity), "metadata": json.loads(metadata or "{}")}
            for event_id, day, event_type, scope, entity, summary, severity, metadata in rows
        ]

    def news_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("news_current", [])
        if cached:
            return self._current_dict_cache("news_current", lambda: [_news_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT date, body, category
            FROM news_current
            ORDER BY date DESC
            """
        ).fetchall()
        return [_news_row_dict(row) for row in rows]

    def phase_metric_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("phase_metric_current", [])
        if cached:
            return self._current_dict_cache("phase_metric_current", lambda: [_phase_metric_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT phase, duration_ms
            FROM phase_metric_current
            ORDER BY duration_ms DESC
            """
        ).fetchall()
        return [_phase_metric_row_dict((None, *row)) for row in rows]

    def country_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("country_current", [])
        if cached:
            return self._current_dict_cache("country_current", lambda: [_country_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT region, population, gdp, growth, rate, inflation, unemployment, rating,
                   trade_balance, import_dependency, export_strength, main_sector, main_bottleneck,
                   debt_to_gdp, credit_growth, expected_growth, expected_inflation, expected_rate, macro_surprise,
                   balance_sheet
            FROM country_current
            ORDER BY region
            """
        ).fetchall()
        return [_country_row_dict(row) for row in rows]

    def forex_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("forex_current", [])
        if cached:
            def build_forex_rows() -> list[dict[str, object]]:
                changes = self._pending_percent_changes("forex_daily", "pair", "rate")
                return [
                    {
                        "pair": str(row[1]),
                        "base": str(row[2]),
                        "quote": str(row[3]),
                        "rate": _float(row[4]),
                        "change": changes.get(str(row[1]), 0.0),
                    }
                    for row in cached
                ]

            return self._current_dict_cache("forex_current", build_forex_rows)
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT pair, base, quote, rate
            FROM forex_current
            ORDER BY pair
            """
        ).fetchall()
        return [
            {
                "pair": str(pair),
                "base": str(base),
                "quote": str(quote),
                "rate": _float(rate),
                "change": self._persisted_percent_change("forex_daily", "pair", str(pair), "rate"),
            }
            for pair, base, quote, rate in rows
        ]

    def bond_current_rows(self) -> list[dict[str, object]]:
        cached = self._current_rows.get("bond_current", [])
        if cached:
            return self._current_dict_cache("bond_current", lambda: [_bond_row_dict(row) for row in cached])
        if not self.enabled or self._connection is None:
            return []
        rows = self._connection.execute(
            """
            SELECT symbol, issuer, region, bond_type, price, yield, coupon, maturity_years, rating,
                   issuer_type, category, default_risk, liquidity, maturity_date, change_pct, duration
            FROM bond_current
            ORDER BY issuer_type, region, symbol
            """
        ).fetchall()
        return [
            {
                "symbol": str(symbol),
                "issuer": str(issuer),
                "region": str(region),
                "bond_type": str(bond_type),
                "price": _float(price),
                "yield": _float(yield_to_maturity),
                "coupon": _float(coupon),
                "maturity_years": _float(maturity_years),
                "rating": str(rating),
                "issuer_type": str(issuer_type),
                "category": str(category),
                "default_risk": _float(default_risk),
                "liquidity": _float(liquidity),
                "maturity_date": str(maturity_date),
                "change": _float(change_pct),
                "duration": _float(duration),
            }
            for (
                symbol,
                issuer,
                region,
                bond_type,
                price,
                yield_to_maturity,
                coupon,
                maturity_years,
                rating,
                issuer_type,
                category,
                default_risk,
                liquidity,
                maturity_date,
                change_pct,
                duration,
            ) in rows
        ]

    def _current_dict_cache(self, key: str, builder) -> list[dict[str, object]]:
        rows = self._current_dict_rows.get(key)
        if rows is None:
            rows = builder()
            self._current_dict_rows[key] = rows
        return rows

    def _pending_percent_change(self, table: str, key_column: str, key: str, value_column: str) -> float:
        values = [
            _float(row[_column_index(table, value_column)])
            for row in self._pending_rows.get(table, [])
            if str(row[_column_index(table, key_column)]) == str(key)
        ]
        if len(values) < 2 or not values[-2]:
            return 0.0
        return ((values[-1] - values[-2]) / values[-2]) * 100.0

    def _pending_percent_changes(self, table: str, key_column: str, value_column: str) -> dict[str, float]:
        grouped: dict[str, list[float]] = defaultdict(list)
        key_index = _column_index(table, key_column)
        value_index = _column_index(table, value_column)
        for row in self._pending_rows.get(table, []):
            grouped[str(row[key_index])].append(_float(row[value_index]))
        changes = {}
        for key, values in grouped.items():
            if len(values) >= 2 and values[-2]:
                changes[key] = ((values[-1] - values[-2]) / values[-2]) * 100.0
            else:
                changes[key] = 0.0
        return changes

    def _persisted_percent_change(self, table: str, key_column: str, key: str, value_column: str) -> float:
        values = self.recent_series(table, key_column, key, value_column, 2)
        if len(values) < 2 or not values[-2]:
            return 0.0
        return ((values[-1] - values[-2]) / values[-2]) * 100.0

    def _create_schema(self) -> None:
        assert self._connection is not None
        create_schema(self._connection)

    def _ensure_history_metadata(self) -> str:
        assert self._connection is not None
        existing = self._connection.execute("SELECT value FROM history_metadata WHERE key='history_id'").fetchone()
        history_id = str(existing[0]) if existing else str(uuid.uuid4())
        previous = dict(self._connection.execute(
            "SELECT key, value FROM history_metadata WHERE key IN ('economic_model_version', 'history_schema_version')"
        ).fetchall())
        for key, value in previous.items():
            current = ECONOMIC_MODEL_VERSION if key == "economic_model_version" else str(HISTORY_SCHEMA_VERSION)
            if value != current:
                self._connection.execute(
                    "INSERT INTO history_metadata SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM history_metadata WHERE key=?)",
                    [f"origin_{key}", value, f"origin_{key}"],
                )
        values = {
            "history_id": history_id,
            "history_schema_version": str(HISTORY_SCHEMA_VERSION),
            "economic_model_version": ECONOMIC_MODEL_VERSION,
        }
        for key, value in values.items():
            self._connection.execute("DELETE FROM history_metadata WHERE key=?", [key])
            self._connection.execute("INSERT INTO history_metadata VALUES (?, ?)", [key, value])
        return history_id

    def _trim_session_rows(self, table: str) -> None:
        rows = self._session_rows.get(table, [])
        dates = sorted({str(row[0]) for row in rows})
        if len(dates) <= 520:
            return
        keep = set(dates[-520:])
        self._session_rows[table] = [row for row in rows if str(row[0]) in keep]

    def _compact_completed_history(self) -> None:
        assert self._connection is not None
        row = self._connection.execute("SELECT max(date) FROM asset_daily").fetchone()
        if not row or row[0] is None:
            return
        reference = _coerce_date(row[0])
        completed_month = date(reference.year, reference.month, 1) - timedelta(days=1)
        completed_year = date(reference.year - 1, 12, 31)
        for resolution, completed in (
            ("monthly", completed_month),
            ("yearly", completed_year),
        ):
            if completed.year < 1:
                continue
            marker_key = f"last_{resolution}_compaction"
            marker_row = self._connection.execute("SELECT value FROM history_metadata WHERE key=?", [marker_key]).fetchone()
            since = _coerce_date(marker_row[0]) if marker_row else None
            if since is not None and since >= completed:
                continue
            specs = _HISTORY_SPECS + (_YEARLY_ONLY_SPECS if resolution == "yearly" else [])
            for spec in specs:
                self._aggregate_spec(spec, resolution, completed, since)
            self._connection.execute("DELETE FROM history_metadata WHERE key=?", [marker_key])
            self._connection.execute("INSERT INTO history_metadata VALUES (?, ?)", [marker_key, completed.isoformat()])
        raw_cutoff = reference - timedelta(days=RAW_RETENTION_DAYS)
        raw_tables = {spec[0] for spec in (*_HISTORY_SPECS, *_YEARLY_ONLY_SPECS)} | {
            "company_output_daily", "fund_allocation_daily", "news_events", "event_log", "phase_metric_daily"
        }
        for table in raw_tables:
            self._connection.execute(
                f"DELETE FROM {_safe_identifier(table)} WHERE date < DATE '{raw_cutoff.isoformat()}'"
            )
        monthly_cutoff = date(max(1, reference.year - 20), 1, 1)
        self._connection.execute(
            "DELETE FROM history_aggregate WHERE resolution='monthly' "
            f"AND bucket_end < DATE '{monthly_cutoff.isoformat()}'",
        )

    def _aggregate_spec(self, spec: tuple[str, str, str, str], resolution: str, completed: date, since: date | None) -> None:
        assert self._connection is not None
        table, entity_expression, field, semantic = spec
        safe_table = _safe_identifier(table)
        safe_field = _safe_identifier(field)
        semantic = SemanticType(semantic).value
        if resolution not in {"monthly", "yearly"}:
            raise ValueError(f"Unknown history resolution: {resolution}")
        bucket_start = "date_trunc('month', date)::DATE" if resolution == "monthly" else "make_date(year(date), 1, 1)"
        bucket_end = "last_day(date)" if resolution == "monthly" else "make_date(year(date), 12, 31)"
        lower_bound = since or date(1, 1, 1)
        sum_expression = f"sum({safe_field})" if semantic == SemanticType.FLOW.value else "0.0"
        # These are validated schema identifiers, enum values and date objects,
        # not external SQL text. Literal constants avoid six Python parameter
        # conversions (and optional pandas probes) for every aggregation spec.
        self._connection.execute(
            f"""
            INSERT INTO history_aggregate
            SELECT '{safe_table}', CAST({entity_expression} AS VARCHAR) AS entity,
                   '{safe_field}', '{semantic}', '{resolution}',
                   {bucket_start} AS bucket_start, {bucket_end} AS bucket_end,
                   arg_min({safe_field}, date), max({safe_field}), min({safe_field}), arg_max({safe_field}, date),
                   avg({safe_field}), {sum_expression}, count({safe_field})
            FROM {safe_table}
            WHERE date <= DATE '{completed.isoformat()}'
              AND date > DATE '{lower_bound.isoformat()}' AND {safe_field} IS NOT NULL
            GROUP BY bucket_start, bucket_end, entity
            """,
        )

    def _upsert_structural_events(self, rows: list[tuple[Any, ...]]) -> None:
        assert self._connection is not None
        durable_types = {"default", "new_company", "crypto_shutdown", "central_bank", "rating_migration", "distress", "recovery"}
        for day, event_type, scope, entity, summary, severity in rows:
            if str(event_type) not in durable_types:
                continue
            identity = "|".join(map(str, (day, event_type, scope, entity, summary)))
            event_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            self._connection.execute("DELETE FROM structural_event WHERE event_id=?", [event_id])
            self._connection.execute(
                "INSERT INTO structural_event VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [event_id, day, event_type, scope, entity, summary, severity, json.dumps({}, separators=(",", ":"))],
            )

    def _migrate_schema(self) -> None:
        assert self._connection is not None
        migrate_schema(self._connection)

    def _replace_rows(self, table: str, date_text: str, rows: list[tuple[Any, ...]]) -> None:
        assert self._connection is not None
        self._connection.execute(f"DELETE FROM {_safe_identifier(table)} WHERE date = ?", [date_text])
        if not rows:
            return
        self._insert_rows(table, rows)

    def _replace_news(self, date_text: str, rows: list[tuple[Any, ...]]) -> None:
        assert self._connection is not None
        self._connection.execute("DELETE FROM news_events WHERE date = ?", [date_text])
        if rows:
            self._insert_rows("news_events", rows)

    def _replace_buffered_rows(self, table: str, rows: list[tuple[Any, ...]]) -> None:
        assert self._connection is not None
        if not rows:
            return
        if table in {"politics_events", "country_politics_monthly"}:
            # Sparse facts are identity-upserted, never date-wide deleted: an
            # election replay must not erase a different country's same-day event.
            indices = (1,) if table == "politics_events" else (0, 1)
            unique = {tuple(row[i] for i in indices): row for row in rows}
            if table == "politics_events":
                # One statement, with safely quoted internal text values. Large
                # Python-list parameters reintroduce per-element driver probes.
                identities = ", ".join("'" + str(key[0]).replace("'", "''") + "'" for key in unique)
                self._connection.execute(
                    f"DELETE FROM politics_events WHERE event_id IN ({identities})"
                )
            else:
                try:
                    canonical = [(date.fromisoformat(str(key[0])).isoformat(),
                                  str(key[1]).replace("'", "''")) for key in unique]
                except ValueError:
                    self._connection.execute(
                        "DELETE FROM country_politics_monthly WHERE (date, region) IN "
                        "(SELECT CAST(unnest(?) AS DATE), unnest(?))",
                        [[str(key[0]) for key in unique], [key[1] for key in unique]],
                    )
                else:
                    identities = ", ".join(f"(DATE '{when}', '{region}')" for when, region in canonical)
                    self._connection.execute(
                        "DELETE FROM country_politics_monthly WHERE (date, region) "
                        f"IN (VALUES {identities})"
                    )
            self._insert_rows(table, list(unique.values()))
            return
        safe_table = _safe_identifier(table)
        dates = sorted({str(row[0]) for row in rows})
        # Canonical ISO dates are internal schema values, not arbitrary SQL.
        # Avoid DuckDB's repeated optional-import probes for Python parameters.
        # Other input formats retain the original bound conversion/error path.
        try:
            canonical = all(date.fromisoformat(value).isoformat() == value for value in dates)
        except ValueError:
            canonical = False
        if canonical:
            literals = ", ".join(f"DATE '{value}'" for value in dates)
            self._connection.execute(f"DELETE FROM {safe_table} WHERE date IN ({literals})")
        else:
            placeholders = ", ".join("?" for _ in dates)
            self._connection.execute(f"DELETE FROM {safe_table} WHERE date IN ({placeholders})", dates)
        self._insert_rows(table, rows)

    def _replace_current_rows(self, table: str, rows: list[tuple[Any, ...]]) -> None:
        assert self._connection is not None
        safe_table = _safe_identifier(table)
        self._connection.execute(f"DELETE FROM {safe_table}")
        if rows:
            self._insert_rows(table, rows)

    def _replace_current_tables(self, tables: dict[str, list[tuple[Any, ...]]]) -> None:
        assert self._connection is not None
        if not tables:
            return
        self._connection.execute("BEGIN TRANSACTION")
        try:
            for table, rows in tables.items():
                self._replace_current_rows(table, rows)
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def _drop_pending_date(self, date_text: str) -> None:
        for table, rows in list(self._pending_rows.items()):
            if table in {"politics_events", "country_politics_monthly"}:
                continue
            self._pending_rows[table] = [row for row in rows if str(row[0]) != date_text]
        self._pending_days.discard(date_text)

    def _insert_rows(self, table: str, rows: list[tuple[Any, ...]]) -> None:
        assert self._connection is not None
        if not rows:
            return
        safe_table = _safe_identifier(table)
        text_rows = table in {"news_events", "news_current", "event_log", "event_current"}
        if text_rows and any(
            type(value) not in (str, type(None), date, datetime) for row in rows for value in row
        ):
            placeholders = ", ".join("?" for _ in rows[0])
            self._connection.executemany(f"INSERT INTO {safe_table} VALUES ({placeholders})", rows)
            return
        temp_path = None
        parameter_rows = text_rows or table in {
            "phase_metric_daily", "phase_metric_current",
            "country_workforce_monthly", "country_workforce_current",
            "country_politics_snapshot", "country_politics_current", "country_politics_monthly", "politics_events",
        }
        try:
            with tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8") as handle:
                temp_path = Path(handle.name)
                if parameter_rows:
                    self._write_parameter_csv(handle, rows)
                else:
                    writer = csv.writer(handle)
                    writer.writerows(rows)
            sql_path = str(temp_path).replace("'", "''")
            null_options = ", ALLOW_QUOTED_NULLS FALSE" if parameter_rows else ""
            self._connection.execute(
                f"COPY {safe_table} FROM '{sql_path}' "
                "(FORMAT CSV, HEADER FALSE, DELIM ',', QUOTE '\"', ESCAPE '\"', NULL '\\N'"
                f"{null_options})"
            )
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _write_parameter_csv(self, handle, rows: list[tuple[Any, ...]]) -> None:
        """Batch small parameter tables without per-cell optional-import probes.

        Only None is an unquoted NULL marker. Quoting every non-null value also
        preserves empty strings, literal \\N, quotes, newlines and Unicode.
        DuckDB's target schema retains the existing DATE/VARCHAR/DOUBLE types.
        """
        for row in rows:
            handle.write(
                ",".join(
                    "\\N" if value is None else '"' + str(value).replace('"', '""') + '"'
                    for value in row
                )
                + "\n"
            )

    def _asset_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows: list[tuple[Any, ...]] = []
        for asset_type, ticker, asset, name, region, sector in _asset_row_sources(daten_module):
            rows.append(
                (
                    date_text,
                    ticker,
                    asset_type,
                    name,
                    region,
                    sector,
                    _float(asset.get("kurs", asset.get("price", 0.0))),
                    _float(asset.get("aenderung", 0.0)),
                    _float(asset.get("market_cap", asset.get("aum", 0.0))),
                    _float(asset.get("revenue", 0.0)),
                    _float(asset.get("free_cash_flow", 0.0)),
                    str(asset.get("rating", "")),
                )
            )
        return rows

    def _product_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows: list[tuple[Any, ...]] = []
        for item_type, code, data, name, category in _product_row_sources(daten_module):
            rows.append(
                (
                    date_text,
                    code,
                    item_type,
                    name,
                    category,
                    _float(data.get("supply", data.get("production", data.get("foerder_menge", 0.0)))),
                    _float(data.get("demand", 0.0)),
                    _float(data.get("inventories", 0.0)),
                    _float(data.get("shortage", 0.0)),
                    _float(data.get("price_pressure", 0.0)),
                    _float(data.get("kurs", data.get("price_index", 0.0))),
                )
            )
        return rows

    def _company_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows = []
        for ticker, asset in getattr(daten_module, "aktien", {}).items():
            rows.append(
                (
                    date_text,
                    str(ticker),
                    str(asset.get("name", ticker)),
                    str(asset.get("land", "")),
                    str(asset.get("branche", "")),
                    str(asset.get("rating", "")),
                    _float(asset.get("kurs", 0.0)),
                    _float(asset.get("market_cap", 0.0)),
                    _float(asset.get("revenue", 0.0)),
                    _float(asset.get("free_cash_flow", 0.0)),
                    _float(asset.get("production_capacity", 0.0)),
                    _float(asset.get("capacity_utilization", 0.0)),
                    _float(asset.get("production_score", 0.0)),
                    _float(asset.get("input_availability", 0.0)),
                    _float(asset.get("supply_chain_shortage", 0.0)),
                )
            )
        return rows

    def _company_output_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows = []
        for ticker, asset in getattr(daten_module, "aktien", {}).items():
            capacity = max(0.0, _float(asset.get("production_capacity", 0.0)))
            for code, share in _normalized_mapping(asset.get("output_mix") or {asset.get("specialization", ""): 1.0}).items():
                if code:
                    rows.append((date_text, str(ticker), "Produces", code, share, capacity * share))
            input_requirements = asset.get("company_input_history", {})
            for code, history in input_requirements.items():
                value = _last_history_value(history.get("history", []) if isinstance(history, dict) else [])
                if value is not None:
                    rows.append((date_text, str(ticker), "Needs", str(code), 0.0, value))
        return rows

    def _country_trade_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows = []
        for region, macro in getattr(daten_module, "makro", {}).items():
            supply = macro.get("regional_supply", {})
            demand = macro.get("regional_demand", {})
            exports = macro.get("exports", {})
            imports = macro.get("imports", {})
            shortages = macro.get("regional_shortage", {})
            pressures = macro.get("regional_pressure", {})
            for code in sorted(set(supply) | set(demand) | set(exports) | set(imports)):
                export_value = _float(exports.get(code, 0.0))
                import_value = _float(imports.get(code, 0.0))
                rows.append(
                    (
                        date_text,
                        str(region),
                        str(code),
                        _float(supply.get(code, 0.0)),
                        _float(demand.get(code, 0.0)),
                        export_value,
                        import_value,
                        export_value - import_value,
                        _float(shortages.get(code, 0.0)),
                        _float(pressures.get(code, 0.0)),
                    )
                )
        return rows

    def _fund_allocation_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows = []
        for fund_ticker, fund in getattr(daten_module, "fonds", {}).items():
            for holding in fund.get("underlyings", []):
                rows.append(
                    (
                        date_text,
                        str(fund_ticker),
                        str(holding.get("ticker", "")),
                        str(holding.get("asset_type", "")),
                        _float(holding.get("weight", 0.0)),
                    )
                )
        return rows

    def _country_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows = []
        for region, macro in getattr(daten_module, "makro", {}).items():
            rows.append(
                (
                    date_text,
                    str(region),
                    _float(macro.get("bevoelkerung", 0.0)),
                    _float(macro.get("bip_abs", 0.0)),
                    _float(macro.get("bip_prozent", 0.0)),
                    _float(macro.get("zins", 0.0)),
                    _float(macro.get("inflation", 0.0)),
                    _float(macro.get("arbeitslosigkeit", 0.0)),
                    str(macro.get("rating", "")),
                    _float(macro.get("trade_balance", 0.0)),
                    _float(macro.get("import_dependency", 0.0)),
                    _float(macro.get("export_strength", 0.0)),
                    str(macro.get("main_sector", "")),
                    str(macro.get("main_bottleneck", "")),
                    _float(macro.get("debt_to_gdp", 0.0)),
                    _float(macro.get("credit_growth", 0.0)),
                    _float(macro.get("expected_growth", macro.get("bip_prozent", 0.0))),
                    _float(macro.get("expected_inflation", macro.get("inflation", 0.0))),
                    _float(macro.get("expected_rate", macro.get("zins", 0.0))),
                    _float(macro.get("macro_surprise_momentum", 0.0)),
                    _float(macro.get("balance_sheet", 0.0)),
                )
            )
        return rows

    def _workforce_rows(self, daten_module) -> list[tuple[Any, ...]]:
        from kojakstreet.core.workforce import POOLS

        rows = []
        for region, macro in getattr(daten_module, "makro", {}).items():
            wf = macro.get("workforce")
            if not wf:
                continue
            has_interval = wf["population_interval_years"] > 0
            rows.append((
                wf["last_aggregation_date"], str(region), wf["model_version"], wf["activated_on"],
                float(macro["bevoelkerung"]), macro["birth_rate"], macro["death_rate"],
                macro.get("population_growth") if has_interval else None,
                wf["population_interval_years"], wf["population_interval_end"],
                wf["population_growth_annualized"] if has_interval else None,
                *(wf[metric][pool] for pool in POOLS for metric in ("supply", "demand", "coverage", "shortage")),
            ))
        return rows

    def _global_macro_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        return [
            (date_text, str(metric), _float(value))
            for metric, value in getattr(daten_module, "global_macro", {}).items()
            if isinstance(value, (int, float))
        ]

    def _forex_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows = []
        histories = getattr(daten_module, "FOREX_PAARE_HISTORIE", {})
        for pair, base, quote in _forex_row_sources(daten_module):
            history = histories.get(pair, [])
            rate = _last_history_value(history)
            if rate is None:
                continue
            rows.append((date_text, pair, base, quote, rate))
        return rows

    def _bond_rows(self, daten_module, date_text: str, *, only_updated: bool = False) -> list[tuple[Any, ...]]:
        current_rows, updated_rows = self._bond_row_sets(daten_module, date_text)
        return updated_rows if only_updated else current_rows

    def _bond_row_sets(
        self,
        daten_module,
        date_text: str,
    ) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
        current_rows = []
        updated_rows = []
        record_ordinal = _coerce_date(date_text).toordinal()
        for bond in getattr(daten_module, "bond_market", []):
            issuer_type = str(bond.get("issuer_type", bond.get("typ", bond.get("bond_type", ""))))
            category = str(bond.get("category", issuer_type))
            row = (
                date_text,
                str(bond.get("symbol", bond.get("ticker", ""))),
                str(bond.get("issuer", bond.get("ticker", ""))),
                str(bond.get("land", bond.get("region", ""))),
                issuer_type,
                _float(bond.get("price", bond.get("kurs", 0.0))),
                _float(bond.get("yield_to_maturity", bond.get("yield", bond.get("rendite", 0.0)))),
                _float(bond.get("coupon", bond.get("zins", 0.0))),
                _float(bond.get("maturity_years", bond.get("term_years", bond.get("laufzeit", 0.0)))),
                str(bond.get("rating", "")),
                issuer_type,
                category,
                _float(bond.get("default_risk", 0.0)),
                _float(bond.get("liquidity", 0.0)),
                _date_text(bond.get("maturity_date", "")),
                _float(bond.get("aenderung", 0.0)),
                _float(bond.get("duration", 0.0)),
            )
            current_rows.append(row)
            if int(bond.get("last_price_update_ordinal", -1) or -1) == record_ordinal:
                updated_rows.append(row)
        return current_rows, updated_rows

    def _should_record_bonds(self, daten_module) -> bool:
        record_date = getattr(daten_module, "last_completed_simulation_date", getattr(daten_module, "datum", None))
        if not hasattr(record_date, "toordinal"):
            return True
        last_update = getattr(daten_module, "last_bond_market_update_ordinal", None)
        return last_update is None or int(last_update) == record_date.toordinal()

    def _portfolio_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        net_worth = _last_history_value(getattr(daten_module, "DEPOT_VERMOEGEN_HISTORIE", []))
        cash = _float(getattr(daten_module, "bargeld", 0.0)) + _float(getattr(daten_module, "forex_depot", {}).get("GD", 0.0))
        return [
            (
                date_text,
                cash,
                net_worth if net_worth is not None else cash,
                len(getattr(daten_module, "depot", {})),
                len(getattr(daten_module, "perpetuals", {})),
            )
        ]

    def _news_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows = []
        for raw in visible_news(daten_module):
            if len(raw) < 3:
                continue
            item_date, body, category = raw[:3]
            if _date_text(item_date) == date_text:
                rows.append((date_text, str(body), str(category)))
        return rows

    def _event_rows(self, news_rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        return [
            (
                row[0],
                _event_type(str(row[1])),
                _event_scope(str(row[1])),
                _event_entity(str(row[1])),
                str(row[1]),
                _event_severity(str(row[2])),
            )
            for row in news_rows
        ]

    def _phase_metric_rows(self, daten_module, date_text: str) -> list[tuple[Any, ...]]:
        rows = []
        for item in getattr(daten_module, "simulation_phase_timings", []):
            if not isinstance(item, dict):
                continue
            rows.append((date_text, str(item.get("phase", "")), _float(item.get("duration_ms", 0.0))))
        return rows


def _date_text(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value)
    if len(text) == 10 and text[2] == "." and text[5] == ".":
        day, month, year = text.split(".")
        return f"{year}-{month}-{day}"
    return text


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _same_current_rows(current_rows: list[tuple[Any, ...]], next_rows: list[tuple[Any, ...]]) -> bool:
    if len(current_rows) != len(next_rows):
        return False
    return all(tuple(current[1:]) == tuple(next_row[1:]) for current, next_row in zip(current_rows, next_rows))


def _asset_row_sources(daten_module) -> list[tuple[str, str, dict, str, str, str]]:
    universes = (
        ("Stock", getattr(daten_module, "aktien", {})),
        ("Commodity", getattr(daten_module, "rohstoffe", {})),
        ("Crypto", getattr(daten_module, "kryptos", {})),
        ("Fund", getattr(daten_module, "fonds", {})),
        ("Index", getattr(daten_module, "indizes", {})),
        ("Derivative", getattr(daten_module, "derivatives", {})),
    )
    signature = tuple((asset_type, tuple(assets.keys())) for asset_type, assets in universes)
    cache = getattr(daten_module, "_asset_row_source_cache", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["sources"]
    sources: list[tuple[str, str, dict, str, str, str]] = []
    for asset_type, assets in universes:
        for ticker, asset in assets.items():
            ticker_text = str(ticker)
            sources.append(
                (
                    asset_type,
                    ticker_text,
                    asset,
                    str(asset.get("name", asset.get("issuer", ticker_text))),
                    str(asset.get("land", "GD")),
                    str(asset.get("branche", asset.get("kategorie", asset.get("fund_type", "")))),
                )
            )
    daten_module._asset_row_source_cache = {"signature": signature, "sources": sources}
    return sources


def _product_row_sources(daten_module) -> list[tuple[str, str, dict, str, str]]:
    universes = (
        ("Commodity", getattr(daten_module, "rohstoffe", {})),
        ("Processed Product", getattr(daten_module, "processed_products", {})),
    )
    signature = tuple((item_type, tuple(products.keys())) for item_type, products in universes)
    cache = getattr(daten_module, "_product_row_source_cache", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["sources"]
    sources: list[tuple[str, str, dict, str, str]] = []
    for item_type, products in universes:
        for code, data in products.items():
            code_text = str(code)
            sources.append(
                (
                    item_type,
                    code_text,
                    data,
                    str(data.get("name", code_text)),
                    str(data.get("kategorie", data.get("category", ""))),
                )
            )
    daten_module._product_row_source_cache = {"signature": signature, "sources": sources}
    return sources


def _forex_row_sources(daten_module) -> list[tuple[str, str, str]]:
    histories = getattr(daten_module, "FOREX_PAARE_HISTORIE", {})
    signature = tuple(histories.keys())
    cache = getattr(daten_module, "_forex_row_source_cache", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["sources"]
    sources = []
    for pair in histories:
        pair_text = str(pair)
        base, quote = _split_pair(pair_text)
        sources.append((pair_text, base, quote))
    daten_module._forex_row_source_cache = {"signature": signature, "sources": sources}
    return sources


def _last_history_value(history: Iterable[Any]) -> float | None:
    if not history:
        return None
    try:
        entry = history[-1]  # type: ignore[index]
    except (TypeError, KeyError):
        values = list(history)
        if not values:
            return None
        entry = values[-1]
    if isinstance(entry, (tuple, list)) and entry:
        return _float(entry[0])
    return _float(entry)


def _split_pair(pair: str) -> tuple[str, str]:
    if "/" in pair:
        base, quote = pair.split("/", 1)
        return base, quote
    if "_" in pair:
        base, quote = pair.split("_", 1)
        return base, quote
    return pair[:3], pair[3:]


def _is_monthly_current_refresh_day(value: Any) -> bool:
    return bool(hasattr(value, "day") and int(value.day) in {1, 15, 16})


def _is_macro_report_day(value: Any) -> bool:
    return bool(hasattr(value, "day") and int(value.day) == 15)


def _product_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "code": str(row[1]),
        "type": str(row[2]),
        "name": str(row[3]),
        "category": str(row[4]),
        "produced": _float(row[5]),
        "demanded": _float(row[6]),
        "inventories": _float(row[7]),
        "shortage": _float(row[8]),
        "pressure": _float(row[9]),
        "price": _float(row[10]),
    }


def _country_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    offset = 1 if len(row) >= 21 else 0
    return {
        "region": str(row[offset + 0]),
        "population": _float(row[offset + 1]),
        "gdp": _float(row[offset + 2]),
        "growth": _float(row[offset + 3]),
        "rate": _float(row[offset + 4]),
        "inflation": _float(row[offset + 5]),
        "unemployment": _float(row[offset + 6]),
        "rating": str(row[offset + 7]),
        "trade_balance": _float(row[offset + 8]),
        "import_dependency": _float(row[offset + 9]),
        "export_strength": _float(row[offset + 10]),
        "main_sector": str(row[offset + 11]),
        "main_bottleneck": str(row[offset + 12]),
        "debt_to_gdp": _float(row[offset + 13] if len(row) > offset + 13 else 0.0),
        "credit_growth": _float(row[offset + 14] if len(row) > offset + 14 else 0.0),
        "expected_growth": _float(row[offset + 15] if len(row) > offset + 15 else row[offset + 3]),
        "expected_inflation": _float(row[offset + 16] if len(row) > offset + 16 else row[offset + 5]),
        "expected_rate": _float(row[offset + 17] if len(row) > offset + 17 else row[offset + 4]),
        "macro_surprise": _float(row[offset + 18] if len(row) > offset + 18 else 0.0),
        "balance_sheet": _float(row[offset + 19] if len(row) > offset + 19 else 0.0),
    }


def _bond_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "symbol": str(row[1]),
        "issuer": str(row[2]),
        "region": str(row[3]),
        "bond_type": str(row[4]),
        "price": _float(row[5]),
        "yield": _float(row[6]),
        "coupon": _float(row[7]),
        "maturity_years": _float(row[8]),
        "rating": str(row[9]),
        "issuer_type": str(row[10] if len(row) > 10 else row[4]),
        "category": str(row[11] if len(row) > 11 else row[4]),
        "default_risk": _float(row[12] if len(row) > 12 else 0.0),
        "liquidity": _float(row[13] if len(row) > 13 else 0.0),
        "maturity_date": str(row[14] if len(row) > 14 else ""),
        "change": _float(row[15] if len(row) > 15 else 0.0),
        "duration": _float(row[16] if len(row) > 16 else row[8]),
    }


def _portfolio_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "cash": _float(row[1]),
        "net_worth": _float(row[2]),
        "positions": int(row[3] or 0),
        "futures": int(row[4] or 0),
    }


def _company_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "ticker": str(row[1]),
        "name": str(row[2]),
        "region": str(row[3]),
        "sector": str(row[4]),
        "rating": str(row[5]),
        "price": _float(row[6]),
        "market_cap": _float(row[7]),
        "revenue": _float(row[8]),
        "free_cash_flow": _float(row[9]),
        "production_capacity": _float(row[10]),
        "capacity_utilization": _float(row[11]),
        "production_score": _float(row[12]),
        "input_availability": _float(row[13]),
        "supply_chain_shortage": _float(row[14]),
    }


def _company_output_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "ticker": str(row[1]),
        "role": str(row[2]),
        "code": str(row[3]),
        "share": _float(row[4]),
        "quantity": _float(row[5]),
    }


def _country_trade_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "region": str(row[1]),
        "code": str(row[2]),
        "produced": _float(row[3]),
        "demanded": _float(row[4]),
        "exports": _float(row[5]),
        "imports": _float(row[6]),
        "net": _float(row[7]),
        "shortage": _float(row[8]),
        "pressure": _float(row[9]),
    }


def _fund_allocation_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "fund_ticker": str(row[1]),
        "ticker": str(row[2]),
        "asset_type": str(row[3]),
        "weight": _float(row[4]),
    }


def _event_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "event_type": str(row[1]),
        "scope": str(row[2]),
        "entity": str(row[3]),
        "summary": str(row[4]),
        "severity": str(row[5]),
    }


def _news_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "date": str(row[0]),
        "body": str(row[1]),
        "category": str(row[2]),
    }


def _phase_metric_row_dict(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "phase": str(row[1]),
        "duration_ms": _float(row[2]),
    }


def _event_type(text: str) -> str:
    upper = text.upper()
    if "INSOLVENCY" in upper or "DEFAULT" in upper:
        return "default"
    if "IPO" in upper:
        return "new_company"
    if "CRYPTO SHUTDOWN" in upper:
        return "crypto_shutdown"
    if "RATING" in upper and any(token in upper for token in ("UPGRADE", "DOWNGRADE", "MIGRATION")):
        return "rating_migration"
    if "DISTRESS" in upper:
        return "distress"
    if "RECOVER" in upper:
        return "recovery"
    if "CAPACITY TREND" in upper:
        return "capacity_trend"
    if "SECTOR MOMENTUM" in upper:
        return "sector_momentum"
    if "COUNTRY" in upper or "TRADE FLOW" in upper:
        return "country_trade"
    if "CENTRAL" in upper or "POLICY" in upper or "ZENTRALBANK" in upper:
        return "central_bank"
    if "MARGIN CALL" in upper:
        return "portfolio_risk"
    return "market_news"


def _event_scope(text: str) -> str:
    event_type = _event_type(text)
    if event_type in {"country_trade", "central_bank"}:
        return "country"
    if event_type in {"new_company", "default", "capacity_trend", "sector_momentum", "rating_migration", "distress", "recovery"}:
        return "company"
    if event_type == "crypto_shutdown":
        return "crypto"
    if event_type == "portfolio_risk":
        return "portfolio"
    return "market"


def _event_entity(text: str) -> str:
    cleaned = text.strip()
    if ":" in cleaned:
        head, tail = cleaned.split(":", 1)
        words = tail.strip().split()
        return words[0].strip(",.;") if words else head.strip()
    return cleaned.split()[0].strip(",.;") if cleaned.split() else ""


def _event_severity(category: str) -> str:
    upper = category.upper()
    if upper in {"ROT", "CRITICAL", "HIGH"}:
        return "negative"
    if upper in {"GRUEN", "GREEN", "POSITIVE"}:
        return "positive"
    if upper in {"ZENTRALBANK", "CENTRAL BANK"}:
        return "policy"
    return "neutral"


def _normalized_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    cleaned = {str(key): max(0.0, _float(raw)) for key, raw in value.items() if key and _float(raw) > 0.0}
    total = sum(cleaned.values())
    if total <= 0:
        return {}
    return {key: raw / total for key, raw in cleaned.items()}


def _safe_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _specs(table: str, entity_expression: str, fields: dict[str, SemanticType]) -> list[tuple[str, str, str, str]]:
    return [(table, entity_expression, field, semantic.value) for field, semantic in fields.items()]


_HISTORY_SPECS = [
    *_specs("country_workforce_monthly", "region", {
        **{f"{pool}_{metric}": SemanticType.LEVEL if metric in {"supply", "demand"} else SemanticType.RATE
           for pool in ("basic", "skilled", "highly_qualified")
           for metric in ("supply", "demand", "coverage", "shortage")},
        "population_growth_annualized": SemanticType.RATE,
    }),
    *_specs("asset_daily", "asset_type || ':' || ticker", {
        "price": SemanticType.PRICE,
    }),
    *_specs("product_daily", "code", {
        "produced": SemanticType.LEVEL,
        "demanded": SemanticType.LEVEL,
        "inventories": SemanticType.LEVEL,
        "shortage": SemanticType.RATE,
        "pressure": SemanticType.RATE,
        "price": SemanticType.PRICE,
    }),
    *_specs("country_daily", "region", {
        "population": SemanticType.LEVEL,
        "gdp": SemanticType.LEVEL,
        "growth": SemanticType.RATE,
        "rate": SemanticType.RATE,
        "inflation": SemanticType.RATE,
        "unemployment": SemanticType.RATE,
        "trade_balance": SemanticType.LEVEL,
        "import_dependency": SemanticType.RATE,
        "export_strength": SemanticType.RATE,
        "debt_to_gdp": SemanticType.RATE,
        "credit_growth": SemanticType.RATE,
        "balance_sheet": SemanticType.LEVEL,
    }),
    *_specs("company_daily", "ticker", {
        "price": SemanticType.PRICE,
        "market_cap": SemanticType.LEVEL,
        "revenue": SemanticType.LEVEL,
        "free_cash_flow": SemanticType.LEVEL,
    }),
    # Global macro contains both stock/level values (M2, balance sheets,
    # liquidity) and rates. Keeping both cheap aggregate interpretations lets
    # each provider request the financially correct semantic at read time.
    *_specs("global_macro_daily", "metric", {"value": SemanticType.RATE}),
    *_specs("global_macro_daily", "metric", {"value": SemanticType.LEVEL}),
    *_specs("forex_daily", "pair", {"rate": SemanticType.PRICE}),
    *_specs("bond_daily", "symbol", {
        "price": SemanticType.PRICE,
        "yield": SemanticType.RATE,
        "default_risk": SemanticType.RATE,
        "liquidity": SemanticType.RATE,
        "duration": SemanticType.LEVEL,
    }),
    *_specs("portfolio_daily", "'WORLD'", {"cash": SemanticType.LEVEL, "net_worth": SemanticType.LEVEL}),
]

_YEARLY_ONLY_SPECS = [
    *_specs("country_trade_daily", "region || ':' || code", {
        "produced": SemanticType.LEVEL,
        "demanded": SemanticType.LEVEL,
        "exports": SemanticType.LEVEL,
        "imports": SemanticType.LEVEL,
        "net": SemanticType.LEVEL,
        "shortage": SemanticType.RATE,
        "pressure": SemanticType.RATE,
    }),
]


def _history_entity(table: str, key_column: str, key: str) -> str:
    if table == "asset_daily" and key_column == "ticker":
        # Callers that need exact disambiguation should pass ``AssetType:TICKER``.
        return str(key) if ":" in str(key) else f"Stock:{key}"
    return str(key)


def _coerce_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    if len(text) == 10 and text[2] == "." and text[5] == ".":
        day, month, year = (int(part) for part in text.split("."))
        return date(year, month, day)
    return date.fromisoformat(text[:10])


def _bounded_points(points: list[dict[str, object]], budget: int) -> list[dict[str, object]]:
    if len(points) <= budget:
        return points
    if budget <= 2:
        return [points[0], points[-1]]
    indexes = {0, len(points) - 1}
    scale = (len(points) - 1) / (budget - 1)
    indexes.update(round(index * scale) for index in range(1, budget - 1))
    return [points[index] for index in sorted(indexes)]


_COLUMN_INDEXES = {
    "country_workforce_monthly": {
        "date": 0, "region": 1, "model_version": 2, "activated_on": 3, "population": 4,
        "birth_rate": 5, "death_rate": 6, "population_growth": 7, "population_interval_years": 8,
        "population_interval_end": 9, "population_growth_annualized": 10,
        **{f"{pool}_{metric}": 11 + 4 * p + m
           for p, pool in enumerate(("basic", "skilled", "highly_qualified"))
           for m, metric in enumerate(("supply", "demand", "coverage", "shortage"))},
    },
    "asset_daily": {
        "date": 0,
        "ticker": 1,
        "asset_type": 2,
        "name": 3,
        "region": 4,
        "sector": 5,
        "price": 6,
        "change_pct": 7,
        "market_cap": 8,
        "revenue": 9,
        "free_cash_flow": 10,
        "rating": 11,
    },
    "bond_daily": {
        "date": 0,
        "symbol": 1,
        "issuer": 2,
        "region": 3,
        "bond_type": 4,
        "price": 5,
        "yield": 6,
        "coupon": 7,
        "maturity_years": 8,
        "rating": 9,
        "issuer_type": 10,
        "category": 11,
        "default_risk": 12,
        "liquidity": 13,
        "maturity_date": 14,
        "change_pct": 15,
        "duration": 16,
    },
    "product_daily": {
        "date": 0,
        "code": 1,
        "item_type": 2,
        "name": 3,
        "category": 4,
        "produced": 5,
        "demanded": 6,
        "inventories": 7,
        "shortage": 8,
        "pressure": 9,
        "price": 10,
    },
    "forex_daily": {
        "date": 0,
        "pair": 1,
        "base": 2,
        "quote": 3,
        "rate": 4,
    },
    "country_daily": {
        "date": 0,
        "region": 1,
        "population": 2,
        "gdp": 3,
        "growth": 4,
        "rate": 5,
        "inflation": 6,
        "unemployment": 7,
        "rating": 8,
        "trade_balance": 9,
        "import_dependency": 10,
        "export_strength": 11,
        "main_sector": 12,
        "main_bottleneck": 13,
        "debt_to_gdp": 14,
        "credit_growth": 15,
        "expected_growth": 16,
        "expected_inflation": 17,
        "expected_rate": 18,
        "macro_surprise": 19,
        "balance_sheet": 20,
    },
}


def _column_index(table: str, column: str) -> int:
    try:
        return _COLUMN_INDEXES[table][column]
    except KeyError as exc:
        raise ValueError(f"Unsupported pending column lookup: {table}.{column}") from exc
