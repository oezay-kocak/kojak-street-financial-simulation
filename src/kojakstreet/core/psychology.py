"""Market psychology layer: expectations, surprise, sentiment and crowding."""

from __future__ import annotations

from collections.abc import Mapping


def ensure_market_psychology(daten_module) -> None:
    if not hasattr(daten_module, "market_psychology"):
        daten_module.market_psychology = {
            "risk_appetite": 0.0,
            "fear": 0.0,
            "liquidity_confidence": 0.0,
            "inflation_fear": 0.0,
            "recession_fear": 0.0,
            "speculation": 0.0,
        }
    signature = (
        tuple(getattr(daten_module, "aktien", {}).keys()),
        tuple(getattr(daten_module, "rohstoffe", {}).keys()),
        tuple(getattr(daten_module, "kryptos", {}).keys()),
    )
    if getattr(daten_module, "_psychology_assets_ready_signature", None) == signature:
        return
    for asset in getattr(daten_module, "aktien", {}).values():
        ensure_asset_psychology(asset)
    for asset in getattr(daten_module, "rohstoffe", {}).values():
        ensure_asset_psychology(asset)
    for asset in getattr(daten_module, "kryptos", {}).values():
        ensure_asset_psychology(asset)
    daten_module._psychology_assets_ready_signature = signature


def update_market_psychology(daten_module) -> dict[str, float]:
    ensure_market_psychology(daten_module)
    macro = getattr(daten_module, "global_macro", {})
    state = daten_module.market_psychology
    vix = float(macro.get("vix", 18.0))
    net_history = getattr(daten_module, "GLOBAL_MACRO_HISTORIE", {}).get("net_liquidity", [])
    current_net = float(macro.get("net_liquidity", 1.0))
    previous_net = _history_value(net_history[-2]) if len(net_history) >= 2 else current_net
    liquidity_impulse = _percent_change(current_net, previous_net)
    curve = float(macro.get("yield_curve_3y10y", macro.get("yield_curve_1y10y", 0.01)))
    growth = float(macro.get("global_gdp_growth", 0.01))
    cpi = float(macro.get("global_cpi", 0.02))
    unemployment = float(macro.get("global_unemployment", 0.06))

    targets = {
        "risk_appetite": (liquidity_impulse * 18.0) + (growth * 8.0) - max(0.0, vix - 18.0) / 35.0,
        "fear": max(0.0, (vix - 18.0) / 24.0) + max(0.0, -curve) * 12.0,
        "liquidity_confidence": liquidity_impulse * 25.0,
        "inflation_fear": max(0.0, cpi - 0.03) * 18.0,
        "recession_fear": max(0.0, -growth) * 16.0 + max(0.0, unemployment - 0.07) * 10.0,
        "speculation": max(0.0, liquidity_impulse) * 16.0 + max(0.0, 18.0 - vix) / 24.0,
    }
    for key, target in targets.items():
        state[key] = _smooth(float(state.get(key, 0.0)), _clamp(target, -2.0, 2.0), 0.10)
    return dict(state)


def ensure_asset_psychology(asset: dict) -> None:
    if asset.get("_psychology_ready") is True:
        return
    asset.setdefault("sentiment", 0.0)
    asset.setdefault("fear", 0.0)
    asset.setdefault("euphoria", 0.0)
    asset.setdefault("crowding", 0.0)
    asset.setdefault("expectation", 0.0)
    asset.setdefault("surprise", 0.0)
    asset["_psychology_state"] = [
        float(asset.get("fear", 0.0)),
        float(asset.get("euphoria", 0.0)),
        float(asset.get("sentiment", 0.0)),
        float(asset.get("crowding", 0.0)),
        float(asset.get("surprise", 0.0)),
    ]
    asset["_psychology_ready"] = True


def update_asset_expectations(asset: dict, asset_type: str) -> None:
    ensure_asset_psychology(asset)
    state = _psychology_state(asset)
    actual = _actual_fundamental_score(asset, asset_type)
    expectation = float(asset.get("expectation", actual))
    surprise = actual - expectation
    state[4] = surprise
    asset["expectation"] = _smooth(expectation, actual, 0.25)
    if surprise < 0:
        state[0] = _clamp(state[0] * 0.90 + abs(surprise) * 2.2, 0.0, 3.0)
    elif surprise > 0:
        state[1] = _clamp(state[1] * 0.90 + surprise * 2.2, 0.0, 3.0)
    _sync_psychology_fields(asset, state)


