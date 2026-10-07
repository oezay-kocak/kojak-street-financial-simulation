"""The production UI worker retains only the selected Society & Politics scope."""
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.politics import rebuild_calendar
from kojakstreet.live_process import LiveSimulationProcess
from kojakstreet.ui_qt.app import KojakStreetWindow


def test_process_society_scope_current_election_country_switch_and_hidden_tab(tmp_path):
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    bootstrap = IntegratedRuntime(root, data_dir=tmp_path, seed=1729)
    bootstrap.daten.makro['Ameron']['politics']['next_election'] = '1990-01-02'
    rebuild_calendar(bootstrap.state)
    process = LiveSimulationProcess.from_runtime(bootstrap, timeout_seconds=90)
    window = KojakStreetWindow(process.state, process)
    try:
        window.set_active_view('macro')
        macro = window.views['macro']
        macro.detail_view.update_region('Ameron', macro.state)
        macro.pages.setCurrentWidget(macro.detail_view)
        macro.detail_view.tabs.setCurrentIndex(4)
        app.processEvents()
        panel = macro.detail_view.society_panel
        identity = (id(panel), id(panel.workforce_pie), id(panel.political_pie))
        assert list(process.state.macro) == ['Ameron']
        assert len(panel.workforce_pie.slices) == 3
        assert not panel.political_pie.slices
        window._request_simulation_steps(16, force_refresh=False)
        deadline = time.perf_counter()+90
        while (window.simulation_busy or window._live_update_pending) and time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(.002)
        assert not window.simulation_busy and not window._live_update_pending
        app.processEvents()
        assert '1990-01-02' in panel.political_note.text()
        assert len(panel.political_pie.slices) == 4
        assert panel.values['Population Growth · annualized'].text() != 'Not yet observed'
        macro._show_main_page()
        assert all('society_politics' not in m for m in process.state.macro.values())
        macro.detail_view.update_region('Ardonia', macro.state)
        macro.pages.setCurrentWidget(macro.detail_view)
        app.processEvents()
        assert list(process.state.macro) == ['Ardonia']
        assert panel.region == 'Ardonia'
        assert not panel.political_pie.slices
        assert identity == (id(panel), id(panel.workforce_pie), id(panel.political_pie))
        updates = panel.update_count
        macro.detail_view.tabs.setCurrentIndex(0)
        app.processEvents()
        assert panel.update_count == updates
        assert 'society_politics' not in process.state.macro['Ardonia']
    finally:
        window.close()
        process.close()
