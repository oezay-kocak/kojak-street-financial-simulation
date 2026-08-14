from __future__ import annotations

from kojakstreet.core.psychology import (
    daily_asset_psychology,
    ensure_asset_psychology,
    update_asset_expectations,
)


def test_negative_surprise_builds_fear() -> None:
    asset = {
        "revenue_growth": -0.08,
        "fcf_margin": 0.02,
        "previous_fcf_margin": 0.12,
        "eps": 1.0,
        "previous_eps": 5.0,
        "expectation": 0.08,
    }

    update_asset_expectations(asset, "Stock")

    assert asset["surprise"] < 0
    assert asset["fear"] > 0


def test_extreme_fear_creates_reversal_pressure_after_shock_fades() -> None:
    asset = {
        "historie": [(100.0, "d", ""), (80.0, "d", ""), (70.0, "d", "")],
        "fear": 2.2,
        "euphoria": 0.0,
        "sentiment": -1.0,
        "crowding": 1.0,
        "surprise": 0.0,
        "news_momentum": 0.0,
    }
    ensure_asset_psychology(asset)

    psychology = daily_asset_psychology(
        asset,
        "Stock",
        {
            "risk_appetite": 0.0,
            "fear": 0.0,
            "liquidity_confidence": 0.0,
            "inflation_fear": 0.0,
            "recession_fear": 0.0,
            "speculation": 0.0,
        },
    )

    assert psychology["signal"] > 0
    assert psychology["volatility_multiplier"] > 1.0


def test_neutral_psychology_does_not_create_excess_volatility() -> None:
    asset = {
        "historie": [(100.0, "d", ""), (100.4, "d", ""), (100.1, "d", "")],
        "surprise": 0.0,
        "news_momentum": 0.0,
    }

    psychology = daily_asset_psychology(
        asset,
        "Crypto",
        {
            "risk_appetite": 0.0,
            "fear": 0.0,
            "liquidity_confidence": 0.0,
            "inflation_fear": 0.0,
            "recession_fear": 0.0,
            "speculation": 0.0,
        },
    )

    assert psychology["volatility_multiplier"] < 1.10
