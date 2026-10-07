"""Summarize measured evidence without mixing diagnostics into latency rows."""
import hashlib
import json
import sys
from pathlib import Path

from visible_sync_report import OUT as RUNS
from visible_sync_report import gc_spans, normal, run, stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/max-performance"


def summary(rows):
    segments = (
        ("T0-T1", lambda row: (row["worker"]["t1"] - row["t0"]) * 1000),
        ("T1-T2", lambda row: (row["t2"] - row["worker"]["t1"]) * 1000),
        ("T2-T3", lambda row: (row["t3"] - row["t2"]) * 1000),
        ("T3-T4", lambda row: (row["t4"] - row["t3"]) * 1000),
        ("T0-T4", lambda row: row["total_ms"]),
        ("Heartbeat", lambda row: max(row["heartbeat_gaps_ms"])),
        ("Bytes", lambda row: row["worker"]["response_bytes"]),
        ("Worker CPU", lambda row: row["worker"]["cpu_ms"]),
        ("Parent CPU", lambda row: row["parent_cpu_ms"]),
        ("Worker RSS MiB", lambda row: row["worker"]["rss_end"] / 2**20),
        ("Parent RSS MiB", lambda row: row["parent_rss_end"] / 2**20),
    )
    return {
        "n": len(rows), **{name: stats([fn(row) for row in rows]) for name, fn in segments},
        "Worker GC": stats(gc_spans(rows, True)), "Parent GC": stats(gc_spans(rows)),
    }


def main():
    result = {}
    for label in sys.argv[1:]:
        data = run(RUNS, label)
        ordinary = normal(data["rows"])
        result[label] = {
            "all": summary(data["rows"]),
            "ordinary": summary(ordinary) if ordinary else None,
            "signature_sha256": hashlib.sha256(json.dumps(data["signature"], sort_keys=True).encode()).hexdigest(),
            "views": {view: summary([row for row in data["rows"] if row["view"] == view]) for view in sorted({row["view"] for row in data["rows"]})},
            "special": [{"date": row["date"], "total_ms": row["total_ms"], "flush_ms": row["worker"]["spans"].get("store.flush", 0), "phases": row["worker"]["phases"]} for row in data["rows"] if row not in ordinary],
        }
        print(label, result[label]["ordinary"] or result[label]["all"], flush=True)
    (OUT / "timing-evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
