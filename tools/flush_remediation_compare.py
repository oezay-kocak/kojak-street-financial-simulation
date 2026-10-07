"""Compare every value and schema in isolated flush candidate databases."""
import argparse
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/flush-remediation"


def signature(path):
    result = {}
    connection = duckdb.connect(str(path), read_only=True)
    try:
        for (table,) in connection.execute("SHOW TABLES").fetchall():
            schema = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            cursor = connection.execute(f'SELECT * FROM "{table}" ORDER BY ALL')
            hasher, count = hashlib.sha256(), 0
            while rows := cursor.fetchmany(4096):
                for row in rows:
                    hasher.update(repr(row).encode("utf-8"))
                    hasher.update(b"\n")
                    count += 1
            result[table] = {"rows": count, "sha256": hasher.hexdigest(), "schema": schema}
    finally:
        connection.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", nargs="+")
    parser.add_argument("--output", default="candidate-exact")
    args = parser.parse_args()
    results = {}
    reference = None
    for label in args.labels:
        current = signature(OUT / (label + ".duckdb"))
        if reference is None:
            reference = current
        differences = [table for table in reference if current.get(table) != reference[table]]
        results[label] = {"exact": not differences, "different_tables": differences, "tables": current}
        print(label, "exact", not differences, differences, flush=True)
    (OUT / (args.output + ".json")).write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
