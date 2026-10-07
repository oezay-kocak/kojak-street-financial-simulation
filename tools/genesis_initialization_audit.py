"""Read-only Genesis evidence collection; all output lives in the audit directory."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/genesis-audit"
BOOKS = ("makro", "aktien", "rohstoffe", "processed_products", "kryptos", "fonds", "indizes")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def freeze():
    files = [ROOT / "daten.py", ROOT / "speicher.py", *sorted((ROOT / "src").rglob("*.py"))]
    hashes = {}
    for path in files:
        relative = path.relative_to(ROOT)
        destination = OUT / "baseline" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        hashes[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    write(OUT / "before-source-hashes.json", hashes)


def collect(seed, label, warm=False, reference=False):
    sys.path.insert(0, str(ROOT))
    project = OUT / "baseline" if reference else ROOT
    sys.path.insert(0, str(project / "src"))
    sys.path.insert(0, str(project))
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture
    from kojakstreet.core.market_data_service import MarketDataService
    from kojakstreet.ui_qt.models.market_table_model import build_market_rows

    if warm:
        import daten  # noqa: F401 - distinguish import/reload RNG behavior
    calls = []
    seen = set()

    def trace(frame, event, arg):
        if event != "call":
            return
        filename = frame.f_code.co_filename
        if not filename.startswith(str(ROOT)) or ".venv" in filename:
            return
        relative = filename[len(str(ROOT)) + 1:]
        if relative.startswith(("src\\", "src/")) or relative == "daten.py":
            identity = (relative, frame.f_code.co_name, frame.f_code.co_firstlineno)
            if identity not in seen:
                calls.append(identity)
                seen.add(identity)

    sys.setprofile(trace)
    try:
        runtime = IntegratedRuntime(project, data_dir=OUT / label / "data", seed=seed)
    finally:
        sys.setprofile(None)
    try:
        data = runtime.daten
        payload = capture(runtime.state)
        write(OUT / label / "checkpoint.json", payload)
        quotes = MarketDataService(data).quotes()
        rows = build_market_rows(runtime.snapshot_for_view("Markets"), set())
        countries = []
        for name, macro in data.makro.items():
            stocks = {t: a for t, a in data.aktien.items() if a["land"] == name}
            indices = {t: a for t, a in data.indizes.items() if a["land"] == name}
            cap = [a["market_cap"] for a in stocks.values()]
            countries.append({
                "country": name, "macro": macro, "company_count": len(stocks),
                "sectors": dict(Counter(a["branche"] for a in stocks.values())),
                "market_cap": sum(cap), "cap_min": min(cap),
                "cap_median": statistics.median(cap), "cap_max": max(cap),
                "production_capacity": sum(a["production_capacity"] for a in stocks.values()),
                "bonds": dict(Counter(b["issuer_type"] for b in data.bond_market if b["region"] == name)),
                "funds": dict(Counter(a["fund_type"] for a in data.fonds.values() if a.get("land") == name)),
                "indices": {t: {k: a[k] for k in ("index_type", "branche", "constituent_count", "kurs", "market_cap")} for t, a in indices.items()},
                "quoted_indices": [q.ticker for q in quotes if q.asset_type == "Index" and q.region == name],
                "displayed_indices": [r["ticker"] for r in rows if r["asset_type"] == "Index" and r["region"] == name],
                "collisions": [t for t in indices if t in data.aktien or t in data.kryptos or t in data.fonds or t in data.rohstoffe],
            })
        inventories = {}
        for book in (*BOOKS, "derivatives", "bond_market", "global_macro", "market_psychology"):
            value = getattr(data, book, {})
            if book in {"global_macro", "market_psychology"}:
                entities = {"world": value}
            elif isinstance(value, list):
                entities = {str(i): row for i, row in enumerate(value)}
            else:
                entities = value
            fields = defaultdict(list)
            for identifier, entity in entities.items():
                if isinstance(entity, dict):
                    for key, val in entity.items():
                        fields[key].append((identifier, val))
            inventories[book] = dict(fields)
        write(OUT / label / "inventory-values.json", inventories)
        write(OUT / label / "creation-calls.json", calls)
        write(OUT / label / "countries.json", countries)
        write(OUT / label / "rng.json", {"python": __import__("random").getstate(), "numpy": __import__("numpy").random.get_state()})
        runtime.data_store.flush()
        write(OUT / label / "manifest.json", runtime.data_store.history_manifest())
        runtime.advance_day()
        write(OUT / label / "day2-checkpoint.json", capture(runtime.state))
        print(json.dumps({"label": label, "countries": len(countries), "indices": len(data.indizes), "collisions": {c["country"]: c["collisions"] for c in countries if c["collisions"]}, "fields": {b: len(f) for b, f in inventories.items()}}))
    finally:
        runtime.close()


def source_fields(label):
    """All literal keyed writes in actual initialization call sites, with consumers."""
    calls = json.loads((OUT / label / "creation-calls.json").read_text(encoding="utf-8"))
    active = {(path.replace("\\", "/"), name) for path, name, _ in calls}
    writes = defaultdict(list)
    consumers = defaultdict(set)
    for path in [ROOT / "daten.py", *sorted((ROOT / "src").rglob("*.py"))]:
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node
        def function(node, parent=parent):
            while node in parent:
                node = parent[node]
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return node.name
            return "<module>"
        for node in ast.walk(tree):
            fn = function(node)
            location = f"{relative}:{node.lineno} ({fn})" if hasattr(node, "lineno") else relative
            key, expression = None, None
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str) and (relative, fn) in active:
                        writes[k.value].append({"location": location, "formula": ast.unparse(v)})
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                key = node.slice.value
                if isinstance(node.ctx, ast.Store) and (relative, fn) in active:
                    statement = parent[node]
                    expression = ast.unparse(statement.value) if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)) else ast.unparse(statement)
                elif isinstance(node.ctx, ast.Load):
                    consumers[key].add(location)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"setdefault", "get"} and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                key = node.args[0].value
                if node.func.attr == "setdefault" and (relative, fn) in active and len(node.args) > 1:
                    expression = ast.unparse(node.args[1])
                else:
                    consumers[key].add(location)
            if isinstance(node, ast.Call) and (relative, fn) in active:
                for keyword in node.keywords:
                    if keyword.arg:
                        writes[keyword.arg].append({"location": location, "formula": ast.unparse(keyword.value)})
            if key and expression:
                writes[key].append({"location": location, "formula": expression})
    write(OUT / "source-fields.json", {"writes": writes, "consumers": {k: sorted(v) for k, v in consumers.items()}})


def compare():
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    results, details = {}, {}
    for seed in (7, 42, 2307):
        before = read(OUT / f"before-{seed}/checkpoint.json")
        after = read(OUT / f"final-{seed}/checkpoint.json")
        changed_fields = [k for k in before["checkpoint"]
                          if before["checkpoint"][k] != after["checkpoint"][k]]
        assert changed_fields == ["indizes"]
        rng = before["rng"]["numpy"][1]
        assert "..." not in rng and len(rng.strip("[]").split()) == 624
        changed_indices = []
        for ticker, original in before["checkpoint"]["indizes"].items():
            fixed = after["checkpoint"]["indizes"][ticker]
            assert {k: v for k, v in original.items() if k != "constituents"} == {
                k: v for k, v in fixed.items() if k != "constituents"}
            assert sorted(original["constituents"].values()) == sorted(fixed["constituents"].values())
            if original["constituents"] != fixed["constituents"]:
                changed_indices.append(ticker)
        results[str(seed)] = {
            "day1_changed_fields": changed_fields,
            "day1_rng_exact": before["rng"] == after["rng"],
            "day2_exact": read(OUT / f"before-{seed}/day2-checkpoint.json") == read(OUT / f"final-{seed}/day2-checkpoint.json"),
            "all_340_displayed": sum(len(c["displayed_indices"]) for c in read(OUT / f"final-{seed}/countries.json")) == 340,
        }
        assert all(v for k, v in results[str(seed)].items() if k != "day1_changed_fields")
        details[str(seed)] = {"changed_membership_indices": changed_indices, "nonmembership_exact": True,
                              "same_weight_multisets": True, "numpy_state_all_624_words": True}
    write(OUT / "equivalence.json", results)
    write(OUT / "index-equivalence-details.json", details)
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "collect", "source", "compare"))
    parser.add_argument("--seed", type=int, default=2307)
    parser.add_argument("--label", default="before-2307")
    parser.add_argument("--warm", action="store_true")
    parser.add_argument("--reference", action="store_true")
    args = parser.parse_args()
    {"freeze": freeze, "collect": lambda: collect(args.seed, args.label, args.warm, args.reference),
     "source": lambda: source_fields(args.label), "compare": compare}[args.action]()
