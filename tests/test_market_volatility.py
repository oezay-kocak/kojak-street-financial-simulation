from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from kojakstreet.core import market_calculations


def test_open_ended_daily_volatility_allows_large_tail_moves(monkeypatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "lognormvariate", lambda _mu, _sigma: 12.0)

    volatility = market_calculations._open_ended_daily_volatility(
        0.01,
        1.25,
        0.80,
        tail_weight=1.0,
    )

    assert volatility > 0.50


def test_routine_daily_volatility_stays_orderly(monkeypatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 1.0)

    volatility = market_calculations._open_ended_daily_volatility(
        0.01,
        0.56,
        0.04,
        tail_weight=0.65,
    )

    assert 0.01 < volatility < 0.013


def test_tail_confluence_can_create_extreme_volatility(monkeypatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "lognormvariate", lambda _mu, _sigma: 18.0)

    volatility = market_calculations._open_ended_daily_volatility(
        0.012,
        0.82,
        0.20,
        tail_weight=0.75,
        asset_type="Stock",
        stress_score=3.2,
        euphoria_score=0.1,
    )

    assert volatility > 0.50


def test_crypto_price_move_uses_floor_instead_of_daily_crash_cap() -> None:
    price = market_calculations._apply_price_move(
        100.0,
        5.0,
        -1,
        asset_type="Crypto",
    )

    assert price == pytest.approx(0.6737946999085467, rel=1e-6)


def test_crypto_upside_move_is_not_capped_below_meme_squeeze_speed() -> None:
    price = market_calculations._apply_price_move(
        100.0,
        0.50,
        1,
        asset_type="Crypto",
    )

    assert price > 150.0


def test_asset_return_uses_long_lookback_window() -> None:
    asset = {"historie": [(100.0, "", "") for _ in range(200)]}
    asset["historie"][-1] = (260.0, "", "")

    assert market_calculations._asset_return(asset, 180) == pytest.approx(1.6)


def test_stock_price_move_allows_large_log_return_crash() -> None:
    price = market_calculations._apply_price_move(
        100.0,
        2.0,
        -1,
        asset_type="Stock",
    )

    assert price < 20.0


def test_commodity_daily_price_move_is_not_tightly_capped() -> None:
    price = market_calculations._apply_price_move(
        100.0,
        0.50,
        1,
        asset_type="Commodity",
    )

    assert price > 150.0


def test_commodity_downside_move_can_fall_more_than_old_daily_band() -> None:
    price = market_calculations._apply_price_move(
        100.0,
        0.50,
        -1,
        asset_type="Commodity",
    )

    assert price < 70.0


def test_commodity_price_anchor_resists_broad_collapse_and_bubbles() -> None:
    cheap_signal = market_calculations._commodity_price_anchor_signal({"kurs": 45.0})
    expensive_signal = market_calculations._commodity_price_anchor_signal({"kurs": 220.0})

    assert cheap_signal > 0.10
    assert expensive_signal < -0.10


def test_open_interest_tracks_perpetual_positioning() -> None:
    asset = {
        "kurs": 100.0,
        "market_cap": 1_000_000.0,
        "long_interest": 20_000.0,
        "short_interest": 16_000.0,
        "historie": [(100.0, "", ""), (104.0, "", "")],
    }
    state = SimpleNamespace(perpetuals={"AAA_LONG": {"ticker": "AAA", "typ": "LONG", "groesse": 10.0}})

    result = market_calculations._update_open_interest(state, "AAA", asset, "Stock", 0.55)

    assert asset["long_interest"] > asset["short_interest"]
    assert asset["open_interest"] == pytest.approx(asset["long_interest"] + asset["short_interest"])
    assert asset["open_interest_history"][-1] == pytest.approx((asset["long_interest"], asset["short_interest"]))
    assert result["volatility_multiplier"] >= 1.0


def test_short_squeeze_pressure_pushes_chance_up() -> None:
    asset = {
        "kurs": 100.0,
        "market_cap": 1_000_000.0,
        "long_interest": 5_000.0,
        "short_interest": 480_000.0,
        "news_momentum": 0.30,
        "historie": [(100.0, "", "") for _ in range(10)] + [(112.0, "", "")],
    }
    state = SimpleNamespace(perpetuals={})

    result = market_calculations._update_open_interest(state, "AAA", asset, "Stock", 0.70)

    assert result["squeeze_pressure"] > 0.0
    assert result["chance_impulse"] > 0.0
    assert asset["squeeze_type"] == "SHORT"


def test_long_squeeze_pressure_pushes_chance_down() -> None:
    asset = {
        "kurs": 100.0,
        "market_cap": 1_000_000.0,
        "long_interest": 480_000.0,
        "short_interest": 5_000.0,
        "news_momentum": -0.30,
        "historie": [(100.0, "", "") for _ in range(10)] + [(88.0, "", "")],
    }
    state = SimpleNamespace(perpetuals={})

    result = market_calculations._update_open_interest(state, "AAA", asset, "Stock", 0.30)

    assert result["squeeze_pressure"] < 0.0
    assert result["chance_impulse"] < 0.0
    assert asset["squeeze_type"] == "LONG"


def test_crypto_squeeze_has_stronger_volatility_multiplier() -> None:
    asset = {
        "kurs": 100.0,
        "market_cap": 1_000_000.0,
        "long_interest": 5_000.0,
        "short_interest": 720_000.0,
        "news_momentum": 0.35,
        "historie": [(100.0, "", "") for _ in range(10)] + [(116.0, "", "")],
    }
    state = SimpleNamespace(perpetuals={})

    result = market_calculations._update_open_interest(state, "CRY", asset, "Crypto", 0.72)

    assert result["squeeze_pressure"] > 0.0
    assert result["volatility_multiplier"] > 1.10
    assert asset["squeeze_type"] == "SHORT"
