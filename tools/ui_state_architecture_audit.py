"""Phase-one measurements only; no production imports are patched permanently.

Sections replays the exact diff algorithm on disjoint field groups. Codec group
measurements use the production binary codec, even for small groups. They are
isolated contribution estimates, not additive timings of mixed wire chunks.
All runtimes/databases/checkpoints live in the audit output directory.
"""
from __future__ import annotations

import argparse
import ast
import base64
import cProfile
import gc
import hashlib
import io
import inspect
import json
import os
from pathlib import Path
import pstats
import sys
import threading
import time
import tracemalloc
import zlib
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/ui-state-architecture-audit"
os.environ["KOJAK_AUDIT_OUTPUT"] = str(OUT)
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]

import kojakstreet.day_delta as dd
from kojakstreet.core.state import GameState
from kojakstreet.live_process import CURRENT_METHODS, economic_signature
import day_transition_audit as prior

BOOKS = {"stocks", "commodities", "processed_products", "cryptos", "funds", "indices", "derivatives"}
QUOTES = {"kurs", "aenderung", "market_cap", "aum", "name", "land", "ziel", "branche", "kategorie", "typ", "fund_type", "instrument_type"}
IO_FIELDS = {"company_inputs", "company_outputs", "company_input_quantities", "company_output_quantities", "regional_supply", "regional_demand", "production_capacity", "capacity_utilization", "capacity_growth", "supply", "demand", "inventories", "shortage", "price_pressure"}
PSYCHOLOGY = {"sentiment", "fear_greed", "open_interest", "long_short_ratio", "positioning", "market_regime", "fear", "euphoria", "crowding", "long_interest", "short_interest", "open_interest_ratio", "positioning_imbalance", "squeeze_pressure", "squeeze_type"}
STOCK_INTERNAL = {"hedge_profile", "hedge_summary", "credit_rating_pressure", "distress_months", "fundamental_repricing_days", "fundamental_repricing_remaining", "news_momentum", "operating_health", "production_score", "rating_migrations", "refinancing_momentum"}


def category(root, key=""):
    key = str(key)
    if root in BOOKS:
        if "history" in key or "historie" in key:
            return root + (".price_history" if key == "historie" else ".other_history")
        if key in QUOTES:
            return root + ".quotes_metadata"
        if root == "stocks" and (key in IO_FIELDS or key.startswith(("company_input", "company_output", "input_", "output_"))):
            return "stocks.input_output"
        if "psych" in key or key in PSYCHOLOGY:
            return root + ".psychology"
        if root == "stocks" and key in STOCK_INTERNAL:
            return "stocks.simulation_internal"
        if root == "funds" and any(s in key for s in ("holding", "allocation", "flow", "fee", "weight", "underlying")):
            return "funds.allocations_flows_fees"
        return root + ".detail_internal"
    if root == "macro":
        return "macro.history" if "history" in key or "historie" in key else "macro.current_trade"
    if root in {"date", "cash", "display_currency"}:
        return "global_status"
    return root


def project(values):
    groups = defaultdict(dict)
    for root, value in values.items():
        if root in BOOKS or root == "macro":
            for entity, fields in value.items():
                for key, item in fields.items():
                    if not str(key).startswith("_"):
                        group = groups[category(root, key)]
                        group.setdefault(root, {}).setdefault(entity, {})[key] = item
        else:
            groups[category(root)][root] = value
    return dict(groups)


def stats(value):
    counts = Counter()
    def visit(item, history=False):
        if isinstance(item, dict):
            counts["dict_fields"] += len(item)
            counts["containers"] += 1
            for key, child in item.items():
                visit(child, history or "history" in str(key) or "historie" in str(key))
        elif isinstance(item, (list, tuple)):
            counts["sequence_slots"] += len(item)
            counts["containers"] += 1
            if history and isinstance(item, list) and (not item or not isinstance(item[0], list)):
                counts["history_points"] += len(item)
            for child in item:
                visit(child, history)
        else:
            counts["scalar_values"] += 1
    visit(value)
    return dict(counts)


class CountingEncoder(dd.DayStateEncoder):
    def __init__(self):
        self.counts = Counter()

    def _mapping(self, old, new, path, changes):
        self.counts["mapping_calls"] += 1
        self.counts["dictionary_fields_visited"] += sum(not str(k).startswith("_") for k in new)
        return super()._mapping(old, new, path, changes)

    def _sequence(self, old, new, path, changes):
        self.counts["sequence_calls"] += 1
        self.counts["sequence_slots_available_for_comparison"] += len(old) + len(new)
        if old != new:
            self.counts["changed_sequences"] += 1
        return super()._sequence(old, new, path, changes)


