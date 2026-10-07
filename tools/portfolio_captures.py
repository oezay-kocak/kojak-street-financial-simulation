"""Capture current portfolio documentation from one genuinely simulated world.

Run with the source installation. Raw state and metadata stay in ignored .cache;
only six complete-window images are saved to docs/assets.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def main() -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, encode
    from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
    from kojakstreet.ui_qt.app import APP_STYLESHEET, KojakStreetWindow

    root = Path(__file__).resolve().parents[1]
    evidence = root / ".cache/portfolio-closeout/captures"
    evidence.mkdir(parents=True, exist_ok=True)
    assets = root / "docs/assets"
    assets.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyleSheet(APP_STYLESHEET)
    for font in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + font)
    rt = IntegratedRuntime(root, data_dir=evidence / "data",
                           world_config=WorldGenerationConfig(mode=WorldMode.HETEROGENEOUS, seed=1729))
    window = None
    try:
        initial = rt.snapshot()
        counts = {"countries": len(initial.macro), "companies": len(initial.stocks),
                  "sectors": len(rt.daten.BRANCHEN), "resources": len(initial.commodities),
                  "products_services": len(initial.processed_products), "indices": len(initial.indices)}
        rt.trading.trade_spot("STONE", 10, "BUY")
        for _ in range(75):
            rt.advance_day()
        print(json.dumps({"date": rt.snapshot().date.isoformat(), "initial_counts": counts}), flush=True)

        def digest():
            return hashlib.sha256(json.dumps(encode(capture(rt.daten)), sort_keys=True).encode()).hexdigest()

        before = digest()
        window = KojakStreetWindow(rt.snapshot(), rt)
        window.resize(1680, 1050)
        window.show()

        def save(name):
            for _ in range(6):
                app.processEvents()
            window.repaint()
            app.processEvents()
            assert window.grab().save(str(assets / (name + ".png")))

        window.set_active_view("markets")
        markets = window.views["markets"]
        markets._select_ticker("STONE", asset_type="Stock")
        save("markets")
        markets._open_asset_detail(markets.market_table.currentIndex())
        markets.stock_detail_view.detail_tabs.setCurrentWidget(markets.stock_detail_view.overview_tab)
        save("company-detail")
        window.set_active_view("macro")
        macro = window.views["macro"]
        country = max(rt.daten.makro, key=lambda c: len(rt.daten.makro[c]["politics"]["parties"]))
        macro.detail_view.update_region(country, macro.state)
        macro.pages.setCurrentWidget(macro.detail_view)
        macro.detail_view.tabs.setCurrentIndex(0)
        save("country")
        window.resize(1920, 1400)
        macro.detail_view.tabs.setCurrentIndex(4)
        macro.detail_view.society_panel.verticalScrollBar().setValue(0)
        save("society-politics")
        window.resize(1680, 1050)
        window.set_active_view("supply_chain")
        save("supply-chain")
        window.set_active_view("portfolio")
        save("portfolio")
        assert digest() == before, "Documentation capture must not mutate world/player/RNG"
        metadata = {"passed": True, "mode": "heterogeneous", "seed": 1729,
                    "real_daily_steps": 75, "date": rt.snapshot().date.isoformat(),
                    "initial_counts": counts, "country": country,
                    "world_player_rng_unchanged_by_capture": True,
                    "assets": [p.name for p in sorted(assets.glob("*.png"))]}
        (evidence / "result.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(json.dumps(metadata), flush=True)
    finally:
        if window is not None:
            window.close()
        rt.close()


if __name__ == "__main__":
    main()
