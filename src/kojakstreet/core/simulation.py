"""Pure daily simulation runtime for the PySide application."""

from __future__ import annotations

from datetime import timedelta
from time import perf_counter
from typing import Any

from kojakstreet.core.accounting import get_net_worth
from kojakstreet.core.bonds import update_dynamic_bond_market
from kojakstreet.core.company_lifecycle import update_company_lifecycle, update_monthly_companies
from kojakstreet.core.events import run_event_phase
from kojakstreet.core.financial_products import (
    roll_expired_financial_products,
    update_financial_products,
)
from kojakstreet.core.label_codes import attach_stable_label_codes
from kojakstreet.core.market_regime import update_market_regime
from kojakstreet.core.monthly_assets import (
    update_crypto_lifecycle,
    update_crypto_production_inputs,
    update_monthly_commodities,
    update_monthly_crypto,
)
from kojakstreet.core.portfolio_risk import (
    update_credit_interest_charges,
    update_future_settlements,
    update_perpetual_liquidations,
    update_spot_derivative_settlements,
)
from kojakstreet.core.performance import record_phase_duration
from kojakstreet.core.production_chains import update_production_chain
from kojakstreet.core.production_signals import emit_production_chain_news

BOND_MARKET_UPDATE_INTERVAL_DAYS = 30
BOND_MARKET_DAILY_REFRESH_LIMIT = 120
ECONOMIC_REPORT_DAY = 15


