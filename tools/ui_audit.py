"""Reproducible offscreen screenshots; never opens the desktop GUI."""
from __future__ import annotations

import argparse
import json
import os
import random
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
from kojakstreet.ui_qt.app import KojakStreetWindow
from kojakstreet.ui_qt.new_simulation import GenerationProgressDialog, NewSimulationDialog
from kojakstreet.ui_qt.theme import APP_STYLESHEET
from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", default="1366x768,1600x900,1920x1080")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    # Windows offscreen plugin does not discover system fonts automatically.
    for name in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf", "seguisym.ttf"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    app.setStyleSheet(APP_STYLESHEET)
    random.seed(1729)
    np.random.seed(1729)
    results = []
    with tempfile.TemporaryDirectory(prefix="kojak-ui-") as directory:
        chooser = NewSimulationDialog()
        chooser.resize(720, 420)
        chooser.show()
        app.processEvents()
        chooser_path = args.output / "new-simulation.png"
        chooser.grab().save(str(chooser_path))
        results.append({"view": "new-simulation", "actual": [chooser.width(), chooser.height()], "file": chooser_path.name})
        chooser.close()
        generation = GenerationProgressDialog(
            WorldGenerationConfig(mode=WorldMode.ESTABLISHED, seed=1729, prehistory_years=50).normalized(),
            Path.cwd(), Path(directory),
        )
        generation.resize(720, 360)
        generation.show()
        app.processEvents()
        generation_path = args.output / "established-world-progress.png"
        generation.grab().save(str(generation_path))
        results.append({"view": "established-world-progress", "actual": [generation.width(), generation.height()], "file": generation_path.name})
        generation.close()
        runtime = IntegratedRuntime(Path.cwd(), data_dir=Path(directory))
        runtime.advance_days(20)
        runtime.trade_spot(next(iter(runtime.daten.aktien)), 3., "BUY")
        runtime.trade_future("XAU", "LONG", 2, 100.)
        window = KojakStreetWindow(runtime.snapshot_for_view("markets"), runtime)
        try:
            for size in args.sizes.split(","):
                width, height = map(int, size.split("x"))
                for key in window.VIEW_ORDER:
                    window.set_active_view(key)
                    window.resize(width, height)
                    window.show()
                    app.processEvents()
                    window.workspace_scroll.fit_page()
                    app.processEvents()
                    path = args.output / f"{key}-{size}.png"
                    window.grab().save(str(path))
                    results.append({"view": key, "requested": [width, height], "actual": [window.width(), window.height()], "minimum": [window.minimumSizeHint().width(), window.minimumSizeHint().height()], "dpr": window.devicePixelRatioF(), "file": path.name})
            for key, callback in [("bondmarket", "_open_bond_detail"), ("macro", "_open_country_detail")]:
                window.set_active_view(key)
                getattr(window.views[key], callback)(0)
                window.workspace_scroll.fit_page()
                window.resize(1366, 768)
                app.processEvents()
                path = args.output / f"detail-{key}.png"
                window.grab().save(str(path))
                results.append({"view": f"detail-{key}", "file": path.name})
            macro = window.views["macro"]
            macro.detail_view.overview_panel._set_range(0)
            app.processEvents()
            path = args.output / "detail-macro-all.png"
            window.grab().save(str(path))
            results.append({"view": "detail-macro-all", "file": path.name})
            window.set_active_view("global_macro")
            global_view = window.views["global_macro"]
            global_view._open_metric_detail(0)
            global_view.detail_view.set_range(0)
            app.processEvents()
            path = args.output / "detail-global-macro-all.png"
            window.grab().save(str(path))
            results.append({"view": "detail-global-macro-all", "file": path.name})
            window.set_active_view("supply_chain")
            supply = window.views["supply_chain"]
            from PySide6.QtWidgets import QTableView
            table = supply.findChild(QTableView)
            supply._open_row_detail(table.model().index(0, 0))
            window.workspace_scroll.fit_page()
            app.processEvents()
            path = args.output / "detail-supply_chain.png"
            window.grab().save(str(path))
            results.append({"view": "detail-supply_chain", "file": path.name})
            state = runtime.snapshot()
            for kind, book in [("stock", state.stocks), ("commodity", state.commodities), ("crypto", state.cryptos), ("fund", state.funds), ("index", state.indices), ("derivative", state.derivatives), ("fx-forward", {k:v for k,v in state.derivatives.items() if v.get("instrument_type") == "FX Forward"}), ("cds", {k:v for k,v in state.derivatives.items() if v.get("instrument_type") == "Credit Default Swap"})]:
                ticker = next(iter(book))
                host = QWidget()
                host_layout = QVBoxLayout(host)
                detail = StockDetailView(state=state)
                host_layout.addWidget(detail)
                detail.update_asset(ticker, book[ticker], {"stock": "Stock", "commodity": "Commodity", "crypto": "Crypto", "derivative": "Derivative", "fund": "Fund", "index": "Index", "fx-forward": "Derivative", "cds": "Derivative"}[kind], state)
                host.resize(1280, 720)
                host.show()
                app.processEvents()
                path = args.output / f"detail-{kind}.png"
                host.grab().save(str(path))
                results.append({"view": f"detail-{kind}", "actual": [host.width(), host.height()], "file": path.name})
                host.close()
        finally:
            window.close()
            runtime.close()
    (args.output / "manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
