"""Controlled player-action ordering audit; never touches the user's game store."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]

from performance_remediation_determinism import digest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import capture, restore

PORTFOLIO = {
    "bargeld",
    "depot",
    "perpetuals",
    "anleihen",
    "kredite",
    "forex_depot",
    "DEPOT_VERMOEGEN_HISTORIE",
    "realisierte_guv_historie",
}
CONTROL = {"spiel_pausiert", "SPIEL_AKTIV", "turbo_modus", "intervall", "anzeige_waehrung"}


def signatures(runtime):
    payload = capture(runtime.daten)
    world = payload["checkpoint"]
    return {
        "world": {
            key: digest(value) for key, value in world.items() if key not in PORTFOLIO | CONTROL
        },
        "portfolio": {key: digest(value) for key, value in world.items() if key in PORTFOLIO},
        "control": {key: digest(value) for key, value in world.items() if key in CONTROL},
        "rng": digest(payload["rng"]),
        "date": runtime.daten.datum.isoformat(),
        "stock": {
            key: runtime.daten.aktien[stock][key]
            for key in ("kurs", "long_interest", "short_interest", "squeeze_pressure")
            if key in runtime.daten.aktien[stock]
        },
    }


def reset(runtime, baseline):
    restore(runtime.daten, baseline)
    runtime.state.sync_from_legacy()
    runtime.market.warm_runtime_indexes()


def step(runtime):
    runtime.simulation.step_day()
    runtime.state.sync_from_legacy()


def main():
    output = ROOT / ".cache/precompute-audit"
    output.mkdir(parents=True, exist_ok=True)
    directory = output / "branch-world-v2"
    if directory.exists():
        raise RuntimeError("Use fresh isolated evidence storage")
    runtime = IntegratedRuntime(ROOT, data_dir=directory, seed=1729)
    global stock
    stock = next(iter(runtime.daten.aktien))
    baseline = capture(runtime.daten)
    crypto = next(iter(runtime.daten.kryptos))
    commodity = "XAU"
    fund = next(iter(runtime.daten.fonds))
    option = next(
        key
        for key, value in runtime.daten.derivatives.items()
        if value.get("instrument_type") == "Option"
    )
    future = next(
        key
        for key, value in runtime.daten.derivatives.items()
        if value.get("instrument_type") == "Commodity Future"
    )
    region = runtime.daten.aktien[stock]["land"]
    target = next(key for key in runtime.daten.forex_depot if key not in {region, "GD"})
    actions = {
        "no action": lambda: None,
        "stock buy": lambda: runtime.trading.trade_spot(stock, 1, "BUY"),
        "stock sell": lambda: runtime.trading.trade_spot(stock, 1, "SELL"),
        "fund buy": lambda: runtime.trading.trade_spot(fund, 1, "BUY"),
        "commodity buy": lambda: runtime.trading.trade_spot(commodity, 1, "BUY"),
        "crypto buy": lambda: runtime.trading.trade_spot(crypto, 1, "BUY"),
        "option buy": lambda: runtime.trading.trade_spot(option, 1, "BUY"),
        "long open": lambda: runtime.trading.open_future(stock, "LONG", 5, 1000),
        "short open": lambda: runtime.trading.open_future(stock, "SHORT", 5, 1000),
        "short close": lambda: runtime.trading.close_future(f"{stock}_SHORT"),
        "dated future open": lambda: runtime.trading.open_future(future, "LONG", 2, 1000),
        "FX exchange": lambda: runtime.trading.exchange_currency("GD", target, 1000),
        "loan balance mutation (not exposed by Qt)": lambda: runtime.daten.kredite.update(
            {region: 1000}
        ),
        "corporate bond maturity (owned fixture; no Qt purchase route)": lambda: (
            runtime.daten.anleihen.append(
                {
                    "typ": "FIRMA",
                    "ticker": stock,
                    "land": region,
                    "nominal": 1000,
                    "zins": 0.03,
                    "resttage": 1,
                    "laufzeit_tage": 365,
                    "zinstage_zaehler": 179,
                }
            )
        ),
        "pause": lambda: runtime.set_running(False),
        "display currency": lambda: setattr(runtime.daten, "anzeige_waehrung", target),
    }
    results = []
    try:
        for day_kind, date in (
            ("normal", baseline["checkpoint"]["datum"].replace(year=1990, month=1, day=10)),
            ("report", baseline["checkpoint"]["datum"].replace(year=1990, month=1, day=15)),
        ):
            for name, action in actions.items():
                reset(runtime, baseline)
                runtime.daten.datum = date
                runtime.set_running(True)
                if name == "stock sell":
                    runtime.trading.trade_spot(stock, 2, "BUY")
                if name == "short close":
                    runtime.trading.open_future(stock, "SHORT", 5, 1000)
                initial = capture(runtime.daten)
                branches = []
                timings = []
                for before in (True, False):
                    reset(runtime, initial)
                    started = perf_counter()
                    if before:
                        action()
                    step(runtime)
                    if not before:
                        action()
                    first = signatures(runtime)
                    # A portfolio-triggered draw can affect only subsequent world days.
                    step(runtime)
                    branches.append((first, signatures(runtime)))
                    timings.append((perf_counter() - started) * 1000)
                left, right = branches
                result = {
                    "day_kind": day_kind,
                    "action": name,
                    "branch_ms": timings,
                    "day1": {},
                    "day2": {},
                    "before": left[0],
                    "after": right[0],
                }
                for index, day in enumerate(("day1", "day2")):
                    result[day] = {
                        section: [
                            key
                            for key in left[index][section]
                            if left[index][section][key] != right[index][section][key]
                        ]
                        for section in ("world", "portfolio", "control")
                    }
                    result[day]["rng_equal"] = left[index]["rng"] == right[index]["rng"]
                    result[day]["dates_equal"] = left[index]["date"] == right[index]["date"]
                results.append(result)
                print(day_kind, name, result["day1"], flush=True)
        (output / "branches.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
