"""Central market-data access for legacy modules, runtime state and UI snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kojakstreet.core.countries import RESERVE_CURRENCY


@dataclass(frozen=True, slots=True)
class AssetQuote:
    ticker: str
    asset_type: str
    data: dict[str, Any]
    price: float
    change: float
    market_cap: float
    region: str
    sector: str


class MarketDataService:
    """Read-only asset lookup across all in-memory asset universes."""

    def __init__(self, state: Any) -> None:
        self.state = state

    def asset_books(self) -> tuple[tuple[str, dict[str, dict[str, Any]]], ...]:
        return (
            ("Stock", _book(self.state, "aktien", "stocks")),
            ("Commodity", _book(self.state, "rohstoffe", "commodities")),
            ("Crypto", _book(self.state, "kryptos", "cryptos")),
            ("Fund", _book(self.state, "fonds", "funds")),
            ("Index", _book(self.state, "indizes", "indices")),
            ("Derivative", _book(self.state, "derivatives", "derivatives")),
        )

    def get(self, ticker: str) -> dict[str, Any] | None:
        for _asset_type, book in self.asset_books():
            if ticker in book:
                return book[ticker]
        return None

    def asset_type(self, ticker: str) -> str:
        for asset_type, book in self.asset_books():
            if ticker in book:
                return asset_type
        return "Other"

    def price(self, ticker: str) -> float | None:
        asset = self.get(ticker)
        if asset is None:
            return None
        try:
            return float(asset.get("kurs", asset.get("price", 0.0)))
        except (TypeError, ValueError):
            return None

    def region(self, ticker: str) -> str | None:
        asset_type = self.asset_type(ticker)
        asset = self.get(ticker)
        if asset is None:
            return None
        if asset_type in {"Commodity", "Crypto"}:
            return RESERVE_CURRENCY
        if asset_type == "Fund":
            return str(asset.get("ziel", asset.get("land", RESERVE_CURRENCY)))
        return str(asset.get("land", RESERVE_CURRENCY))

    def quote(self, ticker: str) -> AssetQuote | None:
        asset = self.get(ticker)
        if asset is None:
            return None
        asset_type = self.asset_type(ticker)
        price = float(asset.get("kurs", asset.get("price", 0.0)))
        region = self.region(ticker) or RESERVE_CURRENCY
        return AssetQuote(
            ticker=ticker,
            asset_type=asset_type,
            data=asset,
            price=price,
            change=float(asset.get("aenderung", 0.0)),
            market_cap=float(asset.get("market_cap", asset.get("aum", 0.0))),
            region=region,
            sector=str(asset.get("branche", asset.get("kategorie", asset.get("typ", "")))),
        )

    def quotes(self) -> list[AssetQuote]:
        rows: list[AssetQuote] = []
        for _asset_type, book in self.asset_books():
            for ticker in book:
                quote = self.quote(str(ticker))
                if quote is not None:
                    rows.append(quote)
        return rows

    def history(self, ticker: str, limit: int = 520) -> list[Any]:
        asset = self.get(ticker)
        if asset is None:
            return []
        return list(asset.get("historie", [])[-limit:])


def _book(state: Any, legacy_name: str, snapshot_name: str) -> dict[str, dict[str, Any]]:
    value = getattr(state, legacy_name, None)
    if isinstance(value, dict):
        return value
    value = getattr(state, snapshot_name, None)
    if isinstance(value, dict):
        return value
    return {}
