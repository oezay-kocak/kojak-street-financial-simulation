"""Qt theme tokens for the Kojak Street Pro interface."""

APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #07090d;
    color: #e5eef8;
    font-family: "Segoe UI";
    font-size: 11pt;
}

QFrame#TopBar, QFrame#SideNav {
    background: #0d1118;
    border: 1px solid #263347;
}

QFrame#Panel {
    background: transparent;
    border: 1px solid #263347;
}

QFrame#PanelInner {
    background: transparent;
    border: 1px solid #263347;
}

QFrame#StatusBar, QFrame#EmptyState {
    background: #0d1118;
    border: 1px solid #263347;
}

QFrame#KpiCard {
    background: transparent;
    border: 1px solid #172033;
}

QFrame#ControlCard {
    background: transparent;
    border: 1px solid #172033;
}

QFrame#TickerTape {
    background: #0a0f16;
    border: 1px solid #263347;
}

QFrame#ViewHeader {
    background: transparent;
    border: 0;
}

QLabel#BrandTitle {
    background: transparent;
    color: #22d3ee;
    font-family: "Cascadia Mono";
    font-size: 24px;
    font-weight: 700;
}

QLabel#SectionTitle {
    background: transparent;
    color: #e5eef8;
    font-size: 17px;
    font-weight: 700;
}

QLabel#Muted {
    background: transparent;
    color: #8ea3b8;
    font-size: 10px;
    font-weight: 600;
}

QLabel#KpiValue {
    background: transparent;
    color: #e5eef8;
    font-family: "Cascadia Mono";
    font-size: 18px;
    font-weight: 700;
}

QLabel#DetailValue {
    background: transparent;
    color: #e5eef8;
    font-family: "Cascadia Mono";
    font-size: 15px;
    font-weight: 700;
}

QLabel#TickerTapeText {
    background: transparent;
    color: #c9d7e6;
    font-family: "Cascadia Mono";
    font-size: 13px;
    font-weight: 700;
}

QPushButton {
    background: transparent;
    border: 0;
    border-left: 3px solid transparent;
    color: #8ea3b8;
    font-weight: 700;
    padding: 11px 14px;
    text-align: left;
}

QPushButton:hover {
    background: #172033;
    color: #e5eef8;
}

QPushButton:checked {
    background: #10242c;
    border-left-color: #22d3ee;
    color: #22d3ee;
}

QPushButton#SegmentButton {
    background: #111827;
    border: 1px solid #263347;
    color: #8ea3b8;
    padding: 6px 10px;
    text-align: center;
}

QPushButton#SegmentButton:hover {
    background: #172033;
    color: #e5eef8;
}

QPushButton#SegmentButton:checked {
    background: #0e7490;
    border-color: #22d3ee;
    color: #ffffff;
}

QPushButton#ActionButton {
    background: #111827;
    border: 1px solid #263347;
    color: #8ea3b8;
    padding: 7px 12px;
    text-align: center;
}

QPushButton#ActionButton:disabled {
    color: #4f6174;
}

QPushButton#RunButton {
    background: #0e7490;
    border: 1px solid #22d3ee;
    color: #ffffff;
    padding: 7px 14px;
    text-align: center;
}

QPushButton#RunButton:checked {
    background: #9f1239;
    border-color: #f43f5e;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #0a0f16;
    border: 1px solid #263347;
    color: #e5eef8;
    padding: 9px 11px;
    selection-background-color: #134e4a;
}

QTextEdit#DetailText {
    background: transparent;
    border: 1px solid #263347;
    color: #e5eef8;
    padding: 12px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #22d3ee;
}

QComboBox::drop-down {
    border: 0;
    width: 26px;
}

QComboBox QAbstractItemView {
    background: #0d1118;
    border: 1px solid #263347;
    color: #e5eef8;
    selection-background-color: #134e4a;
}

QTableWidget, QTableView {
    background: #0b111a;
    border: 1px solid #263347;
    gridline-color: #1f2a3a;
    selection-background-color: #134e4a;
    selection-color: #ffffff;
    alternate-background-color: #111a26;
}

QHeaderView::section {
    background: #162235;
    border: 0;
    border-right: 1px solid #263347;
    color: #22d3ee;
    font-weight: 700;
    padding: 9px;
}

QTableWidget::item, QTableView::item {
    padding: 8px 10px;
}

QTabWidget::pane {
    background: transparent;
    border: 1px solid #263347;
}

QTabBar::tab {
    background: transparent;
    border: 1px solid #172033;
    color: #c9d7e6;
    padding: 7px 12px;
}

QTabBar::tab:selected {
    background: #10242c;
    border-color: #263347;
    color: #ffffff;
}

QSplitter::handle {
    background: #263347;
    width: 1px;
}
"""
