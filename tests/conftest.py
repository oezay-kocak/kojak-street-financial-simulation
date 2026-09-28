"""Keep test runtimes and Qt windows isolated from user data and displays."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app._test_windows = []
    yield app
    app.processEvents()


@pytest.fixture(autouse=True)
def isolated_runtime_storage(tmp_path, monkeypatch, qt_application):
    monkeypatch.setenv("KOJAKSTREET_DATA_DIR", str(tmp_path / "runtime"))
    yield
    # Keep Python wrappers alive for the QApplication session. Manually deleting
    # Qt-owned graphics/popups mid-session can double-finalize them in PySide.
    for widget in qt_application.topLevelWidgets():
        if widget.parent() is None:
            widget.close()
            qt_application._test_windows.append(widget)
    qt_application.processEvents()
