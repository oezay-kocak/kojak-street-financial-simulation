"""World-start selection and isolated prehistory generation UI."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode


class NewSimulationDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Simulation")
        self.setMinimumWidth(820)
        layout = QVBoxLayout(self)
        title = QLabel("NEW SIMULATION")
        title.setObjectName("BrandTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel("Choose how much history exists before you enter the market."))

        modes = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.genesis = self._mode_card(
            "GENESIS WORLD",
            "Start with a young economy and watch its hierarchy emerge.",
            checked=True,
        )
        self.established = self._mode_card(
            "ESTABLISHED WORLD",
            "Generate a mature economy with decades of simulated history before you begin.",
        )
        self.heterogeneous = self._mode_card(
            "HETEROGENEOUS WORLD",
            "Starts on Day 1 with varied country and company sizes, without pre-simulated history.",
        )
        self.mode_group.addButton(self.genesis)
        self.mode_group.addButton(self.established)
        self.mode_group.addButton(self.heterogeneous)
        modes.addWidget(self.genesis.parentWidget())
        modes.addWidget(self.heterogeneous.parentWidget())
        modes.addWidget(self.established.parentWidget())
        layout.addLayout(modes)

        form = QFormLayout()
        self.seed = QSpinBox()
        self.seed.setRange(0, 2_147_483_647)
        self.seed.setValue(1729)
        self.years = QComboBox()
        self.years.addItems(["50 years", "75 years", "100 years"])
        self.years.setPlaceholderText("No prehistory (Day 1)")
        self._prehistory_index = 0
        form.addRow("Seed", self.seed)
        form.addRow("Prehistory", self.years)
        layout.addLayout(form)
        self.genesis.toggled.connect(self._sync_controls)
        self.established.toggled.connect(self._sync_controls)
        self.heterogeneous.toggled.connect(self._sync_controls)
        self._sync_controls()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create World")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _mode_card(self, title: str, description: str, *, checked: bool = False) -> QRadioButton:
        frame = QFrame(self)
        frame.setObjectName("KpiCard")
        box = QVBoxLayout(frame)
        button = QRadioButton(title, frame)
        button.setChecked(checked)
        description_label = QLabel(description, frame)
        description_label.setWordWrap(True)
        description_label.setObjectName("Muted")
        box.addWidget(button)
        box.addWidget(description_label)
        return button

    def _sync_controls(self) -> None:
        if self.heterogeneous.isChecked():
            if self.years.currentIndex() >= 0:
                self._prehistory_index = self.years.currentIndex()
            self.years.setCurrentIndex(-1)
        elif self.years.currentIndex() < 0:
            self.years.setCurrentIndex(self._prehistory_index)
        self.years.setEnabled(self.established.isChecked())

    def config(self) -> WorldGenerationConfig:
        mode = (WorldMode.ESTABLISHED if self.established.isChecked() else
                WorldMode.HETEROGENEOUS if self.heterogeneous.isChecked() else WorldMode.GENESIS)
        years = int(self.years.currentText().split()[0]) if mode == WorldMode.ESTABLISHED else 0
        return WorldGenerationConfig(mode=mode, seed=self.seed.value(), prehistory_years=years).normalized()


class GenerationProgressDialog(QDialog):
    def __init__(self, config: WorldGenerationConfig, project_root: Path, data_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.project_root = Path(project_root)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self.bundle_path = Path(data_root) / "worlds" / f"world-{config.seed}-{config.prehistory_years}y-{stamp}"
        self.process = QProcess(self)
        self._stdout_buffer = ""
        self.completed = False
        self.setWindowTitle("Generating Established World")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)
        self.heading = QLabel(f"ESTABLISHED WORLD · SEED {config.seed} · {config.prehistory_years} YEARS")
        self.heading.setObjectName("BrandTitle")
        self.stage = QLabel("Preparing isolated generation process…")
        self.detail = QLabel("0 years completed")
        self.timing = QLabel("Elapsed — · ETA —")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)
        for widget in (self.heading, self.stage, self.detail, self.timing, self.progress, self.cancel_button):
            layout.addWidget(widget)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(lambda _error: self.stage.setText(self.process.errorString()))

    def start(self) -> None:
        self.bundle_path.parent.mkdir(parents=True, exist_ok=True)
        env = QProcessEnvironment.systemEnvironment()
        source = str(self.project_root / "src")
        env.insert("PYTHONPATH", source + (os.pathsep + env.value("PYTHONPATH") if env.value("PYTHONPATH") else ""))
        self.process.setProcessEnvironment(env)
        self.process.setProgram(sys.executable)
        worker_arguments = [
            "--project-root", str(self.project_root),
            "--output", str(self.bundle_path),
            "--seed", str(self.config.seed),
            "--years", str(self.config.prehistory_years),
        ]
        if getattr(sys, "frozen", False):
            worker_arguments = ["--world-generator", *worker_arguments]
        else:
            worker_arguments = ["-m", "kojakstreet.world_generator", *worker_arguments]
        self.process.setArguments(worker_arguments)
        self.process.start()

    def cancel(self) -> None:
        self.stage.setText("Cancelling safely…")
        self.cancel_button.setEnabled(False)
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(5000):
                self.process.kill()
                self.process.waitForFinished(2000)
        for partial in self.bundle_path.parent.glob(f".{self.bundle_path.name}.*.partial"):
            shutil.rmtree(partial, ignore_errors=True)
        self.reject()

    def _read_stdout(self) -> None:
        self._stdout_buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._apply_event(event)

    def _apply_event(self, event: dict) -> None:
        stage = str(event.get("stage", "simulation"))
        self.stage.setText(str(event.get("error", stage.replace("_", " ").title())))
        self.progress.setValue(round(float(event.get("percent", 0.0)) * 10))
        if stage == "coarse_history":
            self.detail.setText(
                f"{str(event.get('phase', 'coarse')).title()} history · "
                f"{event.get('buckets_completed', 0)} / {event.get('target_buckets', 0)} buckets · "
                f"{event.get('simulation_date', '')}"
            )
        elif "years_completed" in event:
            self.detail.setText(
                f"{float(event['years_completed']):.1f} / {event.get('target_years')} years · {event.get('simulation_date', '')}"
            )
        elapsed = _duration(event.get("elapsed_seconds"))
        eta = _duration(event.get("eta_seconds"))
        self.timing.setText(f"Elapsed {elapsed} · ETA {eta}")
        if stage == "complete":
            self.completed = True

    def _finished(self, exit_code: int, _status) -> None:
        self._read_stdout()
        if exit_code == 0 and self.completed and self.bundle_path.is_dir():
            self.accept()
            return
        self.stage.setText(f"Generation failed (exit {exit_code})")
        self.cancel_button.setText("Close")
        self.cancel_button.setEnabled(True)


def _duration(value: object) -> str:
    if value is None:
        return "—"
    seconds = max(0, int(float(value)))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
