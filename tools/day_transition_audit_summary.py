"""Aggregate independent latency samples and separately collected profiles."""
import json
import os
import pstats
import statistics
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("KOJAK_AUDIT_OUTPUT", str(ROOT / ".cache" / "day-transition-audit"))).resolve()


def quantile(values, fraction):
    values = sorted(values)
    position = (len(values)-1)*fraction
    i = int(position)
    return values[i] + (values[min(i+1, len(values)-1)]-values[i])*(position-i)


def stats(values, unit="ms"):
    if not values:
        return None
    return {"n": len(values), f"min_{unit}": min(values), f"median_{unit}": statistics.median(values),
            f"mean_{unit}": statistics.mean(values), f"p95_{unit}": quantile(values, .95), f"max_{unit}": max(values)}


def kind(row):
    current = date.fromisoformat(row["date"])
    tomorrow = current + timedelta(days=1)
    if tomorrow.year != current.year:
        return "year_end"
    if current.day == 15:
        return "report"
    if tomorrow.month != current.month:
        return "month_end"
    return "normal"


def gc_ms(events):
    start = {}
    total = 0
    for event in events:
        if event["phase"] == "start":
            start[event["generation"]] = event["time"]
        elif event["generation"] in start:
            total += (event["time"]-start.pop(event["generation"]))*1000
    return total


def load_run(path):
    result = json.loads(path.read_text(encoding="utf-8"))
    worker = path.with_name(path.stem + "-worker.jsonl")
    if worker.exists():
        worker_rows = [json.loads(line) for line in worker.read_text(encoding="utf-8").splitlines()]
        if len(worker_rows) != len(result["rows"]):
            raise AssertionError(f"Worker row count differs for {path.stem}")
        for row, detail in zip(result["rows"], worker_rows):
            if row["date"] != detail["date"]:
                raise AssertionError("Dates do not match")
            row["worker"] = detail
            row["simulation_ms"] = (detail["t1"]-row["t0"])*1000
            row["persistence_transfer_ms"] = (row["t2"]-detail["t1"])*1000
            row["ui_ms"] = (row["t4"]-row["t2"])*1000
            row["model_ms"] = (row["t3"]-row["t2"])*1000
            row["paint_wait_ms"] = (row["t4"]-row["t3"])*1000
            row["dispatch_ms"] = (detail["t_sim_start"]-row["t0"])*1000
            row["post_sim_ready_ms"] = (row["t4"]-detail["t1"])*1000
            row["spans"] = detail["spans"] | row["parent_spans"]
            row["phases"] = detail.get("phases", [])
            row["duckdb_ms"] = detail["spans"].get("duckdb.native_api", 0)
            row["worker_gc_ms"] = gc_ms(detail["gc"])
            row["parent_gc_ms"] = gc_ms(row["parent_gc"])
            row["response_bytes"] = detail.get("response_bytes", 0)
            # Retained first intervals can start before T0; only complete
            # intervals between two in-transition heartbeats count here.
            row["heartbeat_max_ms"] = max(row["heartbeat_gaps_ms"][1:], default=0)
            row["cpu_core_equivalents"] = detail["cpu_ms"] / ((detail["t_end"]-detail["t_start"])*1000)
    else:
        for row in result["rows"]:
            row["simulation_ms"] = row["spans"].get("simulation.core", 0)
            row["persistence_transfer_ms"] = row["spans"].get("store.record_day", 0)
            row["duckdb_ms"] = row["spans"].get("duckdb.native_api", 0)
            row["worker_gc_ms"] = gc_ms(row["gc"])
            row["cpu_core_equivalents"] = row["cpu_ms"] / row["total_ms"]
    return result


def profile_tables(pattern):
    paths = sorted(OUT.glob(pattern))
    if not paths:
        return None
    combined = pstats.Stats(str(paths[0]))
    for path in paths[1:]:
        combined.add(str(path))
    rows = []
    for (filename, line, name), (primitive, calls, self_time, cumulative, callers) in combined.stats.items():
        rows.append({"file": filename, "line": line, "function": name, "primitive_calls_per_sample": primitive/len(paths),
                     "calls_per_sample": calls/len(paths), "self_ms_per_sample": self_time*1000/len(paths),
                     "cumulative_ms_per_sample": cumulative*1000/len(paths)})
    return {"samples": len(paths), "total_calls_per_sample": combined.total_calls/len(paths),
            "self_total_ms_per_sample": combined.total_tt*1000/len(paths),
            "top20_cumulative": sorted(rows, key=lambda x:x["cumulative_ms_per_sample"], reverse=True)[:20],
            "top20_self": sorted(rows, key=lambda x:x["self_ms_per_sample"], reverse=True)[:20],
            "top20_calls": sorted(rows, key=lambda x:x["calls_per_sample"], reverse=True)[:20],
            "all": rows}