def daily_asset_psychology(
    asset: dict,
    asset_type: str,
    market_psychology: Mapping[str, float],
) -> dict[str, float]:
    signal, volatility_multiplier, fear, euphoria, sentiment = daily_asset_psychology_values(
        asset,
        asset_type,
        market_psychology,
    )
    return {
        "signal": signal,
        "volatility_multiplier": volatility_multiplier,
        "fear": fear,
        "euphoria": euphoria,
        "sentiment": sentiment,
    }


def daily_asset_psychology_values(
    asset: dict,
    asset_type: str,
    market_psychology: Mapping[str, float],
    macro_bias: float | None = None,
    *,
    assume_ready: bool = False,
) -> tuple[float, float, float, float, float]:
    if not assume_ready:
        ensure_asset_psychology(asset)
    momentum, longer_momentum = _asset_price_momenta(asset, (8, 35))
    state = _psychology_state(asset)
    fear = state[0]
    euphoria = state[1]
    sentiment = state[2]
    crowding = state[3]
    surprise = state[4]
    news_momentum = float(asset.get("news_momentum", asset.get("netzwerk_aktivitaet", 0.0) * 0.04))
    immediate_shock = (news_momentum * 1.10) + (surprise * 1.75)
    if macro_bias is None:
        macro_bias = market_psychology_bias(asset_type, market_psychology)

    fear = (fear * 0.82) + max(0.0, -immediate_shock) * 0.90 + max(0.0, -momentum) * 1.45
    euphoria = (euphoria * 0.82) + max(0.0, immediate_shock) * 0.80 + max(0.0, momentum) * 1.15
    sentiment = (sentiment * 0.86) + (immediate_shock * 0.65) + (momentum * 0.35) + macro_bias
    crowding = (crowding * 0.90) + max(0.0, abs(sentiment) - 1.15) * 0.10

    panic_reversal = max(0.0, fear - 1.35) * 0.13
    euphoria_reversal = max(0.0, euphoria - 1.35) * 0.12
    exhaustion = max(0.0, crowding - 0.90) * 0.06
    reversal_signal = panic_reversal - euphoria_reversal - (exhaustion if sentiment > 0 else -exhaustion)
    signal = (sentiment * 0.035) + (immediate_shock * 0.18) + reversal_signal + macro_bias
    shock_intensity = max(0.0, abs(immediate_shock) - 0.08)
    volatility_multiplier = 1.0 + shock_intensity * 2.4
    volatility_multiplier += max(0.0, fear - 0.80) * 0.22
    volatility_multiplier += max(0.0, euphoria - 0.80) * 0.18
    volatility_multiplier += max(0.0, crowding - 0.90) * 0.12
    volatility_multiplier += max(0.0, abs(longer_momentum) - 0.12) * 1.6

    state[0] = _clamp(fear, 0.0, 3.5)
    state[1] = _clamp(euphoria, 0.0, 3.5)
    state[2] = _clamp(sentiment, -4.0, 4.0)
    state[3] = _clamp(crowding, 0.0, 4.0)
    state[4] = surprise * 0.94
    _sync_psychology_fields(asset, state)
    return signal, volatility_multiplier, state[0], state[1], state[2]


def market_psychology_bias(asset_type: str, psychology: Mapping[str, float]) -> float:
    return _macro_psychology_bias(asset_type, psychology)


def _actual_fundamental_score(asset: dict, asset_type: str) -> float:
    if asset_type == "Stock":
        revenue_growth = float(asset.get("revenue_growth", 0.0))
        fcf_delta = float(asset.get("fcf_margin", 0.0)) - float(asset.get("previous_fcf_margin", 0.0))
        eps_previous = max(0.1, float(asset.get("previous_eps", asset.get("eps", 0.1))))
        eps_growth = (float(asset.get("eps", eps_previous)) - eps_previous) / eps_previous
        return revenue_growth + fcf_delta * 0.8 + eps_growth * 0.35
    if asset_type == "Commodity":
        return (
            float(asset.get("demand_change", 0.0))
            - float(asset.get("production_change", 0.0)) * 0.6
            - float(asset.get("inventories_change", 0.0)) * 0.8
            + float(asset.get("extraction_cost_change", 0.0)) * 0.4
        )
    if asset_type == "Crypto":
        return (
            float(asset.get("transaction_change", 0.0))
            + float(asset.get("fee_change", 0.0)) * 0.65
            + float(asset.get("wallet_change", 0.0)) * 0.75
            - float(asset.get("inflation_rate", 0.0)) * 1.1
        )
    return 0.0


