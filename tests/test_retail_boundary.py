"""Retail ownership changes the player, never world books, histories or RNG."""

import random
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

import daten
from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import capture, restore
from kojakstreet.core.player_accounting import (
    PlayerDay,
    bond_credit_uniform,
    player_uniform,
    visible_news,
)

PLAYER = {
    "bargeld",
    "depot",
    "perpetuals",
    "anleihen",
    "kredite",
    "forex_depot",
    "DEPOT_VERMOEGEN_HISTORIE",
    "realisierte_guv_historie",
    "player_rng_state",
    "PLAYER_NEWS_SPEICHER",
}
CONTROL = {"spiel_pausiert", "SPIEL_AKTIV", "turbo_modus", "intervall", "anzeige_waehrung"}


@pytest.fixture(scope="module")
def retail_runtime(tmp_path_factory):
    namespace = dict(vars(daten))
    rng, np_rng = random.getstate(), np.random.get_state()
    runtime = IntegratedRuntime(Path.cwd(), data_dir=tmp_path_factory.mktemp("retail"), seed=1729)
    runtime.set_running(True)
    initial = capture(runtime.daten)
    try:
        yield runtime, initial
    finally:
        runtime.close()
        for key in set(vars(daten)) - set(namespace):
            delattr(daten, key)
        vars(daten).update(namespace)
        random.setstate(rng)
        np.random.set_state(np_rng)


def reset(runtime, payload):
    restore(runtime.daten, payload)
    runtime.state.sync_from_legacy()
    runtime.market.warm_runtime_indexes()


def signature(runtime, *, player=False):
    import hashlib
    import json

    from kojakstreet.core.checkpoints import encode

    payload = capture(runtime.daten)
    selected = {
        key: value
        for key, value in payload["checkpoint"].items()
        if (key in PLAYER) == player and key not in CONTROL
    }
    if not player:
        selected["rng"] = payload["rng"]
    return hashlib.sha256(json.dumps(encode(selected), sort_keys=True).encode()).hexdigest()


ACTIONS = (
    "stock_buy",
    "stock_sell",
    "fund_buy",
    "commodity_buy",
    "crypto_buy",
    "fx",
    "long",
    "short",
    "short_close",
    "future",
    "option",
    "cds",
    "bond",
    "loan",
    "margin_call",
    "liquidation",
)


def action(runtime, name):
    d = runtime.daten
    stock = next(t for t in d.aktien if t not in d.indizes)
    crypto = next(iter(d.kryptos))
    if name == "stock_buy":
        runtime.trading.trade_spot(stock, 2, "BUY")
    elif name == "stock_sell":
        runtime.trading.trade_spot(stock, 1, "SELL")
    elif name in {"fund_buy", "commodity_buy", "crypto_buy"}:
        ticker = {"fund_buy": next(iter(d.fonds)), "commodity_buy": "XAU", "crypto_buy": crypto}[
            name
        ]
        runtime.trading.trade_spot(ticker, 1, "BUY")
    elif name == "fx":
        runtime.trading.exchange_currency("GD", "Ameron", 10)
    elif name in {"long", "short", "liquidation"}:
        runtime.trading.open_future(stock, "SHORT" if name == "short" else "LONG", 5, 100)
        if name == "liquidation":
            d.perpetuals[f"{stock}_LONG"]["einstiegskurs"] = d.aktien[stock]["kurs"] * 10
    elif name == "short_close":
        runtime.trading.close_future(f"{stock}_SHORT")
    elif name in {"option", "cds", "future"}:
        kind = {"option": "Option", "cds": "Credit Default Swap", "future": "Commodity Future"}[
            name
        ]
        ticker = next(t for t, asset in d.derivatives.items() if asset["instrument_type"] == kind)
        if name == "future":
            runtime.trading.open_future(ticker, "LONG", 2, 100)
            position = next(p for p in d.perpetuals.values() if p["ticker"] == ticker)
            position["expires_at"] = d.datum.isoformat()
        else:
            runtime.trading.trade_spot(ticker, 1, "BUY")
            d.depot[ticker]["expires_at"] = d.datum.isoformat()
    elif name == "bond":
        d.anleihen.append(
            {
                "typ": "FIRMA",
                "ticker": stock,
                "land": d.aktien[stock]["land"],
                "nominal": 1000,
                "zins": 0.03,
                "resttage": 1,
                "laufzeit_tage": 365,
                "zinstage_zaehler": 179,
            }
        )
    elif name == "loan":
        d.kredite["GD"] = 1000
    elif name == "margin_call":
        d.bargeld = -50000