class DailySimulation:
    """Runs one simulation day without legacy Tkinter or chart side effects."""

    def __init__(
        self,
        daten: Any,
        makro: Any,
        markt: Any,
        anleihen: Any,
        production: Any | None = None,
    ) -> None:
        self.daten = daten
        self.makro = makro
        self.markt = markt
        self.anleihen = anleihen
        self.production = production

    def step_day(self) -> None:
        if hasattr(self.daten, "is_active") and not self.daten.is_active:
            return
        if not getattr(self.daten, "SPIEL_AKTIV", True):
            return
        if hasattr(self.daten, "is_paused") and self.daten.is_paused:
            return
        if self.daten.spiel_pausiert:
            return

        self.daten.simulation_phase_timings = []
        monthly_processed = self._phase("monthly_report", self._run_monthly_company_report_if_due)

        self._phase("events", lambda: run_event_phase(self.daten, self.add_news))

        self._phase("global_macro", self._update_global_macro)
        # Monthly production already books today's inventories and flows.
        if not monthly_processed:
            self._phase("daily_production", self._update_daily_production)
        self._phase("credit_interest", lambda: update_credit_interest_charges(self.daten))
        self._phase("bond_market", self._update_bond_market_if_due)
        self._phase("asset_market", self._update_asset_market)
        self._phase("derivatives", self._update_derivatives)
        self._phase("spot_derivative_settlements", lambda: update_spot_derivative_settlements(self.daten, self.add_news))
        self._phase("future_settlements", lambda: update_future_settlements(self.daten, self.add_news))
        self._phase("derivative_rolls", lambda: roll_expired_financial_products(self.daten))
        self._phase("perpetuals", lambda: update_perpetual_liquidations(self.daten, self.add_news))
        self._phase("bond_portfolio", self._update_bond_portfolio)

        if get_net_worth(self.daten) <= 0:
            if hasattr(self.daten, "is_active"):
                self.daten.is_active = False
                self.daten.is_paused = True
            else:
                self.daten.SPIEL_AKTIV = False
                self.daten.spiel_pausiert = True
            self.add_news(" MARGIN CALL: Your net worth is depleted.", "ROT")
            return

        if not hasattr(self.daten, "handels_tage_zaehler"):
            self.daten.handels_tage_zaehler = 0
        self.daten.handels_tage_zaehler += 1
        zeit_str = self.daten.datum.strftime("%d.%m.%Y")
        self.daten.DEPOT_VERMOEGEN_HISTORIE.append((get_net_worth(self.daten), zeit_str))
        if len(self.daten.DEPOT_VERMOEGEN_HISTORIE) > 520:
            del self.daten.DEPOT_VERMOEGEN_HISTORIE[:-520]

        if self._policy_decision_due():
            self.daten.LETZTER_ZINS_TAG = self.daten.datum
            self._run_policy_decision()

        self._complete_and_advance_day()

    def _phase(self, name: str, callback):
        started = perf_counter()
        result = callback()
        self._record_phase_duration(name, started)
        return result

    def _record_phase_duration(self, name: str, started: float) -> None:
        record_phase_duration(self.daten, name, started)

    def _update_bond_market_if_due(self) -> None:
        today_ordinal = self.daten.datum.toordinal()
        update_dynamic_bond_market(self.daten, max_refresh=BOND_MARKET_DAILY_REFRESH_LIMIT)
        self.daten.last_bond_market_update_ordinal = today_ordinal

    def _update_asset_market(self) -> None:
        if hasattr(self.markt, "update_daily_prices"):
            self.markt.update_daily_prices()
            return
        self.markt.update_markt_kurse(self.daten)

    def _update_derivatives(self) -> None:
        update_financial_products(self.daten, self.daten.datum.strftime("%d.%m.%Y"))

    def _update_global_macro(self) -> None:
        if hasattr(self.makro, "update_global_liquidity"):
            self.makro.update_global_liquidity()
        else:
            self.makro.update_global_liquidity_index(self.daten)
        update_market_regime(self.daten)

    def _update_monthly_macro(self) -> None:
        if hasattr(self.makro, "update_monthly_economy"):
            self.makro.update_monthly_economy(self.add_news)
            return
        self.makro.update_makro_oekonomie(self.add_news, self.daten)
        self.makro.update_sovereign_ratings(self.daten)

    def _run_policy_decision(self) -> None:
        if hasattr(self.makro, "run_policy_decision"):
            self.makro.run_policy_decision(self.add_news)
            return
        self.makro.fuehre_monatlichen_zinsentscheid_durch(self.add_news, self.daten)

    def _update_bond_portfolio(self) -> None:
        if hasattr(self.anleihen, "update_owned_bonds"):
            self.anleihen.update_owned_bonds(self.add_news)
            return
        self.anleihen.update_laufende_anleihen(self.add_news, self.daten)

    def add_news(self, text: str, kategorie: str = "WEISS") -> None:
        if "Gewinn" in text or "Verlust" in text:
            return
        zeit_str = self.daten.datum.strftime("%d.%m.%Y")
        self.daten.NEWS_SPEICHER.insert(0, (zeit_str, text, kategorie))
        if len(self.daten.NEWS_SPEICHER) > 50:
            self.daten.NEWS_SPEICHER.pop()

    def _run_monthly_company_report_if_due(self) -> bool:
        if not self._monthly_economic_report_due():
            return False

        self.daten.LETZTER_REPORT_MONAT = self._report_period_key()
        phase_started = perf_counter()
        self._update_monthly_macro()
        self._record_phase_duration("monthly_macro", phase_started)
        phase_started = perf_counter()
        self._update_monthly_companies()
        self._record_phase_duration("monthly_companies", phase_started)

        phase_started = perf_counter()
        self._update_company_lifecycle()
        self._record_phase_duration("monthly_company_lifecycle", phase_started)

        phase_started = perf_counter()
        global_macro_growth = self._global_macro_growth()
        global_world_rate = self._global_world_rate()
        self._update_monthly_commodities(global_macro_growth)
        self._record_phase_duration("monthly_commodities", phase_started)

        phase_started = perf_counter()
        self._update_monthly_production()
        self._record_phase_duration("monthly_production", phase_started)

        phase_started = perf_counter()
        self._update_monthly_crypto(global_macro_growth, global_world_rate)
        self._record_phase_duration("monthly_crypto", phase_started)

        phase_started = perf_counter()
        self._update_crypto_lifecycle()
        self._record_phase_duration("monthly_crypto_lifecycle", phase_started)

        return True

    def _complete_and_advance_day(self) -> None:
        if hasattr(self.daten, "mark_completed_today") and hasattr(self.daten, "advance_one_day"):
            self.daten.mark_completed_today()
            self.daten.advance_one_day()
            return
        self.daten.last_completed_simulation_date = self.daten.datum
        self.daten.datum += timedelta(days=1)

    def _update_monthly_companies(self) -> None:
        if self.production is not None and hasattr(self.production, "update_companies"):
            self.production.update_companies()
            return
        update_monthly_companies(self.daten)

    def _update_company_lifecycle(self) -> None:
        if self.production is not None and hasattr(self.production, "update_company_lifecycle"):
            self.production.update_company_lifecycle(self.add_news)
            return
        update_company_lifecycle(self.daten, self.add_news)

    def _update_monthly_commodities(self, global_macro_growth: float) -> None:
        if self.production is not None and hasattr(self.production, "update_commodities"):
            self.production.update_commodities(global_macro_growth)
            return
        update_monthly_commodities(self.daten, global_macro_growth)

    def _update_monthly_production(self) -> None:
        if self.production is not None and hasattr(self.production, "update_production_chain"):
            self.production.update_production_chain(self.add_news)
            return
        update_crypto_production_inputs(self.daten)
        update_production_chain(self.daten)
        emit_production_chain_news(self.daten, self.add_news)

    def _update_daily_production(self) -> None:
        if self.production is not None and hasattr(self.production, "update_daily_production_chain"):
            self.production.update_daily_production_chain()
            return
        update_crypto_production_inputs(self.daten)
        update_production_chain(
            self.daten,
            advance_population=False,
            rebalance_company_outputs=False,
        )
        attach_stable_label_codes(self.daten)

    def _update_monthly_crypto(self, global_macro_growth: float, global_world_rate: float) -> None:
        if self.production is not None and hasattr(self.production, "update_crypto"):
            self.production.update_crypto(global_macro_growth, global_world_rate)
            return
        update_monthly_crypto(self.daten, global_macro_growth, global_world_rate)

    def _update_crypto_lifecycle(self) -> None:
        if self.production is not None and hasattr(self.production, "update_crypto_lifecycle"):
            self.production.update_crypto_lifecycle(self.add_news)
            return
        update_crypto_lifecycle(self.daten, self.add_news)

    def _monthly_economic_report_due(self) -> bool:
        if self.daten.datum.day != ECONOMIC_REPORT_DAY:
            return False
        marker = getattr(self.daten, "LETZTER_REPORT_MONAT", -1)
        return not self._report_marker_matches_current_month(marker)

    def _report_marker_matches_current_month(self, marker: object) -> bool:
        current_key = self._report_period_key()
        if marker == current_key:
            return True
        return marker == self.daten.datum.month and self.daten.datum.year <= 1990

    def _report_period_key(self) -> int:
        return self.daten.datum.year * 100 + self.daten.datum.month

    def _policy_decision_due(self) -> bool:
        return self._is_last_day_of_month() and getattr(self.daten, "LETZTER_ZINS_TAG", None) != self.daten.datum

    def _is_last_day_of_month(self) -> bool:
        return (self.daten.datum + timedelta(days=1)).month != self.daten.datum.month

    def _global_macro_growth(self) -> float:
        values = [
            float(data.get("bip_prozent", 0.01))
            for data in self.daten.makro.values()
            if isinstance(data, dict)
        ]
        return sum(values) / len(values) if values else 0.01

    def _global_world_rate(self) -> float:
        values = [
            float(data.get("zins", 0.035))
            for data in self.daten.makro.values()
            if isinstance(data, dict)
        ]
        return sum(values) / len(values) if values else 0.035


