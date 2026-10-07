"""Time the real world/accounting split on isolated young and mature worlds."""

from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.accounting import convert_amount
from kojakstreet.core.checkpoints import decode, restore


def main():
    out = ROOT / ".cache/retail-decoupling"
    runtime = IntegratedRuntime(ROOT, data_dir=out / "accounting-probe-world", seed=1729)

    def buy(ticker):
        price = runtime.state.assets.price(ticker)
        region = runtime.state.assets.region(ticker)
        price_gd = convert_amount(runtime.daten, price, region, "GD")
        runtime.trading.trade_spot(ticker, min(1.0, 25.0 / price_gd), "BUY")

    samples = []
    try:
        for checkpoint in ("1990-01-10", "end"):
            payload = decode(json.loads((
                ROOT / f".cache/day-transition-audit/checkpoint-{checkpoint}.json"
            ).read_text(encoding="utf-8")))
            for case in ("no player", "mixed expiry"):
                for repeat in range(2):
                    restore(runtime.daten, payload)
                    runtime.state.sync_from_legacy()
                    runtime.market.warm_runtime_indexes()
                    d = runtime.daten
                    if case == "mixed expiry":
                        stock = next(t for t in d.aktien if t not in d.indizes)
                        for ticker in (stock, next(iter(d.kryptos)), next(iter(d.fonds)), "XAU"):
                            buy(ticker)
                        for kind in ("Option", "Credit Default Swap"):
                            ticker = next(t for t, a in d.derivatives.items() if a["instrument_type"] == kind)
                            buy(ticker)
                            d.depot[ticker]["expires_at"] = d.datum.isoformat()
                        ticker = next(t for t, a in d.derivatives.items() if a["instrument_type"] == "Commodity Future")
                        runtime.trading.open_future(ticker, "LONG", 2, 50)
                        next(p for p in d.perpetuals.values() if p["ticker"] == ticker)["expires_at"] = d.datum.isoformat()
                        runtime.trading.open_future(stock, "SHORT", 2, 50)
                        d.kredite["GD"] = 1000
                        d.anleihen.append({"typ": "STAAT", "land": "GD", "nominal": 1000,
                                          "zins": 0.04, "resttage": 1, "zinstage_zaehler": 179})
                    gc.collect()
                    gc.disable()
                    try:
                        started = time.perf_counter()
                        frame = runtime.simulation.prepare_world_day()
                        prepared = time.perf_counter()
                        runtime.simulation.commit_player_day(frame)
                        committed = time.perf_counter()
                    finally:
                        gc.enable()
                    row = {"checkpoint": checkpoint, "case": case, "repeat": repeat,
                           "world_ms": (prepared-started)*1000,
                           "player_commit_ms": (committed-prepared)*1000,
                           "date": d.datum.isoformat(), "active": d.SPIEL_AKTIV}
                    samples.append(row)
                    print(json.dumps(row), flush=True)
        (out / "accounting-probe.json").write_text(json.dumps(samples, indent=2), encoding="utf-8")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
