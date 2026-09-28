"""Portfolio analytics for read-only UI summaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kojakstreet.core.state import GameState
from kojakstreet.core.accounting import convert_amount


@dataclass(slots=True)
class PositionAnalytics:
    ticker: str
    name: str
    quantity: float
    average_price: float
    last_price: float
    value_local: float
    cost_local: float
    pnl_local: float
    pnl_percent: float
    region: str
    sector: str
    asset_type: str


@dataclass(slots=True)
class PortfolioAnalytics:
    positions: list[PositionAnalytics] = field(default_factory=list)
    total_value_gd: float = 0.0
    total_cost_gd: float = 0.0
    unrealized_pnl_gd: float = 0.0
    unrealized_pnl_percent: float = 0.0
    region_exposure: dict[str, float] = field(default_factory=dict)
    sector_exposure: dict[str, float] = field(default_factory=dict)
    asset_type_exposure: dict[str, float] = field(default_factory=dict)
    gross_exposure_gd: float = 0.0
    leveraged_exposure_gd: float = 0.0


def build_portfolio_analytics(state: GameState) -> PortfolioAnalytics:
    assets = _all_assets(state)
    positions: list[PositionAnalytics] = []
    region_exposure: dict[str, float] = {}
    sector_exposure: dict[str, float] = {}
    asset_type_exposure: dict[str, float] = {}

    for ticker, position in state.portfolio.items():
        asset = assets.get(ticker, {})
        quantity = float(position.get("stueck", 0.0))
        average_price = float(position.get("kaufkurs", 0.0))
        last_price = float(asset.get("kurs", 0.0))
        value_local = quantity * last_price
        cost_local = quantity * average_price
        pnl_local = value_local - cost_local
        pnl_percent = (pnl_local / cost_local * 100.0) if cost_local else 0.0
        region = str(asset.get("land", asset.get("ziel", "GD")))
        sector = str(asset.get("branche", asset.get("kategorie", asset.get("typ", "Other"))))
        asset_type = _asset_type_for_ticker(state, ticker)

        positions.append(
            PositionAnalytics(
                ticker=ticker,
                name=str(asset.get("name", ticker)),
                quantity=quantity,
                average_price=average_price,
                last_price=last_price,
                value_local=value_local,
                cost_local=cost_local,
                pnl_local=pnl_local,
                pnl_percent=pnl_percent,
                region=region,
                sector=sector,
                asset_type=asset_type,
            )
        )

        region_exposure[region] = region_exposure.get(region, 0.0) + convert_amount(state, value_local, region, "GD")
        sector_exposure[sector] = sector_exposure.get(sector, 0.0) + convert_amount(state, value_local, region, "GD")
        asset_type_exposure[asset_type] = asset_type_exposure.get(asset_type, 0.0) + convert_amount(state, value_local, region, "GD")

    total_value = sum(convert_amount(state, p.value_local, p.region, "GD") for p in positions)
    total_cost = sum(convert_amount(state, p.cost_local, p.region, "GD") for p in positions)
    leveraged_exposure = 0.0
    for position in state.perpetuals.values():
        ticker = str(position.get("ticker", ""))
        asset = assets.get(ticker, {})
        price = float(asset.get("kurs", position.get("einstiegskurs", 0.0)))
        exposure = abs(float(position.get("groesse", 0.0)) * price)
        exposure = convert_amount(state, exposure, str(position.get("land", asset.get("land", "GD"))), "GD")
        leveraged_exposure += exposure
        asset_type = _asset_type_for_ticker(state, ticker)
        region = str(position.get("land", asset.get("land", "GD")))
        asset_type_exposure[asset_type] = asset_type_exposure.get(asset_type, 0.0) + exposure
        region_exposure[region] = region_exposure.get(region, 0.0) + exposure
    pnl = total_value - total_cost
    pnl_percent = (pnl / total_cost * 100.0) if total_cost else 0.0

    return PortfolioAnalytics(
        positions=positions,
        total_value_gd=total_value,
        total_cost_gd=total_cost,
        unrealized_pnl_gd=pnl,
        unrealized_pnl_percent=pnl_percent,
        region_exposure=region_exposure,
        sector_exposure=sector_exposure,
        asset_type_exposure=asset_type_exposure,
        gross_exposure_gd=total_value + leveraged_exposure,
        leveraged_exposure_gd=leveraged_exposure,
    )


def _all_assets(state: GameState) -> dict[str, dict[str, Any]]:
    assets = {}
    assets.update(state.stocks)
    assets.update(state.commodities)
    assets.update(state.cryptos)
    assets.update(state.funds)
    assets.update(state.indices)
    assets.update(state.derivatives)
    return assets


def _asset_type_for_ticker(state: GameState, ticker: str) -> str:
    if ticker in state.stocks:
        return "Stock"
    if ticker in state.commodities:
        return "Commodity"
    if ticker in state.cryptos:
        return "Crypto"
    if ticker in state.funds:
        return "Fund"
    if ticker in state.indices:
        return "Index"
    if ticker in state.derivatives:
        return "Derivative"
    return "Other"
