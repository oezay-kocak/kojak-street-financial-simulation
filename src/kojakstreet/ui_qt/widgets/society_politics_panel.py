"""Selected-country society/politics panel, built once in the existing theme."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.ui_qt.models.simple_table_model import SimpleTableModel
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.pie_chart import COLORS, CompositionPie

POOLS = ("basic", "skilled", "highly_qualified")
POOL_LABELS = ("Basic", "Skilled", "Highly Qualified")


def number(value):
    return f"{value:,.0f}" if value is not None else "Not yet observed"


def ideology(value, negative, positive):
    return negative if value < -.25 else positive if value > .25 else "Balanced"


class SocietyPoliticsPanel(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        self.values = {}
        self.captions = {}
        self.region = ""
        self.update_count = 0
        layout.addWidget(self.heading("SOCIETY"))
        society = QGridLayout()
        society.setSpacing(10)
        for i, title in enumerate(("Population", "Birth Rate · annual", "Population Growth · annualized", "Unemployment")):
            society.addWidget(self.card(title), i//2, i%2)
        layout.addLayout(society)
        self.workforce_title = self.heading("WORKFORCE SUPPLY MIX")
        layout.addWidget(self.workforce_title)
        self.workforce_pie = CompositionPie()
        self.workforce_table, self.workforce_model = self.table(["Pool", "Supply", "Demand", "Coverage"])
        self.workforce_table.setFixedHeight(154)
        self.workforce_model.color_callback = lambda row, meta, col: QColor(meta) if col == 0 else None
        row = QHBoxLayout()
        row.addWidget(self.workforce_pie, 1)
        row.addWidget(self.workforce_table, 3)
        layout.addLayout(row)
        unit = self.heading("Supply / demand: workforce equivalents · coverage: supply ÷ demand", muted=True)
        layout.addWidget(unit)
        layout.addWidget(self.heading("POLITICS"))
        politics = QGridLayout()
        politics.setSpacing(10)
        for i, title in enumerate(("Government System", "Political Stability", "Current Government", "Government Status", "Economic Ideology", "Social Ideology", "Next Election / Leadership Review", "Executive")):
            politics.addWidget(self.card(title), i//2, i%2)
        layout.addLayout(politics)
        self.political_title = self.heading("INITIAL MANDATE ALLOCATION")
        layout.addWidget(self.political_title)
        self.political_note = self.heading("No election recorded", muted=True)
        layout.addWidget(self.political_note)
        self.political_pie = CompositionPie()
        self.political_pie.setMaximumHeight(180)
        self.political_area = QStackedWidget()
        self.political_empty = self.empty_state("No election recorded")
        self.political_area.addWidget(self.political_empty)
        self.political_area.addWidget(self.political_pie)
        self.party_table, self.party_model = self.table(["Party", "Share", "Government"])
        self.party_model.color_callback = lambda row, meta, col: QColor(meta) if col == 0 else None
        self.party_table.setFixedHeight(280)
        self.party_area = QStackedWidget()
        self.leadership_empty = self.empty_state("Leadership continuity is assessed without competitive party votes")
        self.party_area.addWidget(self.party_table)
        self.party_area.addWidget(self.leadership_empty)
        self.party_area.setFixedHeight(280)
        row = QHBoxLayout()
        row.addWidget(self.political_area, 1)
        row.addWidget(self.party_area, 3)
        layout.addLayout(row)
        self.continuity = self.heading("No competitive party election", muted=True)
        layout.addWidget(self.continuity)
        layout.addStretch(1)

    def heading(self, title, muted=False):
        label = QLabel(title)
        label.setObjectName("Muted" if muted else "SectionTitle")
        label.setWordWrap(True)
        return label

    def empty_state(self, title):
        frame = QFrame()
        frame.setObjectName("EmptyState")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 12, 12, 12)
        label = self.heading(title, muted=True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(label)
        return frame

    def card(self, title):
        frame = QFrame()
        frame.setObjectName("KpiCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 8, 10, 8)
        caption = self.heading(title.upper(), muted=True)
        self.captions[title] = caption
        value = QLabel("—")
        value.setObjectName("DetailValue")
        value.setWordWrap(True)
        self.values[title] = value
        box.addWidget(caption)
        box.addWidget(value)
        return frame

    def table(self, headers):
        table = QTableView()
        model = SimpleTableModel(headers, right_aligned_columns=set(range(1, len(headers))))
        table.setModel(model)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        optimize_table_view(table)
        return table, model

    def apply_data(self, region, society, politics):
        self.region = region
        self.update_count += 1
        if not society or not politics:
            for value in self.values.values():
                value.setText("Unavailable")
            self.workforce_pie.set_data([])
            self.political_pie.set_data([])
            self.workforce_model.set_rows([])
            self.party_model.set_rows([])
            return
        self.values["Population"].setText(number(society["population"]))
        self.values["Birth Rate · annual"].setText(f"{society['birth_rate']*100:.2f}%")
        growth = society["population_growth_annualized"]
        self.values["Population Growth · annualized"].setText("Not yet observed" if growth is None else f"{growth*100:+.2f}%")
        self.values["Population Growth · annualized"].setToolTip(f"Observed interval: {society['population_interval_years']:.4f} years; ending {society['population_interval_end'] or 'not yet observed'}")
        self.values["Unemployment"].setText(f"{society['unemployment']*100:.2f}%")
        pools = society["pools"]
        total = sum(pools[k]["supply"] for k in POOLS)
        slices, rows = [], []
        for i, (key, label) in enumerate(zip(POOLS, POOL_LABELS, strict=True)):
            pool = pools[key]
            share = pool["supply"]/total if total else 0
            if share:
                slices.append((key, label, share, COLORS[i], f"{label}: {share*100:.1f}% · {number(pool['supply'])} workforce equivalents"))
            rows.append([f"{label} · {share*100:.1f}%", number(pool["supply"]), number(pool["demand"]), f"{pool['coverage']*100:.1f}%"])
        self.workforce_pie.set_data(slices)
        self.workforce_model.set_rows(rows, metadata=list(COLORS[:3]))
        self.values["Government System"].setText(politics["system"])
        self.captions["Current Government"].setText("CABINET" if politics["system_code"] == "semi_presidential_democracy" else "CURRENT GOVERNMENT")
        self.values["Political Stability"].setText(f"{politics['stability']:.1f} / 100")
        self.values["Political Stability"].setToolTip(f"Political continuity: {politics['political_stability']:.1f}; current economic/crisis pressure: {politics['macro_pressure']:.1f}. Government type has no automatic score.")
        parties = sorted(politics["parties"], key=lambda a: a["id"])
        names = {a["id"]: a["name"] for a in parties}
        government = ", ".join(names[i] for i in politics["government_ids"])
        self.values["Current Government"].setText(government or "State leadership")
        self.values["Government Status"].setText(politics["status"].replace("_", " ").title())
        self.values["Economic Ideology"].setText(ideology(politics["ideology"][0], "Interventionist", "Market Liberal"))
        self.values["Social Ideology"].setText(ideology(politics["ideology"][1], "Progressive", "Conservative"))
        due = politics["next_election"] or politics["next_review"]
        self.values["Next Election / Leadership Review"].setText(("Election · " if politics["next_election"] else "Leadership review · ") + due if due else "No scheduled leadership cycle")
        self.values["Executive"].setText(names.get(politics["executive_id"], "Not separate from government"))
        elected = politics["result_date"] is not None
        competitive = politics["next_election"] is not None
        self.political_title.setText("LATEST SIMULATED ELECTION VOTE SHARE" if elected else "INITIAL MANDATE ALLOCATION" if competitive else "LEADERSHIP & CONTINUITY")
        self.political_note.setText(f"{politics['result_type'].replace('_', ' ')} · {politics['result_date']}" if elected else "Initial mandate allocation – no election recorded" if competitive else "No competitive party election")
        slices, rows, colors = [], [], []
        for a in parties:
            slot = int(a["id"].rsplit("p", 1)[-1])
            color = COLORS[slot % len(COLORS)]
            share = a["latest_vote_share"] if elected else a["mandate_share"]
            marker = "Government" if a["id"] in politics["government_ids"] else "Opposition"
            rows.append([a["name"], f"{share*100:.1f}%" if competitive else "No vote recorded", marker])
            colors.append(color)
            if elected:
                slices.append((a["id"], a["name"], share, color, f"{a['name']}: {share*100:.1f}% · {marker}"))
        self.political_pie.set_data(slices)
        self.political_area.setCurrentWidget(self.political_pie if elected else self.political_empty)
        self.political_pie.setVisible(elected)
        self.party_model.set_rows(rows, metadata=colors)
        self.party_area.setCurrentWidget(self.party_table if parties else self.leadership_empty)
        self.political_empty.findChild(QLabel).setText("No election recorded" if competitive else "No competitive party election")
        self.continuity.setVisible(not competitive)
        self.continuity.setText("No competitive party election · leadership continuity" if not competitive else "")
