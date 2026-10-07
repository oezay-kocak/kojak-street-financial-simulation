"""Queued quote updates commit the latest line once with its matching dates."""
from kojakstreet.ui_qt.widgets.asset_chart_panel import AssetChartPanel


def test_live_line_coalesces_queued_quotes_without_losing_latest_history(qt_application, monkeypatch):
    panel = AssetChartPanel()
    panel.update_asset("X", "Stock", {"kurs": 2.0, "historie": [(1.0, "01.01.1990", ""), (2.0, "02.01.1990", "")]})
    commits = []
    monkeypatch.setattr(panel, "_redraw_live_line", lambda points: commits.append((points, list(panel._chart_history))))
    first = {"kurs": 3.0, "historie": [(1.0, "01.01.1990", ""), (3.0, "03.01.1990", "")]}
    latest = {"kurs": 4.0, "historie": [(1.0, "01.01.1990", ""), (4.0, "04.01.1990", "")]}
    panel.update_live_quote(first)
    panel.update_live_quote(latest)
    assert commits == []
    assert panel.current_price == 4.0
    qt_application.processEvents()
    assert commits == [([1.0, 4.0], latest["historie"])]
    assert panel._pending_live_points is None
    qt_application.processEvents()
    assert len(commits) == 1