@pytest.mark.parametrize("date", ((1, 10), (1, 15), (1, 31), (12, 31)))
@pytest.mark.parametrize("name", ACTIONS)
def test_world_and_rng_are_identical_with_retail_actions(retail_runtime, date, name):
    runtime, initial = retail_runtime
    date = initial["checkpoint"]["datum"].replace(year=1990, month=date[0], day=date[1])
    reset(runtime, initial)
    runtime.daten.datum = date
    if name in {"stock_sell", "short_close"}:
        stock = next(t for t in runtime.daten.aktien if t not in runtime.daten.indizes)
        if name == "stock_sell":
            runtime.trading.trade_spot(stock, 2, "BUY")
        else:
            runtime.trading.open_future(stock, "SHORT", 5, 100)
    baseline = capture(runtime.daten)
    branches = []
    for trade in (False, True):
        reset(runtime, baseline)
        if trade:
            action(runtime, name)
        runtime.simulation.step_day()
        first = signature(runtime)
        if name != "margin_call":
            runtime.simulation.step_day()
        branches.append((first, signature(runtime), signature(runtime, player=True)))
    assert branches[0][:2] == branches[1][:2]
    assert branches[0][2] != branches[1][2]
    if name == "margin_call":
        assert not runtime.daten.SPIEL_AKTIV
        assert runtime.daten.datum == date + timedelta(days=1)
    if name == "liquidation":
        assert not runtime.daten.perpetuals
        assert any("LIQUIDATION" in row[1] for row in visible_news(runtime.daten))


def test_player_random_stream_save_restore_and_invalid_state_are_atomic(retail_runtime):
    runtime, initial = retail_runtime
    reset(runtime, initial)
    world_rng = random.getstate()
    value = player_uniform(runtime.daten, 0.01, 0.03)
    assert 0.01 <= value <= 0.03 and random.getstate() == world_rng
    saved = capture(runtime.daten)
    expected = [player_uniform(runtime.daten, 0.01, 0.03) for _ in range(5)]
    reset(runtime, saved)
    assert [player_uniform(runtime.daten, 0.01, 0.03) for _ in range(5)] == expected
    invalid = capture(runtime.daten)
    invalid["checkpoint"]["player_rng_state"] = ("broken",)
    before = signature(runtime, player=True)
    with pytest.raises((ValueError, TypeError)):
        restore(runtime.daten, invalid)
    assert signature(runtime, player=True) == before


def test_bond_credit_event_does_not_depend_on_amount_or_ownership(retail_runtime):
    runtime, initial = retail_runtime
    reset(runtime, initial)
    bond = {"ticker": next(iter(runtime.daten.aktien)), "symbol": "SAME-ISSUE", "nominal": 1000}
    rng = random.getstate()
    event = bond_credit_uniform(runtime.daten, bond)
    assert bond_credit_uniform(runtime.daten, {**bond, "nominal": 900000}) == event
    assert random.getstate() == rng


def test_accounting_uses_pre_policy_credit_marks(retail_runtime):
    runtime, initial = retail_runtime
    reset(runtime, initial)
    d = runtime.daten
    d.datum = initial["checkpoint"]["datum"].replace(year=1990, month=1, day=31)
    country = next(iter(d.makro))
    d.kredite[country] = 1000
    old_cash = d.forex_depot.get(country, 0.0)
    frame = runtime.simulation.prepare_world_day()
    assert d.forex_depot.get(country, 0.0) == old_cash
    expected_interest = 1000 * (frame.credit_rates[country]["zins"] + 0.06) / 365
    d.makro[country]["zins"] = 0.99
    runtime.simulation.commit_player_day(frame)
    assert d.forex_depot[country] == old_cash - expected_interest


@pytest.mark.parametrize("direction,pnl", (("LONG", 20.0), ("SHORT", -20.0)))
def test_expiring_future_preserves_margin_pnl_and_pre_roll_price(retail_runtime, direction, pnl):
    runtime, initial = retail_runtime
    reset(runtime, initial)
    d = runtime.daten
    ticker = next(t for t, a in d.derivatives.items() if a["instrument_type"] == "Commodity Future")
    frame = PlayerDay(d.datum, settlement_contracts={ticker: {"kurs": 110.0, "land": "GD"}})
    d.derivatives[ticker]["kurs"] = 999.0
    d.perpetuals["expiring"] = {
        "ticker": ticker, "typ": direction, "hebel": 2, "einstiegskurs": 100.0,
        "groesse": 2.0, "margin": 200.0, "land": "GD", "expires_at": d.datum.isoformat(),
    }
    old_cash = d.forex_depot["GD"]
    runtime.simulation.commit_player_day(frame)
    assert not d.perpetuals
    assert d.forex_depot["GD"] == old_cash + 200.0 + pnl
    assert d.realisierte_guv_historie[-1] == (frame.date, pnl)


