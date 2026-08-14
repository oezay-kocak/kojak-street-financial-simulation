"""Runtime bridge to the integrated PySide simulation core."""

import gc
import importlib
import sys
from pathlib import Path

from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.asset_market_engine import AssetMarketEngine
from kojakstreet.core.bond_portfolio_engine import BondPortfolioEngine
from kojakstreet.core.bonds import ensure_dynamic_bond_market
from kojakstreet.core.commodities import ensure_commodity_fundamentals
from kojakstreet.core.companies import ensure_company_universe
from kojakstreet.core.cryptos import ensure_crypto_fundamentals
from kojakstreet.core.data_store import EconomicDataStore
from kojakstreet.core.economy_repository import EconomyRepository
from kojakstreet.core.expectations import ensure_macro_expectations
from kojakstreet.core.fiscal import ensure_country_financials
from kojakstreet.core.fundamentals import ensure_stock_fundamentals
from kojakstreet.core.global_macro import ensure_global_macro
from kojakstreet.core.label_codes import attach_stable_label_codes
from kojakstreet.core.macro_engine import MacroEngine
from kojakstreet.core.market_regime import update_market_regime
from kojakstreet.core.market_data_service import MarketDataService
from kojakstreet.core.production_chains import (
    assign_company_specializations,
    ensure_country_economies,
    ensure_population,
    ensure_processed_products,
    update_production_chain,
)
from kojakstreet.core.production_engine import ProductionEngine
from kojakstreet.core.psychology import ensure_asset_psychology, ensure_market_psychology
from kojakstreet.core.randomness import set_simulation_seed
from kojakstreet.core.ratings import DEFAULT_RATING, RATINGS, normalize_rating
from kojakstreet.core.runtime_context import RuntimeContext, RuntimeServices, SimulationDelta
from kojakstreet.core.simulation import DailySimulation
from kojakstreet.core.simulation_state import SimulationState
from kojakstreet.core.state import GameState
from kojakstreet.core.trading_service import TradingService


