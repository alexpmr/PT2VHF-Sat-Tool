"""v1.9.0: botão PREVER — passagens das próximas horas de todos os satélites selecionados numa lista só.

Pedido do PU2MUS: não ter que consultar satélite por satélite. A elevação mínima filtra as passagens
pela elevação máxima (passagens baixas demais ficam de fora).
"""
from __future__ import annotations

import csv
import threading
from datetime import datetime, timedelta, timezone

from .core import make_satellite, predict_passes, now_utc


def forecast_passes(orbits: dict, ids, station, *, hours: float = 24, min_elevation: float = 10.0,
                    now: datetime | None = None, ts=None, cancel=None) -> list[dict]:
    """Passagens (AOS dentro da janela, ou em andamento) de cada satélite, ordenadas pelo AOS."""
    now = now or now_utc()
    end = now + timedelta(hours=float(hours))
    out = []
    for ident in ids:
        if cancel is not None and cancel.is_set():
            break
        orbit = orbits.get(str(ident))
        if not orbit:
            continue
        try:
            sat = make_satellite(orbit, ts)
            rows = predict_passes(sat, station, now=now, hours=float(hours), ts=ts)
        except Exception:
            continue
        for p in rows:
            if p.get("los") is None or p["los"] <= now or p["aos"] > end:
                continue
            if float(p.get("max_el") or 0.0) < float(min_elevation):
                continue
            out.append({**p, "id": str(ident), "name": str(orbit.get("OBJECT_NAME") or ident),
                        "duration_s": max(0.0, (p["los"] - p["aos"]).total_seconds())})
    out.sort(key=lambda p: (p["aos"], -p["max_el"]))
    return out


def local(moment: datetime | None) -> str:
    if moment is None:
        return "—"
    return moment.astimezone().strftime("%d/%m %H:%M:%S")


def duration_text(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60:d}:{seconds % 60:02d}"


def write_csv(path, passes):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["satellite", "norad", "aos_local", "tca_local", "los_local", "duration", "max_elevation"])
        for p in passes:
            writer.writerow([p["name"], p["id"], local(p["aos"]), local(p.get("tca")), local(p["los"]),
                             duration_text(p["duration_s"]), f"{p['max_el']:.1f}"])


def open_forecast(window):
    """Janela PREVER ligada à janela principal (satélites selecionados, estação salva, catálogo)."""
    from .qt_compat import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDoubleSpinBox,
                            QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, Qt, QObject, Signal)

    class Bridge(QObject):
        done = Signal(object, object)

    existing = getattr(window, "_forecast_dialog", None)
    if existing is not None:
        existing.show(); existing.raise_(); existing.activateWindow()
        return existing
    cfg = window.config.values
    dialog = QDialog(window)
    dialog.setWindowTitle("Prever passagens")
    dialog.resize(760, 520)
    lay = QVBoxLayout(dialog)
    bar = QHBoxLayout()
    bar.addWidget(QLabel("Elevação mínima"))
    min_el = QDoubleSpinBox(); min_el.setRange(0, 90); min_el.setDecimals(0); min_el.setSuffix("°")
    min_el.setValue(float(cfg.get("forecast_min_elevation", 10)))
    bar.addWidget(min_el)
    bar.addWidget(QLabel("Próximas"))
    hours = QDoubleSpinBox(); hours.setRange(1, 72); hours.setDecimals(0); hours.setSuffix(" h")
    hours.setValue(float(cfg.get("forecast_hours", 24)))
    bar.addWidget(hours)
    run = QPushButton("Calcular")
    save = QPushButton("Salvar CSV"); save.setEnabled(False)
    bar.addWidget(run); bar.addWidget(save); bar.addStretch(1)
    lay.addLayout(bar)
    status = QLabel("Satélites selecionados, estação salva e horário local.")
    status.setWordWrap(True)
    lay.addWidget(status)
    table = QTableWidget(0, 6)
    table.setHorizontalHeaderLabels(["Satélite", "AOS local", "TCA local", "LOS local", "Duração", "Elevação máxima"])
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.setToolTip("Clique duas vezes para selecionar o satélite na aba Operação")
    lay.addWidget(table, 1)
    bridge = Bridge(dialog)
    state = {"passes": [], "cancel": threading.Event()}

    def fill(passes, error):
        run.setEnabled(True)
        if error:
            status.setText(f"Falha ao calcular: {error}")
            return
        state["passes"] = passes
        table.setRowCount(len(passes))
        for r, p in enumerate(passes):
            values = [f"{p['name']} ({p['id']})", local(p["aos"]), local(p.get("tca")), local(p["los"]),
                      duration_text(p["duration_s"]), f"{p['max_el']:.1f}°"]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                if c == 0:
                    item.setData(Qt.UserRole, p["id"])
                if c == 5 and p["max_el"] >= 45:
                    item.setForeground(Qt.green)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        save.setEnabled(bool(passes))
        status.setText(f"{len(passes)} passagens de {state['count']} satélites nas próximas "
                       f"{hours.value():.0f} h com elevação máxima a partir de {min_el.value():.0f}°.")

    bridge.done.connect(fill)

    def calculate():
        try:
            station = window.saved_station()
        except Exception as exc:
            status.setText(str(exc))
            return
        if station is None:
            status.setText("Cadastre e salve a estação antes de prever passagens.")
            return
        ids = [i for i in window.enabled_satellite_ids() if i in window.omm]
        if not ids:
            status.setText("Nenhum satélite selecionado no catálogo.")
            return
        cfg["forecast_min_elevation"] = float(min_el.value())
        cfg["forecast_hours"] = float(hours.value())
        window.config.save()
        state["count"] = len(ids)
        run.setEnabled(False)
        status.setText(f"Calculando {len(ids)} satélites…")
        orbits = {i: dict(window.omm[i]) for i in ids}
        h, m = float(hours.value()), float(min_el.value())

        def work():
            try:
                bridge.done.emit(forecast_passes(orbits, ids, station, hours=h, min_elevation=m,
                                                 ts=window.ts, cancel=state["cancel"]), None)
            except Exception as exc:   # pragma: no cover - relatado na própria janela
                try:
                    bridge.done.emit([], str(exc))
                except RuntimeError:
                    pass
        threading.Thread(target=work, name="sat-forecast", daemon=True).start()

    def export():
        path, _ = QFileDialog.getSaveFileName(dialog, "Salvar previsão", "previsao_passagens.csv", "CSV (*.csv)")
        if path:
            try:
                write_csv(path, state["passes"])
                status.setText(f"Previsão salva em {path}")
            except OSError as exc:
                QMessageBox.warning(dialog, "Prever passagens", str(exc))

    def choose(row, _col):
        item = table.item(row, 0)
        if item is None:
            return
        index = window.sat_combo.findData(str(item.data(Qt.UserRole)))
        if index >= 0:
            window.search.clear()
            window.sat_combo.setCurrentIndex(index)
            window.tabs.setCurrentIndex(0)
            window.raise_(); window.activateWindow()

    def closed(*_):
        state["cancel"].set()
        window._forecast_dialog = None

    run.clicked.connect(calculate)
    save.clicked.connect(export)
    table.cellDoubleClicked.connect(choose)
    dialog.finished.connect(closed)
    dialog.calculate, dialog.table, dialog.status_label = calculate, table, status
    dialog.min_elevation, dialog.hours, dialog.state = min_el, hours, state
    window._forecast_dialog = dialog
    dialog.show()
    calculate()
    return dialog
