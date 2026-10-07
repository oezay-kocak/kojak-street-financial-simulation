"""Real-cadence sequential benchmark; optional separate worker/UI profiling."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/max-performance"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["KOJAK_AUDIT_OUTPUT"] = str(ROOT / ".cache/visible-ui-sync")
SOURCE = Path(os.environ.get("KOJAK_AUDIT_PROJECT_ROOT", str(ROOT))).resolve()
sys.path[:0] = [str(SOURCE / "src"), str(SOURCE), str(ROOT / "tools")]


def worker():
    import argparse
    import cProfile

    import day_transition_audit_support as audit

    from kojakstreet import live_worker

    parser = argparse.ArgumentParser()
    for name in ("project-root", "data-dir", "bootstrap", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(sys.argv[2:])
    audit.install()
    audit.install_worker_logging(args.output)
    if os.environ.get("KOJAK_MAX_TRACE_WORKER") == "1":
        import json
        import tracemalloc

        original_trace = live_worker._execute
        trace_count = 0

        def traced(runtime, command, arguments):
            nonlocal trace_count
            if command != "advance" or not arguments.get("steps", 0):
                return original_trace(runtime, command, arguments)
            tracemalloc.start(3)
            before = tracemalloc.take_snapshot()
            try:
                result = original_trace(runtime, command, arguments)
                after = tracemalloc.take_snapshot()
                current, peak = tracemalloc.get_traced_memory()
                changes = after.compare_to(before, "lineno")
                payload = {
                    "current_bytes": current, "peak_bytes": peak,
                    "net_bytes": sum(row.size_diff for row in changes),
                    "net_blocks": sum(row.count_diff for row in changes),
                    "top": [{"source": str(row.traceback), "bytes": row.size_diff, "blocks": row.count_diff} for row in changes[:30]],
                }
                (OUT / f"worker-allocations-{args.output.stem}-{trace_count}.json").write_text(json.dumps(payload), encoding="utf-8")
                trace_count += 1
                return result
            finally:
                tracemalloc.stop()

        live_worker._execute = traced
    if os.environ.get("KOJAK_MAX_PROFILE") == "1":
        original = live_worker._execute
        count = 0

        def profiled(runtime, command, arguments):
            nonlocal count
            if command != "advance" or not arguments.get("steps", 0):
                return original(runtime, command, arguments)
            profiler = cProfile.Profile()
            result = profiler.runcall(original, runtime, command, arguments)
            profiler.dump_stats(OUT / f"worker-{args.output.stem}-{count}.pstats")
            count += 1
            return result

        live_worker._execute = profiled
    raise SystemExit(live_worker.run(args.project_root, args.data_dir, args.bootstrap))


def benchmark():
    import inspect  # noqa: I001 -- source pinning requires this order

    import day_transition_audit as prior
    # Pin the package before legacy audit drivers prepend their tool root.
    import kojakstreet
    import zero_flicker_benchmark as driver

    assert Path(kojakstreet.__file__).resolve().is_relative_to(SOURCE)
    sys.path[:0] = [str(SOURCE / "src"), str(SOURCE)]
    # Observe the closed bootstrap's retained analytics outside all transitions.
    import json

    from kojakstreet.core.data_store import EconomicDataStore

    original_close = EconomicDataStore.close
    label = sys.argv[sys.argv.index("--label") + 1]

    def close(store):
        original_close(store)
        payload = {
            "session_rows": {table: len(rows) for table, rows in store._session_rows.items()},
            "current_rows": {table: len(rows) for table, rows in store._current_rows.items()},
        }
        (OUT / f"closed-bootstrap-{label}.json").write_text(json.dumps(payload), encoding="utf-8")

    EconomicDataStore.close = close
    if "--trace-worker" in sys.argv:
        sys.argv.remove("--trace-worker")
        os.environ["KOJAK_MAX_TRACE_WORKER"] = "1"
    stacks = "--stacks" in sys.argv
    if stacks:
        sys.argv.remove("--stacks")
        import json
        import threading
        import time

        main_thread = threading.get_ident()
        stop = threading.Event()
        samples = []
        original_finish = prior.audit.finish
        label = sys.argv[sys.argv.index("--label") + 1]
        count = 0

        def sample():
            while not stop.wait(0.002):
                if prior.audit.ACTIVE is None:
                    continue
                frame = sys._current_frames().get(main_thread)
                stack = []
                while frame is not None:
                    stack.append((frame.f_code.co_filename, frame.f_code.co_name, frame.f_lineno))
                    frame = frame.f_back
                samples.append((time.perf_counter(), stack))

        def finish():
            nonlocal count
            result = original_finish()
            if result:
                (OUT / f"stacks-{label}-{count}.json").write_text(json.dumps(samples), encoding="utf-8")
                count += 1
                samples.clear()
            return result

        prior.audit.finish = finish
        observer = threading.Thread(target=sample, daemon=True)
        observer.start()
    profile = "--profile" in sys.argv
    if profile:
        sys.argv.remove("--profile")
        os.environ["KOJAK_MAX_PROFILE"] = "1"
    original_source = inspect.getsource

    def source(value):
        result = original_source(value)
        if value is prior.qt:
            result = result.replace(
                "QTimer.singleShot(30, request)",
                'QTimer.singleShot(max(0, int(3000-(time.perf_counter()-row["t0"])*1000)), request)',
            )
        elif value is driver.driver and profile:
            result = result.replace("profile_ui=False", "profile_ui=True")
        return result

    inspect.getsource = source
    prior.__file__ = __file__
    try:
        driver.main()
    finally:
        if stacks:
            stop.set()
            observer.join()


if __name__ == "__main__":
    worker() if len(sys.argv) > 1 and sys.argv[1] == "worker" else benchmark()