def _macro_psychology_bias(asset_type: str, psychology: Mapping[str, float]) -> float:
    risk = float(psychology.get("risk_appetite", 0.0))
    fear = float(psychology.get("fear", 0.0))
    liquidity = float(psychology.get("liquidity_confidence", 0.0))
    inflation = float(psychology.get("inflation_fear", 0.0))
    recession = float(psychology.get("recession_fear", 0.0))
    speculation = float(psychology.get("speculation", 0.0))
    if asset_type == "Stock":
        return (risk * 0.040) + (liquidity * 0.030) - (fear * 0.045) - (recession * 0.040)
    if asset_type == "Crypto":
        return (risk * 0.050) + (liquidity * 0.060) + (speculation * 0.040) - (fear * 0.030)
    if asset_type == "Commodity":
        return (inflation * 0.040) - (recession * 0.025) + (fear * 0.010)
    return 0.0


def _asset_price_momentum(asset: dict, lookback: int) -> float:
    return _asset_price_momenta(asset, (lookback,))[0]


def _asset_price_momenta(asset: dict, lookbacks: tuple[int, ...]) -> tuple[float, ...]:
    history = asset.get("historie", [])
    if not lookbacks:
        return ()
    if not history:
        return tuple(0.0 for _lookback in lookbacks)
    cache = asset.setdefault("_momentum_cache", {})
    history_len = len(history)
    current = _history_value_safe(history[-1])
    values = []
    for lookback in lookbacks:
        if history_len <= lookback:
            values.append(0.0)
            continue
        cache_key = str(lookback)
        cached = cache.get(cache_key, {})
        previous = _history_value_safe(history[-1 - lookback])
        if (
            cached.get("length") == history_len
            and cached.get("current") == current
            and cached.get("previous") == previous
        ):
            values.append(float(cached.get("momentum", 0.0)))
            continue
        momentum = ((current - previous) / previous) if previous > 0 else 0.0
        cache[cache_key] = {
            "length": history_len,
            "current": current,
            "previous": previous,
            "momentum": momentum,
        }
        values.append(momentum)
    return tuple(values)


def _psychology_state(asset: dict) -> list[float]:
    state = asset.get("_psychology_state")
    if isinstance(state, list) and len(state) == 5:
        return state
    state = [
        float(asset.get("fear", 0.0)),
        float(asset.get("euphoria", 0.0)),
        float(asset.get("sentiment", 0.0)),
        float(asset.get("crowding", 0.0)),
        float(asset.get("surprise", 0.0)),
    ]
    asset["_psychology_state"] = state
    return state


def _sync_psychology_fields(asset: dict, state: list[float]) -> None:
    asset["fear"] = state[0]
    asset["euphoria"] = state[1]
    asset["sentiment"] = state[2]
    asset["crowding"] = state[3]
    asset["surprise"] = state[4]


def _price_momentum(history: list, lookback: int) -> float:
    if len(history) <= lookback:
        return 0.0
    current = _history_value_safe(history[-1])
    previous = _history_value_safe(history[-1 - lookback])
    if previous <= 0:
        return 0.0
    return (current - previous) / previous


def _history_value(entry) -> float:
    return float(entry[0] if isinstance(entry, (tuple, list)) else entry)


def _history_value_safe(entry) -> float:
    try:
        return float(entry[0] if isinstance(entry, (tuple, list)) else entry)
    except (TypeError, ValueError):
        return 0.0


def _percent_change(current: float, previous: float) -> float:
    return (current - previous) / previous if previous else 0.0


def _smooth(current: float, target: float, speed: float) -> float:
    return current + (target - current) * speed


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
