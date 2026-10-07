"""Actual heterogeneous scopes and complete-window viewport verification."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
OUT = ROOT / '.cache/politics-implementation/ui-shell-theme-closed'


def main():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, encode
    from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
    from kojakstreet.live_process import game_state_payload
    from kojakstreet.ui_qt.app import APP_STYLESHEET, KojakStreetWindow
    from kojakstreet.visible_state import project_visible_state
    OUT.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    app.setStyleSheet(APP_STYLESHEET)
    for font in ('segoeui.ttf', 'segoeuib.ttf', 'consola.ttf'):
        assert QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font) >= 0
    rt = IntegratedRuntime(ROOT, data_dir=OUT/'data', world_config=WorldGenerationConfig(mode=WorldMode.HETEROGENEOUS, seed=1729))
    window = None
    try:
        def digest():
            return hashlib.sha256(json.dumps(encode(capture(rt.daten)), sort_keys=True).encode()).hexdigest()
        before = digest()
        payloads = []
        for country, m in rt.daten.makro.items():
            state, _, _ = project_visible_state(rt, {'view': 'macro', 'selection': {'region': country, 'area': 'society_politics'}})
            size = len(json.dumps(game_state_payload(state), separators=(',', ':')).encode())
            assert list(state.macro) == [country] and not state.macro_history
            payloads.append({'country': country, 'parties': len(m['politics']['parties']), 'bytes': size})
        assert max(p['bytes'] for p in payloads) < 5000
        window = KojakStreetWindow(rt.snapshot(), rt)
        window.set_active_view('macro')
        macro = window.views['macro']
        country = max(payloads, key=lambda p: p['parties'])['country']
        macro.detail_view.update_region(country, macro.state)
        macro.pages.setCurrentWidget(macro.detail_view)
        macro.detail_view.tabs.setCurrentIndex(4)
        window.show()
        geometry = []
        for name, width, height in [('narrow', 1080, 720), ('default', 1360, 860), ('large', 1920, 1400)]:
            window.resize(width, height)
            macro.detail_view.society_panel.verticalScrollBar().setValue(0)
            window.workspace_scroll.horizontalScrollBar().setValue(0)
            app.processEvents()
            assert window.grab().save(str(OUT/(name+'.png')))
            geometry.append({'name': name, 'width': window.width(), 'height': window.height(),
                             'horizontal_scroll_range': window.workspace_scroll.horizontalScrollBar().maximum()})
            macro.detail_view.society_panel.verticalScrollBar().setValue(macro.detail_view.society_panel.verticalScrollBar().maximum())
            window.workspace_scroll.horizontalScrollBar().setValue(window.workspace_scroll.horizontalScrollBar().maximum())
            app.processEvents()
            assert window.grab().save(str(OUT/(name+'-lower-right.png')))
        assert digest() == before, 'UI navigation/projection mutated world/player/RNG'
        (OUT/'result.json').write_text(json.dumps({'passed': True, 'payloads': payloads,
            'maximum_bytes': max(p['bytes'] for p in payloads), 'max_party_count': max(p['parties'] for p in payloads),
            'geometry': geometry, 'world_player_rng_unchanged': True}, indent=2), encoding='utf-8')
        print(json.dumps({'passed': True, 'maximum_bytes': max(p['bytes'] for p in payloads), 'geometry': geometry}), flush=True)
    finally:
        if window is not None:
            window.close()
        rt.close()


if __name__ == '__main__':
    main()
