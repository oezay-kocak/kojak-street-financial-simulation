"""Isolated before/after microbenchmarks for the repaired index presentation boundary."""
import ast
import importlib.util
import json
import statistics
import sys
import time
from copy import deepcopy
from functools import partial
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/genesis-audit"


def load_service(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.MarketDataService


def load_rewrite(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_rewrite_ticker_references")
    namespace = {"ModuleType": ModuleType}
    # This executes only the selected function in our frozen production source.
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)  # noqa: S102
    return namespace[node.name]


def stats(values):
    return {"n": len(values), "median_ms": statistics.median(values),
            "p95_ms": sorted(values)[int((len(values) - 1) * .95)], "max_ms": max(values)}


def main():
    baseline = OUT / "baseline/src/kojakstreet/core"
    current = ROOT / "src/kojakstreet/core"
    payload = json.loads((OUT / "final-2307/checkpoint.json").read_text(encoding="utf-8"))["checkpoint"]
    result = {}
    services = [load_service(baseline / "market_data_service.py", "audit_before_service"),
                load_service(current / "market_data_service.py", "audit_after_service")]
    rewrites = [load_rewrite(baseline / "companies.py"), load_rewrite(current / "companies.py")]
    for mode in ("quotes", "rename_identity", "rename_actual"):
        samples = [[], []]
        for iteration in range(105):
            for side in ((0, 1) if iteration % 2 == 0 else (1, 0)):
                data = SimpleNamespace(**deepcopy(payload)) if mode.startswith("rename") else SimpleNamespace(**payload)
                if mode == "quotes":
                    action = services[side](data).quotes
                else:
                    renamed = {t: t for t in data.aktien}
                    if mode == "rename_actual":
                        for ticker in list(renamed)[:10]:
                            renamed[ticker] = "AUDIT_" + ticker
                    action = partial(rewrites[side], data, renamed)
                started = time.perf_counter()
                action()
                elapsed = (time.perf_counter() - started) * 1000
                if iteration >= 5:
                    samples[side].append(elapsed)
        result[mode] = {"before": stats(samples[0]), "after": stats(samples[1])}
    before_source = (baseline / "market_calculations.py").read_bytes()
    result["daily_index_source_unchanged"] = before_source == (current / "market_calculations.py").read_bytes()
    result["scope"] = "100 alternating isolated samples, 5 warmup, fixed Genesis2307, excludes deepcopy/setup; no full-day/native cadence claim"
    (OUT / "index-costs.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