class SectionEncoder(dd.DayStateEncoder):
    def _mapping(self, old, new, path, changes):
        if len(path) != 1:
            return super()._mapping(old, new, path, changes)
        start, cpu = time.perf_counter(), time.thread_time()
        result = super()._mapping(old, new, path, changes)
        self.sections[path[0]] = {"diff_ms": (time.perf_counter()-start)*1000, "diff_cpu_ms": (time.thread_time()-cpu)*1000}
        return result

    def _sequence(self, old, new, path, changes):
        if len(path) != 1:
            return super()._sequence(old, new, path, changes)
        start, cpu = time.perf_counter(), time.thread_time()
        result = super()._sequence(old, new, path, changes)
        self.sections[path[0]] = {"diff_ms": (time.perf_counter()-start)*1000, "diff_cpu_ms": (time.thread_time()-cpu)*1000}
        return result


def binary_encode(changes):
    chunks = []
    for offset in range(0, len(changes), 2048):
        stream = io.BytesIO()
        batch = [(op, tuple(path), (value[0], value[1], tuple(value[2])) if op == "splice" else value) for op, path, value in changes[offset:offset+2048]]
        dd._DataPickler(stream, protocol=5).dump(batch)
        chunks.append(base64.b64encode(zlib.compress(stream.getvalue(), level=1)).decode("ascii"))
    return {"version": 1, "base_revision": 0, "revision": 1, "codec": "data-pickle5-zlib1", "changes": chunks}


def timed(fn):
    start, cpu = time.perf_counter(), time.thread_time()
    result = fn()
    return result, {"ms": (time.perf_counter()-start)*1000, "cpu_ms": (time.thread_time()-cpu)*1000}


