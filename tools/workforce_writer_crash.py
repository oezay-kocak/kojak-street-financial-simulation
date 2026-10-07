"""Crash the production writer at a requested boundary using workforce rows."""
import argparse
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from tools.process_crash import crash_exit


def row():
    return ("1990-01-15", "Ameron", 1, "1990-01-01", 20_000_000., .012, .0085,
            .0003, 1 / 12, "1990-01-15", .0036,
            5_200_000., 4_000_000., 1.3, 0.,
            5_200_000., 4_000_000., 1.3, 0.,
            2_600_000., 2_000_000., 1.3, 0.)


def main():
    import duckdb

    from kojakstreet.core.data_store import EconomicDataStore
    from kojakstreet.core.persistence_writer import OrderedWriter

    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--stage", required=True)
    args = parser.parse_args()
    store = EconomicDataStore(args.database)
    history = store._history_id
    store.close()

    class CrashConnection:
        def __init__(self, raw):
            self.raw = raw

        def __getattr__(self, key):
            return getattr(self.raw, key)

        def execute(self, sql, *values, **kwargs):
            command = sql.strip().split()[0].upper()
            if (args.stage == "before_transaction" and command == "BEGIN") or (args.stage == "before_commit" and command == "COMMIT"):
                crash_exit()
            if args.stage == "during_commit" and command == "COMMIT":
                threading.Timer(.001, crash_exit).start()
            result = self.raw.execute(sql, *values, **kwargs)
            if (args.stage == "during_copy" and command == "COPY") or (args.stage == "after_commit" and command == "COMMIT"):
                crash_exit()
            return self if result is self.raw else result

    writer = OrderedWriter(args.database, history,
                           lambda path: CrashConnection(duckdb.connect(path)),
                           EconomicDataStore._write_row_batch)
    if args.stage == "after_ack":
        original = writer.journal.acknowledge

        def acknowledge(*args):
            original(*args)
            crash_exit()
        writer.journal.acknowledge = acknowledge
    rows = [row()]
    writer.submit({"country_workforce_monthly": rows}, {"country_workforce_current": rows}, {"1990-01-15"})
    writer.barrier()
    crash_exit()


if __name__ == "__main__":
    main()