def test_option_settlement_keeps_original_contract_currency_and_strike(retail_runtime):
    from kojakstreet.core.accounting import convert_amount

    runtime, initial = retail_runtime
    reset(runtime, initial)
    d = runtime.daten
    ticker = next(t for t, a in d.derivatives.items() if a["instrument_type"] == "Option")
    frame = PlayerDay(d.datum, settlement_contracts={ticker: {"kurs": 20.0, "land": "Ameron"}})
    d.derivatives[ticker].update(kurs=999.0, land="GD", strike_price=900.0)
    d.rohstoffe["XAU"]["kurs"] = 120.0
    d.depot[ticker] = {
        "instrument_type": "Option", "stueck": 3, "kaufkurs": 4.0,
        "underlying": "XAU", "underlying_type": "Commodity", "strike_price": 100.0,
        "option_type": "CALL", "expires_at": d.datum.isoformat(),
    }
    before = d.forex_depot.get("Ameron", 0.0)
    expected_pnl = convert_amount(d, 48.0, "Ameron", "GD")
    runtime.simulation.commit_player_day(frame)
    assert ticker not in d.depot
    assert d.forex_depot["Ameron"] == before + 60.0
    assert d.realisierte_guv_historie[-1] == (frame.date, expected_pnl)


def test_cds_default_uses_full_world_rating_after_credit_marks(retail_runtime):
    from kojakstreet.core.accounting import convert_amount
    from kojakstreet.core.financial_products import CDS_CONTRACT_SCALE

    runtime, initial = retail_runtime
    reset(runtime, initial)
    d = runtime.daten
    ticker = next(t for t, a in d.derivatives.items() if a["instrument_type"] == "Credit Default Swap")
    country = str(d.derivatives[ticker]["underlying"])
    d.makro[country]["rating"] = "D"
    d.kredite[country] = 1000.0
    frame = PlayerDay(
        d.datum, credit_rates={country: {"zins": 0.02}},
        settlement_contracts={ticker: {"kurs": 5.0, "land": country}},
    )
    d.depot[ticker] = {
        "instrument_type": "Credit Default Swap", "stueck": 2, "kaufkurs": 5.0,
        "underlying": country, "underlying_type": "Sovereign", "notional": 1000000,
        "recovery_rate": 0.4, "expires_at": (d.datum + timedelta(days=90)).isoformat(),
    }
    payout = 2 * (1000000 / CDS_CONTRACT_SCALE) * 0.6
    before = d.forex_depot.get(country, 0.0)
    expected_cash = before - 1000 * (0.02 + 0.06) / 365 + payout
    expected_pnl = convert_amount(d, payout - 10.0, country, "GD")
    runtime.simulation.commit_player_day(frame)
    assert ticker not in d.depot
    assert d.forex_depot[country] == expected_cash
    assert d.realisierte_guv_historie[-1] == (frame.date, expected_pnl)


def test_lifecycle_pays_prior_events_then_removes_holdings_and_recovers_bond(retail_runtime):
    from kojakstreet.core.ratings import RECOVERY_RATE

    runtime, initial = retail_runtime
    reset(runtime, initial)
    d = runtime.daten
    stock, crypto = next(iter(d.aktien)), next(iter(d.kryptos))
    d.depot.update({stock: {"stueck": 4}, crypto: {"stueck": 3}})
    d.perpetuals["retired"] = {"ticker": crypto}
    d.anleihen.append({"typ": "FIRMA", "ticker": stock, "nominal": 1000, "land": "GD"})
    multiplier = player_uniform(d, 0.01, 0.03)
    del d.player_rng_state
    frame = PlayerDay(d.datum, events=[
        ("dividend", stock, 10.0, 0.005, "GD"),
        ("crypto_fee", crypto, 5.0, "GD"),
        ("company_default", stock), ("crypto_delist", crypto),
    ])
    before, world_rng = d.forex_depot["GD"], random.getstate()
    expected = before + 4 * 10.0 * 0.005
    expected += 5.0 * 3 * multiplier
    expected += 1000 * RECOVERY_RATE
    runtime.simulation.commit_player_day(frame)
    assert not d.depot and not d.perpetuals and not d.anleihen
    assert d.forex_depot["GD"] == expected
    assert random.getstate() == world_rng