class IntegratedRuntime:
    """Adapter that lets the Qt app drive the integrated simulation."""

    def __init__(self, project_root: Path) -> None:
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        import daten
        daten = importlib.reload(daten)
        self.daten = daten
        self.state = SimulationState.from_legacy(daten)
        self.market = AssetMarketEngine(self.state)
        self.macro = MacroEngine(self.state)
        self.bond_portfolio = BondPortfolioEngine(self.state)
        self.production = ProductionEngine(self.state)
        self.simulation = DailySimulation(
            self.state,
            self.macro,
            self.market,
            self.bond_portfolio,
            self.production,
        )
        self._mark_pyside_runtime()
        ensure_country_financials(self.state)
        ensure_macro_expectations(self.state)
        self._ensure_market_fundamentals()
        ensure_global_macro(self.state)
        attach_stable_label_codes(self.state)
        update_market_regime(self.state)
        ensure_dynamic_bond_market(self.state)
        self.data_store = EconomicDataStore(
            project_root / ".cache" / "kojakstreet.duckdb",
            flush_interval_days=120,
            auto_flush=False,
        )
        self.economy = EconomyRepository(self.data_store)
        self.trading = TradingService(self.state)
        self.data_store.record_day(self.state, current_scope="full")
        self._ticker_tape_cache_version = -1
        self._ticker_tape_cache: list[dict[str, float | str]] = []
        self.context = RuntimeContext(
            self.daten,
            self.simulation,
            self.data_store,
            self.economy,
            RuntimeServices(
                market=self.market,
                trading=self.trading,
                macro=self.macro,
                bond_portfolio=self.bond_portfolio,
                production=self.production,
            ),
            self.state,
        )
        self.running = False

    def snapshot(self) -> GameState:
        return snapshot_from_legacy(self.state)

    def snapshot_for_view(self, view_key: str) -> GameState:
        return snapshot_from_legacy(self.state, profile=view_key)

    def close(self) -> None:
        self.data_store.close()

    def asset_history(self, asset_type: str, ticker: str, limit: int = 520) -> list[tuple[float, str, str]]:
        assets = {
            "Stock": getattr(self.daten, "aktien", {}),
            "Commodity": getattr(self.daten, "rohstoffe", {}),
            "Crypto": getattr(self.daten, "kryptos", {}),
            "Fund": getattr(self.daten, "fonds", {}),
            "Index": getattr(self.daten, "indizes", {}),
            "Derivative": getattr(self.daten, "derivatives", {}),
        }.get(asset_type, {})
        return list(assets.get(ticker, {}).get("historie", [])[-limit:])

    def bond_history(self, symbol: str, limit: int = 520) -> list[tuple[float, str, str]]:
        history = self.data_store.bond_history(symbol, limit)
        if history:
            return history
        for bond in getattr(self.daten, "bond_market", []):
            if str(bond.get("symbol", "")) == symbol:
                return list(bond.get("historie", [])[-limit:])
        return []

    def product_history(self, code: str, metric: str, limit: int = 520) -> list[float]:
        column = {
            "produced": "produced",
            "demanded": "demanded",
            "inventories": "inventories",
            "shortage": "shortage",
            "pressure": "pressure",
            "price": "price",
        }.get(metric, metric)
        return self.data_store.session_series("product_daily", "code", code, column, limit)

    def forex_history(self, pair: str, limit: int = 520) -> list[float]:
        history = self.data_store.session_series("forex_daily", "pair", pair, "rate", limit)
        if history:
            return history
        values = []
        for entry in getattr(self.daten, "FOREX_PAARE_HISTORIE", {}).get(pair, [])[-limit:]:
            try:
                values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
            except (TypeError, ValueError):
                continue
        return values

    def country_history(self, region: str, metric: str, limit: int = 520) -> list[float]:
        macro = getattr(self.daten, "makro", {}).get(region, {})
        key = {
            "inflation": f"{region}_INF",
            "growth": f"{region}_BIP",
            "gdp": f"{region}_BIP",
            "unemployment": f"{region}_ALO",
            "rate": f"{region}_ZINS",
            "trade_balance": "trade_balance_history",
            "import_dependency": "import_dependency_history",
            "export_strength": "export_strength_history",
        }.get(metric, metric)
        source = macro.get(key, []) if key.endswith("_history") else getattr(self.daten, "MAKRO_HISTORIE", {}).get(key, [])
        values = []
        for entry in source[-limit:]:
            try:
                values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
            except (TypeError, ValueError):
                continue
        if values:
            return values
        return []

    def asset_quote_rows(self) -> list[dict[str, object]]:
        rows = self.data_store.asset_quote_rows()
        if rows:
            return rows
        return [
            {
                "ticker": quote.ticker,
                "asset_type": quote.asset_type,
                "price": quote.price,
                "change": quote.change,
                "market_cap": quote.market_cap,
                "region": quote.region,
            }
            for quote in MarketDataService(self.daten).quotes()
        ]

    def product_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.product_current_rows()

    def country_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.country_current_rows()

    def forex_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.forex_current_rows()

    def bond_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.bond_current_rows()

    def company_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.company_current_rows()

    def company_output_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.company_output_current_rows()

    def country_trade_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.country_trade_current_rows()

    def fund_allocation_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.fund_allocation_current_rows()

    def event_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.event_current_rows()

    def news_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.news_current_rows()

    def phase_metric_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.phase_metric_current_rows()

    def portfolio_current_rows(self) -> list[dict[str, object]]:
        return self.data_store.portfolio_current_rows()

    def architecture_health(self) -> dict[str, int | bool]:
        return self.data_store.architecture_health()

    def economy_repository(self) -> EconomyRepository:
        return self.economy

    def current_version(self) -> int:
        return self.data_store.current_version()

    def current_delta(self) -> SimulationDelta:
        return self.data_store.current_delta()

    def performance_snapshot(self) -> dict[str, object]:
        rows = self.phase_metric_current_rows()
        phases = {str(row["phase"]): float(row["duration_ms"]) for row in rows}
        return {
            "current_version": self.current_version(),
            "date": self.daten.datum.strftime("%d.%m.%Y"),
            "phases": phases,
            "total_phase_ms": sum(phases.values()),
            "slowest_phase": max(phases, key=phases.get) if phases else "",
        }

    def ticker_tape_quotes(self) -> list[dict[str, float | str]]:
        current_version = self.data_store.current_version()
        if self._ticker_tape_cache_version == current_version:
            return self._ticker_tape_cache
        quotes = self.asset_quote_rows()
        preferred_types = {"Commodity": 2, "Crypto": 2, "Stock": 4, "Index": 1000}
        items: list[dict[str, float | str]] = []
        for asset_type, limit in preferred_types.items():
            ranked = sorted(
                (quote for quote in quotes if quote["asset_type"] == asset_type),
                key=lambda quote: float(quote["change"]),
                reverse=True,
            )[:limit]
            items.extend(
                {
                    "ticker": str(quote["ticker"]),
                    "price": float(quote["price"]),
                    "change": float(quote["change"]),
                }
                for quote in ranked
            )
        self._ticker_tape_cache_version = current_version
        self._ticker_tape_cache = items
        return items

    def set_running(self, running: bool) -> None:
        self.running = running
        self.daten.spiel_pausiert = not running

    def set_seed(self, seed: int) -> None:
        set_simulation_seed(self.state, seed)

    def step_day(self) -> GameState:
        self.advance_day()
        return self.snapshot()

    def advance_day(self) -> None:
        previous_running = self.running
        self.daten.spiel_pausiert = False
        gc_was_enabled = gc.isenabled()
        if gc_was_enabled:
            gc.disable()
        try:
            self.simulation.step_day()
            self.data_store.record_day(self.state)
        finally:
            if gc_was_enabled:
                gc.enable()
        if previous_running:
            self.daten.spiel_pausiert = False
        self.running = previous_running

    def advance_days(self, steps: int, view_key: str = "full") -> GameState:
        for _ in range(max(0, steps)):
            self.advance_day()
        return self.snapshot_for_view(view_key) if view_key != "full" else self.snapshot()

    def save_game(self) -> GameState:
        import speicher

        self.data_store.record_day(self.state, current_scope="full")
        self.data_store.flush()
        speicher.spiel_speichern()
        return self.snapshot()

    def load_game(self) -> GameState:
        import speicher

        speicher.spiel_laden()
        self.state.sync_from_legacy()
        self._ensure_market_fundamentals()
        ensure_global_macro(self.state)
        attach_stable_label_codes(self.state)
        update_market_regime(self.state)
        ensure_dynamic_bond_market(self.state)
        self.data_store.record_day(self.state, current_scope="full")
        return self.snapshot()

    def trade_spot(self, ticker: str, quantity: float, side: str) -> GameState:
        self.trading.trade_spot(ticker, quantity, side)
        return self.snapshot()

    def validate_trade(self, ticker: str, mode: str, side: str, amount: float, leverage: int = 1):
        return self.trading.validate_trade(ticker, mode, side, amount, leverage)

    def trade_future(self, ticker: str, direction: str, leverage: int, margin: float) -> GameState:
        self.trading.open_future(ticker, direction, leverage, margin)
        return self.snapshot()

    def close_future(self, position_id: str) -> GameState:
        self.trading.close_future(position_id)
        return self.snapshot()

    def exchange_currency(self, source_region: str, target_region: str, amount: float) -> GameState:
        self.trading.exchange_currency(source_region, target_region, amount)
        return self.snapshot()

    def _mark_pyside_runtime(self) -> None:
        """Mark this process as running through the integrated PySide runtime."""

        self.daten.PYSIDE_RUNTIME = True
        self.daten.CHART_REFFS = {}

    def _ensure_market_fundamentals(self) -> None:
        ensure_company_universe(self.state)
        ensure_processed_products(self.state)
        ensure_population(self.state)
        ensure_country_economies(self.state)
        assign_company_specializations(self.state)
        for asset in self.state.aktien.values():
            ensure_stock_fundamentals(asset)
            ensure_asset_psychology(asset)
            asset["rating"] = DEFAULT_RATING if asset.get("rating") == "BB" else normalize_rating(asset.get("rating"))
        self.state.RATINGS = RATINGS
        for country in self.state.makro.values():
            country["rating"] = normalize_rating(country.get("rating", DEFAULT_RATING))
        for asset in self.state.rohstoffe.values():
            ensure_commodity_fundamentals(asset)
            ensure_asset_psychology(asset)
        for asset in self.state.kryptos.values():
            ensure_crypto_fundamentals(asset)
            ensure_asset_psychology(asset)
        ensure_market_psychology(self.state)
        update_production_chain(self.state, advance_population=False)
        attach_stable_label_codes(self.state)
        update_market_regime(self.state)
        self.market.warm_runtime_indexes()


LegacyRuntime = IntegratedRuntime