def main():
    output = {"runs": {}, "profiles": {}, "comparisons": {}}
    raw = {}
    for path in OUT.glob("*.json"):
        if path.name.startswith(("environment-", "checkpoint-", "allocations-", "profiles", "summary", "merged")):
            continue
        if path.stem.startswith("qt-") and not path.stem.endswith("-valid"):
            continue  # Superseded or exploratory runs are not performance evidence.
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict) or "rows" not in result:
            continue
        result = load_run(path)
        raw[path.stem] = result
        summary = {"mode": result["mode"], "samples": len(result["rows"]), "types": {}}
        for name in ("all", "normal", "normal_no_flush", "report", "month_end", "year_end", "year_start", "annual_issue", "flush"):
            rows = [r for r in result["rows"] if name == "all" or kind(r) == name
                    or name == "flush" and r["spans"].get("store.flush", 0) > 0
                    or name == "normal_no_flush" and kind(r) == "normal" and not r["spans"].get("store.flush", 0)
                    or name == "year_start" and r["date"][5:] == "01-01"
                    or name == "annual_issue" and r["date"][5:] == "01-03"]
            if not rows:
                continue
            metrics = {}
            for key in ("total_ms", "simulation_ms", "persistence_transfer_ms", "ui_ms", "model_ms", "paint_wait_ms", "dispatch_ms",
                        "post_sim_ready_ms", "duckdb_ms", "worker_gc_ms", "parent_gc_ms", "heartbeat_max_ms", "response_bytes", "cpu_core_equivalents"):
                if key in rows[0]:
                    unit = "bytes" if key == "response_bytes" else "cores" if key == "cpu_core_equivalents" else "ms"
                    metrics[key] = stats([row[key] for row in rows], unit)
            spans = sorted({key for row in rows for key in row["spans"]})
            metrics["spans"] = {key:stats([row["spans"].get(key,0) for row in rows]) for key in spans}
            phases = sorted({p["phase"] for row in rows for p in row.get("phases", [])})
            metrics["phases"] = {phase:stats([next((p["duration_ms"] for p in row.get("phases", []) if p["phase"]==phase),0) for row in rows]) for phase in phases}
            summary["types"][name] = metrics
        summary["signal_totals"] = {key:sum(row.get(key,0) for row in result["rows"]) for key in ("visible_chart_calls", "hidden_chart_calls", "paints", "qt_metacalls")}
        summary["view_calls"] = {}
        summary["model_signals"] = {}
        for row in result["rows"]:
            for target in ("view_calls", "model_signals"):
                for key,value in row.get(target,{}).items():
                    summary[target][key] = summary[target].get(key,0) + value
        output["runs"][path.stem] = summary
    for label in ("normal", "report", "month_end", "year_end", "mature_normal", "warm_normal", "flush"):
        output["profiles"][label] = profile_tables(f"profile-{label}-*.pstats")
    for name in raw:
        if (OUT / f"ui-profile-{name}-0.pstats").exists():
            output["profiles"][name] = profile_tables(f"ui-profile-{name}-*.pstats")
    for left, right in (("headless-year-clean", "qt-year-clean-valid"), ("headless-year", "qt-year-valid"), ("headless-mature", "qt-mature-none-valid"), ("headless-mature", "qt-mature-detail-valid"), ("headless-mature", "qt-mature-heavy-valid"), ("headless-mature", "qt-mature-candle-valid"), ("headless-mature", "qt-mature-preview-valid"), ("control-original", "control-instrumented")):
        if left in raw and right in raw:
            output["comparisons"][left + " vs " + right] = {"economic_signature_equal": raw[left]["signature"] == raw[right]["signature"]}
            if "public_numeric_checkpoint" in raw[left]:
                output["comparisons"][left + " vs " + right]["public_numeric_checkpoint_equal"] = raw[left]["public_numeric_checkpoint"] == raw[right].get("public_numeric_checkpoint")
    # Full merged records permit independent verification of T0→T4 arithmetic.
    (OUT / "summary.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    (OUT / "merged-results.json").write_text(json.dumps(raw), encoding="utf-8")
    print(json.dumps({name:{kind:round(metrics['total_ms']['median_ms'],2) for kind,metrics in run['types'].items()}
                      for name,run in output['runs'].items()}, indent=2))


if __name__ == "__main__":
    main()
