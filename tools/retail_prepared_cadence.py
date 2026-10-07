"""Isolated experimental scheduler: gate preparation at the real 3-second cadence.

This tool changes runtime methods only in its measurement worker. It does not
enable speculative publication in the application.
"""
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["KOJAK_AUDIT_OUTPUT"] = str(ROOT / ".cache/visible-ui-sync")
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]


def worker():
    import argparse

    import day_transition_audit_support as audit
    from retail_precompute_experiment import WorldPreparer, install_detached_rng, publish_world

    from kojakstreet import live_worker

    parser = argparse.ArgumentParser()
    for name in ("project-root", "data-dir", "bootstrap", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(sys.argv[2:])
    owner = threading.get_ident()
    original_span = audit.span

    # Background world phases must not contaminate boundary request timings.
    from contextlib import contextmanager

    @contextmanager
    def measured_span(label):
        if threading.get_ident() != owner:
            yield
        else:
            with original_span(label):
                yield

    audit.span = measured_span
    audit.install()
    audit.install_worker_logging(args.output)
    if os.environ.get("KOJAK_PREPARED_CADENCE_CONTROL") == "1":
        raise SystemExit(live_worker.run(args.project_root, args.data_dir, args.bootstrap))
    install_detached_rng()
    original_load = live_worker._load_runtime
    original_execute = live_worker._execute

    def load(*values):
        runtime = original_load(*values)
        controller = WorldPreparer(runtime)
        runtime._experimental_preparer = controller
        runtime._experimental_metrics = {}
        step = runtime.simulation.step_day
        close = runtime.close

        def prepared_step():
            prepared = controller.take()
            if prepared is None:
                runtime._experimental_metrics = {"hit": False, "reason": controller.miss_reason}
                return step()
            with audit.span("simulation.core"):
                runtime._experimental_metrics = publish_world(runtime, prepared, controller.epoch)
            if audit.ACTIVE is not None:
                audit.ACTIVE["t1"] = time.perf_counter()
                audit.ACTIVE["phases"] = list(runtime.daten.simulation_phase_timings)

        def finish():
            controller.close()
            close()

        runtime.simulation.step_day = prepared_step
        runtime.close = finish
        controller.start()
        return runtime

    def execute(runtime, command, arguments):
        result, stop = original_execute(runtime, command, arguments)
        if command == "advance":
            result["experimental_precomputation"] = runtime._experimental_metrics
        if not stop:
            runtime._experimental_preparer.start()
        return result, stop

    live_worker._load_runtime = load
    live_worker._execute = execute
    raise SystemExit(live_worker.run(args.project_root, args.data_dir, args.bootstrap))


def benchmark():
    import inspect

    import day_transition_audit as prior
    import zero_flicker_benchmark as driver

    from kojakstreet.live_process import LiveSimulationProcess

    if "--sequential" in sys.argv:
        sys.argv.remove("--sequential")
        os.environ["KOJAK_PREPARED_CADENCE_CONTROL"] = "1"

    original_source = inspect.getsource
    apply = LiveSimulationProcess._apply_result

    def applied(self, result):
        self.experimental_precomputation = result.get("experimental_precomputation", {})
        return apply(self, result)

    LiveSimulationProcess._apply_result = applied

    def source(value):
        result = original_source(value)
        if value is prior.qt:
            result = result.replace(
                'QTimer.singleShot(30, request)',
                'QTimer.singleShot(max(0, int(3000 - (time.perf_counter() - row["t0"])*1000)), request)',
            )
            result = result.replace('row["t4"] = now',
                'row["precomputation"] = dict(process.experimental_precomputation)\n        row["t4"] = now')
        return result

    inspect.getsource = source
    prior.__file__ = __file__
    driver.main()


if __name__ == "__main__":
    worker() if len(sys.argv) > 1 and sys.argv[1] == "worker" else benchmark()