def test_held_excess_crypto_is_delisted_by_world_criteria(retail_runtime):
    from kojakstreet.core.cryptos import TARGET_CRYPTO_COUNT, _trim_excess_universe

    runtime, initial = retail_runtime
    reset(runtime, initial)
    d = runtime.daten
    template = next(iter(d.kryptos.values()))
    ticker = "RETAIL-EXCESS"
    d.kryptos[ticker] = {**template, "market_share": -1.0, "kurs": 0.01}
    d.depot[ticker] = {"stueck": 1000}
    d.perpetuals["excess"] = {"ticker": ticker}
    frame = PlayerDay(d.datum)
    d._player_day_frame = frame
    try:
        _trim_excess_universe(d)
    finally:
        d._player_day_frame = None
    assert len(d.kryptos) == TARGET_CRYPTO_COUNT and ticker not in d.kryptos
    assert ticker in d.depot and "excess" in d.perpetuals
    frame.apply_events(d)
    assert ticker not in d.depot and "excess" not in d.perpetuals


@pytest.mark.parametrize("corporate,event", ((True, 0.0), (True, 1.0), (False, 0.0)))
def test_mature_bond_preserves_final_coupon_and_principal_outcome(retail_runtime, monkeypatch, corporate, event):
    from kojakstreet.core import bond_calculations

    runtime, initial = retail_runtime
    reset(runtime, initial)
    d = runtime.daten
    ticker = next(iter(d.aktien))
    d.anleihen.append({
        "typ": "FIRMA" if corporate else "STAAT", "ticker": ticker, "land": "GD",
        "nominal": 1000.0, "zins": 0.04, "resttage": 1,
        "laufzeit_tage": 365, "zinstage_zaehler": 179,
    })
    monkeypatch.setattr(bond_calculations, "bond_credit_uniform", lambda *_: event)
    before, rng = d.forex_depot["GD"], random.getstate()
    coupon = 1000 * (0.04 * (180 / 365))
    principal = 0.0 if corporate and event == 0.0 else 1000.0
    frame = PlayerDay(d.datum)
    runtime.simulation.commit_player_day(frame)
    assert d.forex_depot["GD"] == before + coupon + principal
    assert d.realisierte_guv_historie[-1] == (frame.date, coupon)
    assert not d.anleihen and random.getstate() == rng


def test_player_messages_do_not_displace_world_news(retail_runtime):
    runtime, initial = retail_runtime
    reset(runtime, initial)
    original = list(runtime.daten.NEWS_SPEICHER)
    for n in range(60):
        runtime.simulation.add_player_news(f"LIQUIDATION {n}", "ROT")
    assert runtime.daten.NEWS_SPEICHER == original
    assert len(runtime.daten.PLAYER_NEWS_SPEICHER) == 50
    assert len(visible_news(runtime.daten)) == 50


def test_save_load_replays_actual_crypto_report_and_pause_preserves_date(retail_runtime):
    runtime, initial = retail_runtime
    reset(runtime, initial)
    runtime.daten.datum = initial["checkpoint"]["datum"].replace(year=1990, month=1, day=14)
    action(runtime, "crypto_buy")
    action(runtime, "stock_buy")
    runtime.set_running(False)
    date = runtime.daten.datum
    runtime.simulation.step_day()
    assert runtime.daten.datum == date
    runtime.save_game()
    saved = signature(runtime), signature(runtime, player=True)
    runtime.advance_days(2)
    assert hasattr(runtime.daten, "player_rng_state")
    expected = signature(runtime), signature(runtime, player=True)
    runtime.load_game()
    assert (signature(runtime), signature(runtime, player=True)) == saved
    assert runtime.daten.spiel_pausiert
    runtime.advance_days(2)
    assert (signature(runtime), signature(runtime, player=True)) == expected


def test_runtime_keeps_margin_call_paused_after_completing_world_day(retail_runtime):
    runtime, initial = retail_runtime
    reset(runtime, initial)
    runtime.set_running(True)
    date = runtime.daten.datum
    runtime.daten.bargeld = -50000
    runtime.advance_day()
    assert runtime.daten.datum == date + timedelta(days=1)
    assert not runtime.daten.SPIEL_AKTIV and runtime.daten.spiel_pausiert
    assert not runtime.running
    runtime.advance_day()
    assert runtime.daten.datum == date + timedelta(days=1)
    assert runtime.daten.spiel_pausiert