def write(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def replay_groups(old_values, new_values, traced=False):
    old_groups, new_groups = project(old_values), project(new_values)
    output = {}
    collecting = gc.isenabled()
    gc.disable()
    try:
        for name in sorted(set(old_groups) | set(new_groups)):
            old, new = old_groups.get(name, {}), new_groups.get(name, {})
            info = {"input": stats(new), "entities": sum(len(v) for k, v in new.items() if k in BOOKS or k == "macro")}
            info["field_names"] = sorted({str(field) for root, book in new.items() if root in BOOKS or root == "macro" for entity in book.values() for field in entity})
            if traced:
                gc.collect()
                tracemalloc.start(1)
                before = tracemalloc.take_snapshot()
                tracemalloc.reset_peak()
            # Timing the unmodified algorithm; counter traversal is separate.
            count_old = dd.public_copy(old)
            if traced:
                before = tracemalloc.take_snapshot()
                allocation_start = tracemalloc.get_traced_memory()[0]
                tracemalloc.reset_peak()
            changes = []
            plain = dd.DayStateEncoder.__new__(dd.DayStateEncoder)
            _, info["diff"] = timed(lambda: plain._mapping(old, new, [], changes))
            body, info["encode"] = timed(lambda: binary_encode(changes))
            prepared, info["decode"] = timed(lambda: dd.prepare_day_delta(body))
            if traced:
                current, peak = tracemalloc.get_traced_memory()
                after = tracemalloc.take_snapshot()
                differences = after.compare_to(before, "lineno")
                info["allocations"] = {"net_bytes": sum(x.size_diff for x in differences), "net_blocks": sum(x.count_diff for x in differences), "peak_extra_bytes": peak-allocation_start, "current_extra_bytes": current-allocation_start,
                    "top": [{"source": str(x.traceback), "bytes": x.size_diff, "blocks": x.count_diff} for x in differences[:8]]}
                tracemalloc.stop()
            counter = CountingEncoder()
            counted_changes = []
            counter._mapping(count_old, new, [], counted_changes)
            assert counted_changes == changes
            assert old == dd.public_copy(new)
            assert len(prepared["changes"]) == len(changes)
            info["traversal"] = dict(counter.counts)
            info["operations"] = len(changes)
            info["output"] = stats([c[2] for c in changes])
            info["history_tail_points"] = sum(len(c[2][2]) for c in changes if c[0] == "splice")
            info["wire_bytes_isolated"] = len(json.dumps(body, separators=(",", ":")).encode())
            raw = io.BytesIO()
            dd._DataPickler(raw, protocol=5).dump(changes)
            info["uncompressed_pickle_bytes"] = len(raw.getvalue())
            output[name] = info
    finally:
        if collecting:
            gc.enable()
        if tracemalloc.is_tracing():
            tracemalloc.stop()
    return output


def codec_profile(payload, label):
    parts = Counter()
    decoded = []
    collections = []
    original = gc.isenabled()
    gc.disable()
    try:
        for chunk in payload["changes"]:
            raw, t = timed(lambda: base64.b64decode(chunk, validate=True)); parts["base64_ms"] += t["ms"]
            blob, t = timed(lambda: zlib.decompress(raw)); parts["zlib_ms"] += t["ms"]
            batch, t = timed(lambda: dd._DataUnpickler(io.BytesIO(blob)).load()); parts["unpickle_ms"] += t["ms"]
            _, t = timed(lambda: decoded.extend(batch)); parts["extend_ms"] += t["ms"]
            if original:
                _, t = timed(lambda: gc.collect(0)); collections.append(t["ms"])
            _, t = timed(lambda: time.sleep(0)); parts["yield_ms"] += t["ms"]
        if original:
            _, t = timed(lambda: gc.collect(1)); parts["gc1_ms"] += t["ms"]
    finally:
        if original:
            gc.enable()
    parts["gc0_ms"] = sum(collections)
    profile = cProfile.Profile()
    profile.runcall(dd.prepare_day_delta, payload)
    profile.dump_stats(str(OUT / f"decode-{label}.pstats"))
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(25)
    (OUT / f"decode-{label}.txt").write_text(stream.getvalue(), encoding="utf-8")
    return {"parts": dict(parts), "gc0_chunks_ms": collections}


def sections(args):
    runtime = prior.make_runtime(OUT / f"sections-{args.label}", args.checkpoint)
    results = []
    try:
        initial = runtime.snapshot()
        encoder = SectionEncoder(initial)
        receiver = GameState(**dd.public_copy(dd.state_values(initial)))
        revision = 0
        for day in range(args.days):
            old = dd.public_copy(dd.state_values(runtime.snapshot()))
            encoder.sections = {}
            _, core = timed(runtime.advance_day)
            state, snapshot = timed(runtime.snapshot)
            original_encode = dd.encode_changes
            encode_metrics = {}
            def encode(changes):
                body, measurement = timed(lambda: original_encode(changes))
                encode_metrics.update(measurement)
                encode_metrics["operations"] = len(changes)
                return body
            dd.encode_changes = encode
            try:
                payload, delta = timed(lambda: encoder.update(state))
            finally:
                dd.encode_changes = original_encode
            text, json_encode = timed(lambda: json.dumps(payload, separators=(",", ":")))
            parsed, json_decode = timed(lambda: json.loads(text))
            prepared, decode = timed(lambda: dd.prepare_day_delta(parsed))
            revision, apply = timed(lambda: dd.apply_day_delta(receiver, prepared, revision))
            signature_before = economic_signature(runtime.daten)
            assert dd.state_values(receiver) == dd.public_copy(dd.state_values(state))
            current_rows = {}
            for table, method in CURRENT_METHODS.items():
                if not hasattr(runtime, method):
                    continue
                rows, measurement = timed(lambda method=method: getattr(runtime, method)())
                current_rows[table] = {**measurement, "rows": len(rows), "json_bytes": len(json.dumps(rows, default=str, separators=(",", ":")).encode()), "emitted_today": table in runtime.current_delta().tables}
            if day == 0 and not args.allocations:
                profile_encoder = dd.DayStateEncoder.__new__(dd.DayStateEncoder)
                profile_encoder.baseline = dd.public_copy(old)
                profile_encoder.revision = 0
                profile = cProfile.Profile()
                profile.runcall(profile_encoder.update, state)
                profile.dump_stats(str(OUT / f"generation-{args.label}.pstats"))
                stream = io.StringIO()
                pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(30)
                (OUT / f"generation-{args.label}.txt").write_text(stream.getvalue(), encoding="utf-8")
                del profile_encoder
            row = {"day": day + 1, "date": state.date.isoformat(), "core_and_record": core, "snapshot": snapshot, "day_delta": delta, "encode": encode_metrics,
                "json_encode": json_encode, "json_decode": json_decode, "decode": decode, "apply": apply, "wire_delta_bytes": len(text.encode()), "sections": encoder.sections,
                "current_rows": current_rows, "groups": replay_groups(old, dd.state_values(state), traced=args.allocations), "allocations_run": args.allocations}
            if not args.allocations:
                row["read_projection"] = projection_probe(runtime, state)
            if day == 0 and not args.allocations:
                row["codec_profile"] = codec_profile(payload, args.label)
                row["public_mirror"] = stats(dd.state_values(state))
            assert signature_before == economic_signature(runtime.daten)
            results.append(row)
            write(f"sections-{args.label}.json", {"label": args.label, "checkpoint": args.checkpoint, "rows": results, "exact_receiver_roundtrip": True, "economics_rng_unchanged_by_diagnostics": True})
            print(json.dumps({"label": args.label, "day": day+1, "delta_ms": delta["ms"], "decode_ms": decode["ms"], "bytes": len(text.encode())}), flush=True)
    finally:
        runtime.close()


def projection_probe(runtime, full_state):
    """Audit-only upper bound: all table rows including static metadata.

    Reads authoritative objects explicitly, never calls snapshot/full diff.
    This is not an implemented IPC contract or a UI performance claim.
    """
    from kojakstreet.core.market_data_service import MarketDataService
    def rows_from(state):
        return [(q.asset_type, q.ticker, q.data.get("name", q.ticker), q.region, q.sector,
                 q.data.get("fund_type", ""), q.data.get("instrument_type", ""),
                 q.price, q.change, q.market_cap) for q in MarketDataService(state).quotes()]
    def extract():
        status = runtime.snapshot_for_view("status")
        rows = rows_from(runtime.daten)
        ticker = []
        # Preserve the timer's existing daily-change ranking, not the separate
        # startup TopBar weekly-history calculation.
        for kind, count in (("Commodity", 2), ("Crypto", 2), ("Stock", 4), ("Index", 1000)):
            ticker.extend((r[1], r[7], r[8]) for r in sorted((r for r in rows if r[0] == kind), key=lambda r: r[8], reverse=True)[:count])
        return {"date": status.date.isoformat(), "cash": status.cash, "display_currency": status.display_currency, "rows": rows, "ticker": ticker}
    body, extraction = timed(extract)
    assert body["rows"] == rows_from(full_state), "Projection requires snapshot index market-cap fallback"
    text, encode = timed(lambda: json.dumps(body, separators=(",", ":")))
    parsed, decode = timed(lambda: json.loads(text))
    assert parsed["rows"] == [list(r) for r in body["rows"]]
    tickers = list(runtime.daten.aktien)
    selected = tickers[min(437, len(tickers)-1)]
    detail, detail_time = timed(lambda: dd.public_copy(runtime.daten.aktien[selected]))
    detail_json = json.dumps(detail, default=str, separators=(",", ":"))
    return {"all_table_rows": len(body["rows"]), "ticker_rows": len(body["ticker"]), "extract": extraction, "json_encode": encode, "json_decode": decode, "json_bytes": len(text.encode()),
        "selected_stock": selected, "full_selected_stock_public_copy": detail_time, "selected_stock_json_bytes": len(detail_json.encode()), "exact_quote_values_match_full_snapshot": True}


def consumers():
    rows = []
    for path in sorted((ROOT / "src/kojakstreet").rglob("*.py")):
        if "ui_qt" not in path.parts and path.parent.name != "core":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        refs, keys = [], []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in GameState.__dataclass_fields__:
                refs.append({"field": node.attr, "line": node.lineno, "expression": ast.unparse(node)})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                keys.append({"field": node.args[0].value, "line": node.lineno})
        if refs:
            rows.append({"file": str(path.relative_to(ROOT)), "state_refs": refs, "get_keys": keys})
    write("consumer-source-index.json", rows)


def multi_ui(args):
    """Reuse existing T0--T4/heartbeat harness and rotate the real nine views.

    Only the measurement driver's request scheduling is changed in memory.
    Actual timer callback, worker, IPC, views, paints and history waits run as
    shipped. View switches are measured outside normal tick intervals.
    """
    import kojakstreet.live_process as live_process
    decode_context = threading.local()
    original_prepare = live_process.prepare_day_delta
    def prepare(payload):
        decode_context.active = True
        start_cpu = time.thread_time()
        try:
            return original_prepare(payload)
        finally:
            if prior.audit.ACTIVE is not None:
                prior.audit.ACTIVE["spans"]["decode.thread_cpu"] += (time.thread_time() - start_cpu) * 1000
            decode_context.active = False
    live_process.prepare_day_delta = prepare
    for owner, name, label in ((base64, "b64decode", "base64"), (zlib, "decompress", "decompress"),
                              (dd._DataUnpickler, "load", "unpickle"), (time, "sleep", "yield"), (gc, "collect", "gc")):
        original = getattr(owner, name)
        def bind(original, label):
            def measured(*values, **kwargs):
                if not getattr(decode_context, "active", False):
                    return original(*values, **kwargs)
                suffix = str(values[0]) if label == "gc" and values else ""
                start_cpu = time.thread_time()
                try:
                    with prior.audit.span("decode." + label + suffix):
                        return original(*values, **kwargs)
                finally:
                    if prior.audit.ACTIVE is not None:
                        prior.audit.ACTIVE["spans"]["decode." + label + suffix + ".thread_cpu"] += (time.thread_time() - start_cpu) * 1000
            return measured
        setattr(owner, name, bind(original, label))
    source = inspect.getsource(prior.qt)
    if args.minimal_observer:
        if args.single_view != "markets":
            raise ValueError("Minimal paint observer control requires Markets")
        source = source.replace("app.installEventFilter(observer)", "window.markets_view.market_table.viewport().installEventFilter(observer)\n    window.top_bar.ticker_tape.installEventFilter(observer)\n    window.centralWidget().installEventFilter(observer)")
    source = source.replace("window.set_active_view(key)\n        app.processEvents()", "switch_start = time.perf_counter()\n        window.set_active_view(key)\n        app.processEvents()\n        cold_switches[key] = (time.perf_counter() - switch_start) * 1000")
    source = source.replace('ctx = {"row": None', 'cold_switches = {}\n    ctx = {"row": None')
    prior.__dict__["audit_view_sequence"] = (args.single_view,) if args.single_view else None
    source = source.replace('date = process._status_state.date.date()', '''view_sequence = audit_view_sequence or window.VIEW_ORDER
        next_view = view_sequence[len(ctx["records"]) % len(view_sequence)]
        switch_start = time.perf_counter()
        window.set_active_view(next_view)
        app.processEvents()
        switch_ms = (time.perf_counter() - switch_start) * 1000
        date = process._status_state.date.date()''')
    source = source.replace('row["main_thread"] = threading.get_ident()', 'row["view"] = next_view\n        row["switch_sync_ms"] = switch_ms\n        row["main_thread"] = threading.get_ident()')
    source = source.replace('window._request_simulation_steps(1, force_refresh=args.force_refresh)', 'window._on_timer_tick()')
    source = source.replace('row["t4"] = now', '''assert window.state.date == process.snapshot().date
        row["ticker_pending_at_t4"] = window.top_bar.ticker_tape.pending_items is not None
        row["ticker_current_matches_worker_at_t4"] = window.top_bar.ticker_tape._signature(window.top_bar.ticker_tape.items) == window.top_bar.ticker_tape._signature(process.ticker_tape_quotes())
        row["ticker_count"] = len(window.top_bar.ticker_tape.items)
        row["ticker_tile_width"] = window.top_bar.ticker_tape._tile_width()
        row["t4"] = now''')
    source = source.replace('"qt_platform": app.platformName()', '"cold_view_switch_including_process_events_ms": cold_switches, "qt_platform": app.platformName()')
    namespace = {}
    exec(compile(source, str(Path(__file__).resolve()), "exec"), prior.__dict__, namespace)
    ui_args = argparse.Namespace(days=args.days, name=args.label, checkpoint=args.checkpoint,
        display=args.display, chart="none", view="markets", force_refresh=False,
        manual_step=False, profile_ui=args.profile_ui, trace_ui=False, indicators=False, repeat_span=0)
    namespace["qt"](ui_args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("sections", "consumers", "ui"))
    parser.add_argument("--label", default="mature")
    parser.add_argument("--checkpoint")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--allocations", action="store_true")
    parser.add_argument("--single-view", choices=("markets", "supply_chain", "forex", "bondmarket", "portfolio", "macro", "trade_map", "global_macro", "news"))
    parser.add_argument("--display", choices=("windows", "offscreen"), default="offscreen")
    parser.add_argument("--minimal-observer", action="store_true")
    parser.add_argument("--profile-ui", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    write(f"environment-{args.mode}-{args.label}.json", {"python": sys.version, "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "src").rglob("*.py")},
        "method": "Unmodified full update, top-section diff timers; disjoint category replays; isolated production binary codec contributions; allocation runs excluded from latencies."})
    if args.mode == "consumers":
        consumers()
    elif args.mode == "ui":
        multi_ui(args)
    else:
        sections(args)


if __name__ == "__main__":
    main()
