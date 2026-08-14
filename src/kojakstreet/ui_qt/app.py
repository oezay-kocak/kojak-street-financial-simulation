"""Application entry point for the next-generation Kojak Street UI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _project_root()

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.financial_products import EXPIRING_DERIVATIVE_CONTRACT_TYPES, derivative_allows_future_trade
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.runtime_ports import RuntimePort, is_refreshable
from kojakstreet.ui_qt.theme import APP_STYLESHEET
from kojakstreet.ui_qt.views.bondmarket_view import BondMarketView
from kojakstreet.ui_qt.views.forex_view import ForexView
from kojakstreet.ui_qt.views.global_macro_view import GlobalMacroView
from kojakstreet.ui_qt.views.macro_view import MacroView
from kojakstreet.ui_qt.views.markets_view import MarketsView
from kojakstreet.ui_qt.views.news_view import NewsView
from kojakstreet.ui_qt.views.portfolio_view import PortfolioView
from kojakstreet.ui_qt.views.supply_chain_view import SupplyChainView
from kojakstreet.ui_qt.views.trade_map_view import TradeMapView
from kojakstreet.ui_qt.widgets.side_nav import SideNav
from kojakstreet.ui_qt.widgets.top_bar import TopBar


def _load_legacy_state() -> GameState:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    import daten

    return snapshot_from_legacy(daten)


class SimulationWorker(QObject):
    finished = Signal(object, int)
    failed = Signal(str)

    def __init__(self, runtime: IntegratedRuntime) -> None:
        super().__init__()
        self.runtime = runtime

    @Slot()
    def run(self) -> None:
        self.advance(1, "full")

    @Slot(int, str)
    def advance(self, steps: int, view_key: str = "full") -> None:
        try:
            if hasattr(self.runtime, "advance_days"):
                state = self.runtime.advance_days(steps, view_key)
            else:
                state = None
                for _ in range(steps):
                    state = self.runtime.step_day()
                if state is None:
                    state = self.runtime.snapshot()
            self.finished.emit(state, steps)
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            self.failed.emit(str(exc))


class KojakStreetWindow(QMainWindow):
    """Main Qt shell backed by a legacy state snapshot."""

    simulation_requested = Signal(int, str)

    VIEW_ORDER = (
        "markets",
        "supply_chain",
        "forex",
        "bondmarket",
        "portfolio",
        "macro",
        "trade_map",
        "global_macro",
        "news",
    )

    def __init__(self, state: GameState, runtime: RuntimePort | None = None) -> None:
        super().__init__()
        self.state = state
        self.runtime = runtime
        self.active_view_key = "markets"
        self.ticks_per_timeout = 1
        self.refresh_every_ticks = 1
        self.pending_ticks = 0
        self.simulation_busy = False
        self.simulation_thread: QThread | None = None
        self.simulation_worker: SimulationWorker | None = None
        self.force_refresh_after_worker = False
        self.queued_simulation_steps = 0
        self.queued_force_refresh = False
        self._last_live_current_version = -1
        self._live_update_pending = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.markets_view = MarketsView(state, self._execute_trade, self._asset_history_provider())
        self.stack = QStackedWidget()
        self.views: dict[str, QWidget] = {"markets": self.markets_view}
        self._loaded_view_keys = {"markets"}

        self.setWindowTitle("Kojak Street Pro")
        self.resize(1360, 860)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)
        self.top_bar = TopBar(state, self.asset_count)
        self.top_bar.run_button.setCheckable(True)
        self.top_bar.run_button.clicked.connect(self.toggle_simulation)
        self.top_bar.step_button.clicked.connect(self.save_game)
        self.top_bar.load_button.clicked.connect(self.load_game)
        root_layout.addWidget(self.top_bar)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.side_nav = SideNav()
        self.side_nav.view_changed.connect(self.set_active_view)
        body.addWidget(self.side_nav, 0)
        for view_key in self.VIEW_ORDER:
            view = self.views.get(view_key)
            if view is None:
                view = self._build_view_placeholder(view_key)
                self.views[view_key] = view
            self.stack.addWidget(view)
        body.addWidget(self.stack, 1)
        root_layout.addLayout(body, 1)

        self.setCentralWidget(root)
        self._update_status("markets")

    @property
    def asset_count(self) -> int:
        return self.markets_view.asset_count

    def _asset_count(self) -> int:
        """Compatibility shim for early tests while the UI is being split."""

        return self.markets_view.proxy_model.rowCount()

    def set_active_view(self, view_key: str) -> None:
        view = self.views.get(view_key)
        if view is None:
            return
        if self.runtime is not None and hasattr(self.runtime, "snapshot_for_view"):
            self.state = self.runtime.snapshot_for_view(view_key)
        view = self._ensure_view_loaded(view_key)
        if view_key != self.active_view_key and is_refreshable(view):
            self._refresh_view_widget(view, throttle_charts=bool(self.runtime and self.runtime.running))
        self.stack.setCurrentWidget(view)
        self.active_view_key = view_key
        self._update_status(view_key)

    def _update_status(self, view_key: str) -> None:
        self.top_bar.date_value.setText(self.state.date.strftime("%d.%m.%Y"))

    def toggle_simulation(self) -> None:
        if self.runtime is None:
            self.top_bar.run_button.setChecked(False)
            return
        running = self.top_bar.run_button.isChecked()
        self.runtime.set_running(running)
        self.top_bar.run_button.setText("Pause" if running else "Run")
        if running:
            self.timer.start(self._timer_interval_ms())
        else:
            self.timer.stop()
            if hasattr(self.runtime, "snapshot_for_view"):
                self.state = self.runtime.snapshot_for_view(self.active_view_key)
                self._refresh_active_view()
        self._update_status(self.active_view_key)

    def step_simulation(self) -> None:
        if self.runtime is None:
            return
        self._request_simulation_steps(1, force_refresh=True)

    def save_game(self) -> None:
        if self.runtime is None:
            return
        self.runtime.save_game()
        self.state = self.runtime.snapshot_for_view(self.active_view_key)
        self._refresh_active_view()

    def load_game(self) -> None:
        if self.runtime is None or not hasattr(self.runtime, "load_game"):
            return
        self.runtime.load_game()
        self.state = self.runtime.snapshot_for_view(self.active_view_key)
        self._refresh_active_view()

    def _execute_trade(self, ticker: str, mode: str, side: str, amount: float, leverage: int) -> None:
        if self.runtime is None:
            return
        try:
            if hasattr(self.runtime, "validate_trade"):
                validation = self.runtime.validate_trade(ticker, mode, side, amount, leverage)
                if not validation.is_valid:
                    return
            if mode == "SPOT":
                self.runtime.trade_spot(ticker, amount, side)
            elif mode == "FUTURE":
                if not self._allows_perpetual_trade(ticker):
                    return
                self.runtime.trade_future(ticker, side, leverage, amount)
            else:
                return
        except ValueError:
            return
        self.state = self.runtime.snapshot_for_view(self.active_view_key)
        self._refresh_active_view()

    def _allows_perpetual_trade(self, ticker: str) -> bool:
        if self.runtime is None:
            return False
        state = self.runtime.state
        if ticker in state.stocks or ticker in state.commodities or ticker in state.cryptos:
            return True
        derivative = state.derivatives.get(ticker)
        return bool(derivative and derivative_allows_future_trade(derivative))

    def _close_future(self, position_id: str) -> None:
        if self.runtime is None:
            return
        try:
            self.runtime.close_future(position_id)
        except ValueError:
            return
        self.state = self.runtime.snapshot_for_view(self.active_view_key)
        self._refresh_active_view()

    def _exchange_currency(self, source_region: str, target_region: str, amount: float) -> None:
        if self.runtime is None:
            return
        try:
            self.runtime.exchange_currency(source_region, target_region, amount)
        except ValueError:
            return
        self.state = self.runtime.snapshot_for_view(self.active_view_key)
        self._refresh_active_view()

    def _on_timer_tick(self) -> None:
        if self.runtime is None:
            return
        self._request_simulation_steps(self.ticks_per_timeout, force_refresh=False)

    def _request_simulation_steps(self, steps: int, *, force_refresh: bool) -> None:
        if self.runtime is None or steps <= 0:
            return
        if self.simulation_busy:
            self.queued_simulation_steps += steps
            self.queued_force_refresh = self.queued_force_refresh or force_refresh
            return

        self._ensure_simulation_worker()
        self.simulation_busy = True
        self.force_refresh_after_worker = force_refresh
        self.top_bar.step_button.setEnabled(False)
        self.top_bar.load_button.setEnabled(False)
        worker_view_key = self.active_view_key if force_refresh else "status"
        self.simulation_requested.emit(steps, worker_view_key)

    def _ensure_simulation_worker(self) -> None:
        if self.runtime is None or self.simulation_thread is not None:
            return
        self.simulation_thread = QThread(self)
        self.simulation_worker = SimulationWorker(self.runtime)
        self.simulation_worker.moveToThread(self.simulation_thread)
        self.simulation_requested.connect(self.simulation_worker.advance)
        self.simulation_worker.finished.connect(self._on_simulation_finished)
        self.simulation_worker.failed.connect(self._on_simulation_failed)
        self.simulation_thread.finished.connect(self.simulation_worker.deleteLater)
        self.simulation_thread.start()

    @Slot(object, int)
    def _on_simulation_finished(self, state: GameState, steps: int) -> None:
        self.pending_ticks += steps
        if self.force_refresh_after_worker:
            if self.runtime is not None and hasattr(self.runtime, "snapshot_for_view"):
                self.state = self.runtime.snapshot_for_view(self.active_view_key)
            else:
                self.state = state
            self._refresh_active_view()
            self.pending_ticks = 0
        else:
            self.top_bar.update_status(state)
            self._schedule_live_market_updates()
        self.force_refresh_after_worker = False
        self.simulation_busy = False
        self.top_bar.step_button.setEnabled(True)
        self.top_bar.load_button.setEnabled(True)
        if not self._request_queued_simulation_steps() and not self.top_bar.run_button.isChecked():
            self._shutdown_simulation_worker()

    @Slot(str)
    def _on_simulation_failed(self, message: str) -> None:
        self.force_refresh_after_worker = False
        self.simulation_busy = False
        self.top_bar.step_button.setEnabled(True)
        self.top_bar.load_button.setEnabled(True)
        self.queued_simulation_steps = 0
        self.queued_force_refresh = False

    @Slot()
    def _clear_simulation_worker(self) -> None:
        if self.simulation_thread is not None:
            self.simulation_thread.deleteLater()
        self.simulation_thread = None
        self.simulation_worker = None

    def _request_queued_simulation_steps(self) -> bool:
        if self.queued_simulation_steps <= 0:
            return False
        queued_steps = self.queued_simulation_steps
        force_refresh = self.queued_force_refresh
        self.queued_simulation_steps = 0
        self.queued_force_refresh = False
        self._request_simulation_steps(queued_steps, force_refresh=force_refresh)
        return True

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._shutdown_simulation_worker()
        super().closeEvent(event)

    def _shutdown_simulation_worker(self) -> None:
        if self.simulation_thread is None:
            return
        self.simulation_thread.quit()
        self.simulation_thread.wait(1500)
        self._clear_simulation_worker()

    def _timer_interval_ms(self) -> int:
        return 2000

    def _apply_live_market_updates(self) -> None:
        self._live_update_pending = False
        if self.runtime is None:
            return
        if hasattr(self.runtime, "current_version"):
            current_version = self.runtime.current_version()
            if current_version == self._last_live_current_version:
                return
            self._last_live_current_version = current_version
        if hasattr(self.runtime, "ticker_tape_quotes"):
            self.top_bar.update_ticker_quotes(self.runtime.ticker_tape_quotes())
        active_view = self.views.get(self.active_view_key)
        changed_tables = None
        if hasattr(self.runtime, "current_delta"):
            changed_tables = self.runtime.current_delta().tables
        if (
            self.active_view_key == "markets"
            and isinstance(active_view, MarketsView)
            and hasattr(self.runtime, "asset_quote_rows")
            and _current_table_changed(changed_tables, "asset_current")
        ):
            active_view.apply_live_quotes(self.runtime.asset_quote_rows())
        elif (
            self.active_view_key == "supply_chain"
            and isinstance(active_view, SupplyChainView)
            and hasattr(self.runtime, "product_current_rows")
            and _current_table_changed(changed_tables, "product_current")
        ):
            active_view.apply_live_current_rows(self.runtime.product_current_rows())
        elif (
            self.active_view_key == "macro"
            and isinstance(active_view, MacroView)
            and hasattr(self.runtime, "country_current_rows")
            and _current_table_changed(changed_tables, "country_current")
        ):
            active_view.apply_live_current_rows(self.runtime.country_current_rows())
        elif (
            self.active_view_key == "forex"
            and isinstance(active_view, ForexView)
            and hasattr(self.runtime, "forex_current_rows")
            and _current_table_changed(changed_tables, "forex_current")
        ):
            active_view.apply_live_current_rows(self.runtime.forex_current_rows())
        elif (
            self.active_view_key == "bondmarket"
            and isinstance(active_view, BondMarketView)
            and hasattr(self.runtime, "bond_current_rows")
            and _current_table_changed(changed_tables, "bond_current")
        ):
            active_view.apply_live_current_rows(self.runtime.bond_current_rows())
        elif (
            self.active_view_key == "portfolio"
            and isinstance(active_view, PortfolioView)
            and hasattr(self.runtime, "portfolio_current_rows")
            and _current_table_changed(changed_tables, "portfolio_current")
        ):
            active_view.apply_live_current_rows(self.runtime.portfolio_current_rows())
        elif (
            self.active_view_key == "news"
            and isinstance(active_view, NewsView)
            and hasattr(self.runtime, "news_current_rows")
            and _current_table_changed(changed_tables, "news_current")
        ):
            active_view.apply_live_current_rows(self.runtime.news_current_rows())

    def _schedule_live_market_updates(self) -> None:
        if self._live_update_pending:
            return
        self._live_update_pending = True
        QTimer.singleShot(0, self._apply_live_market_updates)

    def _refresh_active_view(self) -> None:
        active_view = self._ensure_view_loaded(self.active_view_key)
        throttle_charts = bool(self.runtime and self.runtime.running)
        if self.active_view_key == "markets" and isinstance(active_view, MarketsView):
            active_view.refresh(self.state, throttle_charts=throttle_charts)
        elif is_refreshable(active_view):
            self._refresh_view_widget(active_view, throttle_charts=throttle_charts)
        else:
            self._replace_view(self.active_view_key)
        self.top_bar.update_state(self.state, self.asset_count)
        if self.runtime is not None and hasattr(self.runtime, "current_version"):
            self._last_live_current_version = self.runtime.current_version()
        self._update_status(self.active_view_key)

    def _refresh_view_widget(self, view: QWidget, *, throttle_charts: bool) -> None:
        try:
            view.refresh(self.state, throttle_charts=throttle_charts)  # type: ignore[attr-defined]
        except TypeError:
            view.refresh(self.state)  # type: ignore[attr-defined]

    def _replace_view(self, view_key: str) -> None:
        old_view = self.views.get(view_key)
        if old_view is None:
            return
        index = self.stack.indexOf(old_view)
        new_view = self._build_view(view_key)
        self.views[view_key] = new_view
        if view_key == "markets":
            self.markets_view = new_view  # type: ignore[assignment]
        if index >= 0:
            self.stack.removeWidget(old_view)
            old_view.deleteLater()
            self.stack.insertWidget(index, new_view)
        else:
            self.stack.addWidget(new_view)
        if view_key == self.active_view_key:
            self.stack.setCurrentWidget(new_view)

    def _refresh_all_views(self) -> None:
        for view_key in list(self._loaded_view_keys):
            view = self.views[view_key]
            if is_refreshable(view):
                view.refresh(self.state)  # type: ignore[attr-defined]
        self.top_bar.update_state(self.state, self.asset_count)
        self._update_status(self.active_view_key)

    def _build_view_placeholder(self, view_key: str) -> QWidget:
        placeholder = QWidget()
        placeholder.setObjectName(f"{view_key}_placeholder")
        return placeholder

    def _ensure_view_loaded(self, view_key: str) -> QWidget:
        if view_key in self._loaded_view_keys:
            return self.views[view_key]
        current = self.views.get(view_key)
        index = self.stack.indexOf(current) if current is not None else -1
        view = self._build_view(view_key)
        self.views[view_key] = view
        self._loaded_view_keys.add(view_key)
        if view_key == "markets":
            self.markets_view = view  # type: ignore[assignment]
        if index >= 0:
            old_view = self.stack.widget(index)
            self.stack.removeWidget(old_view)
            old_view.deleteLater()
            self.stack.insertWidget(index, view)
        else:
            self.stack.addWidget(view)
        return view

    def _build_view(self, view_key: str) -> QWidget:
        if view_key == "markets":
            return MarketsView(self.state, self._execute_trade, self._asset_history_provider())
        if view_key == "supply_chain":
            return SupplyChainView(
                self.state,
                self._product_history_provider(),
                self._product_current_provider(),
                self._company_current_provider(),
                self._company_output_provider(),
            )
        if view_key == "portfolio":
            return PortfolioView(self.state, self._execute_trade, self._close_future, self._exchange_currency)
        if view_key == "forex":
            return ForexView(self.state, self._exchange_currency, self._forex_history_provider(), self._forex_current_provider())
        if view_key == "bondmarket":
            return BondMarketView(self.state, self._bond_history_provider(), self._bond_current_provider())
        if view_key == "macro":
            return MacroView(self.state, self._country_history_provider(), self._country_current_provider())
        if view_key == "global_macro":
            return GlobalMacroView(self.state)
        if view_key == "trade_map":
            return TradeMapView(self.state, self._country_trade_current_provider())
        if view_key == "news":
            return NewsView(self.state)
        return MarketsView(self.state, history_provider=self._asset_history_provider())

    def _asset_history_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "asset_history"):
            return None
        return self.runtime.asset_history

    def _bond_history_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "bond_history"):
            return None
        return self.runtime.bond_history

    def _bond_current_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "bond_current_rows"):
            return None
        return self.runtime.bond_current_rows

    def _product_history_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "product_history"):
            return None
        return self.runtime.product_history

    def _product_current_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "product_current_rows"):
            return None
        return self.runtime.product_current_rows

    def _company_current_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "company_current_rows"):
            return None
        return self.runtime.company_current_rows

    def _company_output_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "company_output_current_rows"):
            return None
        return self.runtime.company_output_current_rows

    def _country_trade_current_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "country_trade_current_rows"):
            return None
        return self.runtime.country_trade_current_rows

    def _forex_history_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "forex_history"):
            return None
        return self.runtime.forex_history

    def _forex_current_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "forex_current_rows"):
            return None
        return self.runtime.forex_current_rows

    def _country_history_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "country_history"):
            return None
        return self.runtime.country_history

    def _country_current_provider(self):
        if self.runtime is None or not hasattr(self.runtime, "country_current_rows"):
            return None
        return self.runtime.country_current_rows


def _current_table_changed(changed_tables: frozenset[str] | set[str] | None, table: str) -> bool:
    return changed_tables is None or table in changed_tables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the Kojak Street Pro PySide6 shell.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Create the application shell and exit without entering the Qt event loop.",
    )
    args = parser.parse_args(argv)

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    runtime = IntegratedRuntime(PROJECT_ROOT)
    window = KojakStreetWindow(runtime.snapshot_for_view("markets"), runtime)

    if args.smoke_test:
        return 0

    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
