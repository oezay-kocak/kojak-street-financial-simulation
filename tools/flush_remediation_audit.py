"""Isolated, current-source flush evidence; never changes a production database."""
import argparse
import csv
import hashlib
import importlib._bootstrap as bootstrap
import json
import os
import pickle
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/flush-remediation"
OUT.mkdir(parents=True, exist_ok=True)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def freeze():
    target = OUT / "baseline"
    assert not target.exists()
    hashes = {}
    for path in [*sorted((ROOT / "src").rglob("*.py")), ROOT / "daten.py", ROOT / "speicher.py"]:
        relative = path.relative_to(ROOT)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        hashes[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    write("before-source-hashes.json", hashes)
    print("Frozen", len(hashes), "production files", flush=True)


def prepare():
    import day_transition_audit as driver

    runtime = driver.make_runtime(OUT / "prepare-world", "end")
    try:
        for _ in range(29):
            runtime.advance_day()
        store = runtime.data_store
        store.auto_flush = False
        runtime.advance_day()
        state = {
            "pending_rows": dict(store._pending_rows), "pending_days": store._pending_days,
            "current_rows": store._current_rows,
        }
        with (OUT / "flush-rows.pickle").open("wb") as stream:
            pickle.dump(state, stream, protocol=5)
        store._connection.execute("CHECKPOINT")
        store._connection.close()
        store._connection = None
        shutil.copy2(store.path, OUT / "before-flush.duckdb")
        write("fixture.json", {
            "date": str(runtime.daten.datum),
            "days": sorted(state["pending_days"]),
            "rows": {table: len(rows) for table, rows in state["pending_rows"].items()},
            "current_rows": {table: len(rows) for table, rows in state["current_rows"].items()},
            "buffer_bytes": (OUT / "flush-rows.pickle").stat().st_size,
            "database_bytes": (OUT / "before-flush.duckdb").stat().st_size,
        })
        print("Prepared", str(runtime.daten.datum), flush=True)
    finally:
        runtime.close()


class Observer:
    def __init__(self, raw, path, profile=False, commit_threads=None):
        self.raw, self.path = raw, path
        self.sql, self.operations = [], []
        self.table, self.operation = None, None
        self.active_sql = None
        self.profile = profile
        self.commit_threads = commit_threads
        if profile:
            raw.execute("SET profiling_output=?", [str(OUT / (path.stem + '-setup-profile.json'))])
            raw.execute("SET enable_profiling='json'")
            raw.execute("SET profiling_coverage='ALL'")

    def __getattr__(self, key):
        return getattr(self.raw, key)

    def execute(self, sql, *args, **kwargs):
        return self.invoke("execute", sql, *args, **kwargs)

    def executemany(self, sql, *args, **kwargs):
        return self.invoke("executemany", sql, *args, **kwargs)

    def invoke(self, method, sql, *args, **kwargs):
        command = sql.lstrip().split()[0].upper()
        copied = None
        if command == "COPY":
            match = re.search(r"FROM '((?:[^']|'')+)'", sql)
            if match:
                copied = Path(match[1].replace("''", "'")).stat().st_size
        before = self.disk()
        profile_path = OUT / f"{self.path.stem}-sql-{len(self.sql)}.json"
        if self.profile:
            self.raw.execute("SET profiling_output=?", [str(profile_path)])
        started, cpu = time.perf_counter(), time.process_time()
        previous_threads = None
        if command == 'COMMIT' and self.commit_threads:
            previous_threads = self.raw.execute("SELECT current_setting('threads')").fetchone()[0]
            self.raw.execute(f"SET threads={self.commit_threads}")
        self.active_sql = sql
        try:
            result = getattr(self.raw, method)(sql, *args, **kwargs)
        finally:
            self.active_sql = None
            if previous_threads is not None:
                self.raw.execute(f"SET threads={previous_threads}")
        self.sql.append({
            "sql": sql, "command": command, "table": self.table,
            "operation": self.operation, "method": method,
            "ms": (time.perf_counter() - started) * 1000,
            "cpu_ms": (time.process_time() - cpu) * 1000,
            "copy_bytes": copied, "disk_before": before, "disk_after": self.disk(),
            "bound_rows": len(args[0]) if method == "executemany" and args else None,
            "profile_path": str(profile_path) if self.profile else None,
        })
        return self if result is self.raw else result

    def disk(self):
        return {suffix: path.stat().st_size if path.exists() else 0
                for suffix, path in (("db", self.path), ("wal", Path(str(self.path) + ".wal")))}


def raw(args):
    from kojakstreet.core.data_store import EconomicDataStore

    with (OUT / "flush-rows.pickle").open("rb") as stream:
        state = pickle.load(stream)  # Trusted locally generated fixture.
    results = []
    original_insert = EconomicDataStore._insert_rows
    original_buffered = EconomicDataStore._replace_buffered_rows
    original_current = EconomicDataStore._replace_current_rows
    original_compact = EconomicDataStore._compact_completed_history
    original_writer = csv.writer

    def io_insert(store, table, rows):
        previous = store._connection.execute("SELECT current_setting('threads')").fetchone()[0]
        store._connection.execute("SET threads=1")
        try:
            return original_insert(store, table, rows)
        finally:
            store._connection.execute(f"SET threads={previous}")

    def literal_buffered(store, table, rows):
        from datetime import date
        if not rows:
            return
        dates = sorted({str(row[0]) for row in rows})
        # Only canonical ISO dates enter SQL; fallback preserves legacy input conversion.
        try:
            valid = all(date.fromisoformat(value).isoformat() == value for value in dates)
        except ValueError:
            valid = False
        if not valid:
            return original_buffered(store, table, rows)
        literals = ','.join("DATE '" + value + "'" for value in dates)
        store._connection.execute(f"DELETE FROM {table} WHERE date IN ({literals})")
        store._insert_rows(table, rows)

    def numpy_insert(store, table, rows):
        import math

        import numpy as np
        if not rows or table in {'news_events', 'news_current', 'event_log', 'event_current', 'phase_metric_daily', 'phase_metric_current'}:
            return original_insert(store, table, rows)
        if any(isinstance(value, float) and math.isnan(value) for row in rows for value in row):
            return original_insert(store, table, rows)
        # Match the existing generic CSV's configured null marker. Its writer
        # emits None as an empty field; literal backslash-N is the COPY null.
        schema = store._connection.execute(f"PRAGMA table_info('{table}')").fetchall()
        arrays = {'c' + str(index): np.asarray([
            '' if value is None else None if isinstance(value, str) and value == r'\N' else value
            for value in column], dtype=np.float64 if schema[index][2] == 'DOUBLE' else
            np.int64 if schema[index][2] in {'INTEGER', 'BIGINT'} else object)
                  for index, column in enumerate(zip(*rows))}
        store._connection.register('_flush_candidate_rows', arrays)
        try:
            store._connection.execute(f"INSERT INTO {table} SELECT * FROM _flush_candidate_rows")
        finally:
            store._connection.unregister('_flush_candidate_rows')

    def staging_insert(store, table, rows):
        if not rows or table in {'news_events', 'news_current', 'event_log', 'event_current', 'phase_metric_daily', 'phase_metric_current'}:
            return original_insert(store, table, rows)
        temporary = '_flush_staging'
        store._connection.execute(f'CREATE TEMP TABLE {temporary} AS SELECT * FROM {table} WHERE FALSE')
        try:
            original_insert(store, temporary, rows)
            store._connection.execute(f'INSERT INTO {table} SELECT * FROM {temporary}')
        finally:
            store._connection.execute(f'DROP TABLE {temporary}')

    candidate_insert = numpy_insert if args.candidate in {'numpy', 'combined'} else io_insert if args.candidate == 'io1' else staging_insert if args.candidate == 'staging' else original_insert
    candidate_buffered = literal_buffered if args.candidate in {'literal', 'combined'} else original_buffered
    EconomicDataStore._insert_rows = candidate_insert
    EconomicDataStore._replace_buffered_rows = candidate_buffered

    class CsvTimer:
        def __init__(self, *values, **kwargs):
            self.raw = original_writer(*values, **kwargs)

        def __getattr__(self, key):
            return getattr(self.raw, key)

        def writerows(self, rows):
            started = time.perf_counter()
            self.raw.writerows(rows)
            observer.operations.append({"operation": "csv", "table": observer.table,
                                        "rows": len(rows), "ms": (time.perf_counter() - started) * 1000})

    def measured(function, operation):
        def call(store, *values, **kwargs):
            previous = observer.table, observer.operation
            table = values[0] if values and isinstance(values[0], str) else None
            observer.table, observer.operation = table, operation
            index, started = len(observer.sql), time.perf_counter()
            try:
                return function(store, *values, **kwargs)
            finally:
                elapsed = (time.perf_counter() - started) * 1000
                native = sum(row["ms"] for row in observer.sql[index:])
                observer.operations.append({"operation": operation, "table": table,
                                            "rows": len(values[1]) if len(values) > 1 else None,
                                            "ms": elapsed, "python_ms": elapsed - native, "duckdb_ms": native})
                observer.table, observer.operation = previous
        return call

    for index in range(args.repeats):
        path = OUT / f"{args.label}-{index}.duckdb"
        assert not path.exists()
        shutil.copy2(OUT / "before-flush.duckdb", path)
        store = EconomicDataStore(path)
        observer = Observer(store._connection, path, args.profile, args.commit_threads)
        store._connection = observer
        settings = observer.raw.execute("SELECT name,value FROM duckdb_settings() WHERE name IN ('threads','checkpoint_threshold','preserve_insertion_order','enable_fsync')").fetchall()
        if args.threads:
            observer.raw.execute(f"SET threads={args.threads}")
        counts_before = {table: observer.raw.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                         for (table,) in observer.raw.execute("SHOW TABLES").fetchall()}
        store._pending_rows = defaultdict(list, {key: list(rows) for key, rows in state["pending_rows"].items()})
        store._pending_days = set(state["pending_days"])
        store._current_rows = {key: list(rows) for key, rows in state["current_rows"].items()}
        imports = defaultdict(lambda: {'calls': 0, 'failed': 0, 'ms': 0.0})
        original_import = bootstrap._find_and_load

        def import_probe(name, import_, observer=observer, original_import=original_import, imports=imports):
            if name != 'pandas' or observer.active_sql is None:
                return original_import(name, import_)
            key = observer.active_sql[:140]
            started = time.perf_counter()
            try:
                return original_import(name, import_)
            except ImportError:
                imports[key]['failed'] += 1
                raise
            finally:
                imports[key]['calls'] += 1
                imports[key]['ms'] += (time.perf_counter() - started) * 1000

        if args.imports:
            bootstrap._find_and_load = import_probe
        if args.observe:
            csv.writer = CsvTimer
            EconomicDataStore._insert_rows = measured(candidate_insert, "insert")
            EconomicDataStore._replace_buffered_rows = measured(candidate_buffered, "buffered")
            EconomicDataStore._replace_current_rows = measured(original_current, "current")
            EconomicDataStore._compact_completed_history = measured(original_compact, "compaction")
        started, cpu = time.perf_counter(), time.process_time()
        if args.timeout:
            import threading
            def timed_out(index=index):
                write(args.label + '-timeout.json', {'repetition': index, 'timeout_seconds': args.timeout})
                os._exit(124)
            timer = threading.Timer(args.timeout, timed_out)
            timer.start()
        store.flush()
        if args.timeout:
            timer.cancel()
        elapsed, cpu_ms = (time.perf_counter() - started) * 1000, (time.process_time() - cpu) * 1000
        bootstrap._find_and_load = original_import
        if args.profile:
            observer.raw.execute("PRAGMA disable_profiling")
        counts_after = {table: observer.raw.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                        for table in counts_before}
        result = {"ms": elapsed, "cpu_ms": cpu_ms, "settings": settings, "disk": observer.disk(),
                  "before": counts_before, "after": counts_after,
                  "sql": observer.sql, "operations": observer.operations, "imports": dict(imports)}
        results.append(result)
        print(args.label, index, round(elapsed, 2), flush=True)
        store.close()
    csv.writer = original_writer
    EconomicDataStore._insert_rows = original_insert
    EconomicDataStore._replace_buffered_rows = original_buffered
    EconomicDataStore._replace_current_rows = original_current
    EconomicDataStore._compact_completed_history = original_compact
    write(args.label + ".json", results)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "prepare", "raw"))
    parser.add_argument("--label", default="raw-before")
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--observe", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--imports", action="store_true")
    parser.add_argument("--threads", type=int)
    parser.add_argument("--commit-threads", type=int)
    parser.add_argument("--candidate", choices=('literal', 'numpy', 'combined', 'io1', 'staging'))
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    source = OUT / "baseline" if args.reference else ROOT
    os.environ["KOJAK_AUDIT_PROJECT_ROOT"] = str(source)
    sys.path[:0] = [str(source / "src"), str(source), str(ROOT / "tools")]
    if args.mode == "freeze":
        freeze()
    elif args.mode == "prepare":
        prepare()
    else:
        raw(args)


if __name__ == "__main__":
    main()
