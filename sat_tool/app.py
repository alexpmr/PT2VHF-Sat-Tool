"""PT2VHF Sat Tool desktop Windows MVP.

UI is intentionally non-transmitting: no CAT TX/PTT commands exist.
"""
from __future__ import annotations
import json
import os
import math
import time
import unicodedata
import sys
import threading
import traceback
import wave
import struct
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .qt_compat import Qt, QTimer, QObject, Signal, Slot, QUrl
from .crash_diagnostics import heartbeat,report_event,report_exception,diagnostic_dir
from .log_journal import EventJournal
from .qt_compat import QDoubleValidator, QFont, QIcon, QPixmap, QColor, QBrush
from .qt_compat import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QGroupBox, QTabWidget, QPlainTextEdit,
    QSplitter, QMessageBox, QDialog, QMenu, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QAbstractItemView, QProgressDialog, QScrollArea, QProgressBar, QFileDialog,
)
from .qt_compat import QWebEngineView, QGeoPositionInfoSource, qt_exec, QT_BINDING
from skyfield.api import load
from . import __version__
from .passfmt import radial_kmh_text
from .appearance import DEFAULTS as THEME_DEFAULTS
from .rotor_ui import RotorUiMixin
from .cat import TS2000, available_ports, decode_satellite_status
from .catalog import refresh_orbits, load_orbits, refresh_transmitters, load_transmitters, age_hours, satellite_search_text, normalized_satellite_search, DEFAULT_GROUPS
from .config import Config, DEFAULT_SATELLITES
from .geolocation import GeoFix
from .maidenhead import maidenhead_to_latlon
from .location_map import parse_coordinate_fields, sanitize_map_pick, valid_coordinates
from .frequency import format_frequency,parse_mhz_input,frequency_label
from .transponder import prioritized_transponders,cat_pair_diagnostic
from .i18n import LANGUAGES,translated,resolve_language,flag_icon
from .satellite_info import orbital_characteristics, operational_characteristics, characteristics_text
from .updater import check_for_update, download_update, install_flavor, launch_staged_update
from .profile import choose_satellites, capability, render_service, CANDIDATES
from .selection import change_selection, transmitter_batch_ids
from .alerts import eta_seconds, format_duration, selected_aos_alarm
from .web_ui import LocalStatusServer
from .media import find_photo, photo_html
from .operations import (select_next_pass, select_selected_satellite_pass,
                         frequency_prediction, status_at, orbital_age_days)
from .core import (Station, now_utc, make_satellite, position, ground_track, footprint,
                   predict_passes, transponder_options, doppler_frequencies, paired_linear_uplink,
                   ground_track_between, track_period_bounds)

def branding_asset(name):
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    return root/'assets'/'branding'/name


STYLE = """
QWidget {background:#0b1526; color:#e8edf5;font-family:'Segoe UI';font-size:12px}
QMainWindow {background:#081323} QGroupBox {border:1px solid #253f58;border-radius:9px;
 margin-top:13px;padding:13px 10px 8px;font-weight:600;background:#0e1f34}
QGroupBox::title {subcontrol-origin:margin;left:10px;padding:0 6px;color:#64ded2}
QLineEdit,QComboBox,QDoubleSpinBox {background:#14283d;border:1px solid #33506c;
 border-radius:6px;padding:6px;selection-background-color:#1e8caa}
QPushButton {background:#184b6b;border:1px solid #306f8d;border-radius:6px;padding:7px 10px;font-weight:600}
QPushButton:hover {background:#226688} QPushButton:disabled {background:#183045;color:#778fa0}
QPushButton#primary {background:#087b75;border-color:#24ad9d} QPushButton#danger {background:#653c3a}
QTabWidget::pane {border:0} QTabBar::tab {padding:11px 21px;background:#162943;color:#bdd0df}
QTabBar::tab:selected {background:#145d72;color:white} QLabel#metric {font-size:20px;font-weight:700;color:#62ead8}
QPlainTextEdit,QTableWidget {background:#0b1b2e;border:1px solid #2b4a65;border-radius:5px}
QHeaderView::section{background:#18334c;color:#c1d9e4;padding:6px}
QSplitter::handle {background:#1d354a}
QTabBar::tab:selected {background:#155b82;border-bottom:2px solid #27d7f1}
QGroupBox {border-color:#244b6b;background:#0a1c30}
QGroupBox::title {color:#36d3ed;font-size:11px}
QTableWidget {gridline-color:#173a55;alternate-background-color:#10283f}
QTableWidget::item:selected {background:#155b80;color:white}
QPushButton#primary {background:#087a75;border:1px solid #22cab4}
QScrollBar:vertical {background:#091b2b;width:9px}
QScrollBar::handle:vertical {background:#1e5775;border-radius:4px;min-height:24px}
QHeaderView::section {background:#163750;color:#bbdceb;font-weight:700}
QStatusBar {background:#08182c;color:#88b7c9;font-size:11px}
"""

class Events(QObject):
    result = Signal(str, object)
    failure = Signal(str, str)
    progress = Signal(int, int)
    record = Signal(str)


def label(t):
    w = QLabel(t)
    w.setWordWrap(True)
    return w


def group(title):
    g = QGroupBox(title)
    return g, QVBoxLayout(g)


class MainWindow(RotorUiMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'PT2VHF Sat Tool  •  v{__version__}')
        icon_path=branding_asset('icon-256.png')
        if icon_path.exists():self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1650, 930)
        self.setMinimumSize(1120, 700)
        self.config = Config()
        self.journal = EventJournal(self.config.dir / "logs")
        self.ts = load.timescale(builtin=True)
        self.radio = TS2000(self.log)
        self.rotor_init()
        self.events = Events()
        self.events.result.connect(self.background_result)
        self.events.failure.connect(self.background_error)
        self.events.progress.connect(self.download_progress)
        self.events.record.connect(self._append_log)
        self.available_update = None
        self.update_dialog = None
        self.update_last_checked = 0
        self.update_distribution = install_flavor(QT_BINDING)
        self.manual_update_requested = False
        self._update_prompted_version = None
        self.omm = {}
        self.sat = None
        self.options = []
        self.last_pos = None
        self.last_map_time = None
        self.pending_jobs = set()
        self.passes = []
        self.next_candidate = None
        self.track_cache_key = None
        self.track_pending_key = None
        self.track_cache = {"past": [], "future": []}
        self.plan_satellites = {}
        self.pass_rows = {}
        self.pass_enabled = set()
        self.tx_prefetch_started = set()
        self.last_freqs = (None, None)
        self.last_radio_poll = 0
        self.last_cat_success = None
        self.last_cat_telemetry = None
        self.selected_cat_target = None
        self.freq_update_cancel = False
        self.freq_update_stats = None
        self.frequency_progress_dialog = None
        self.frequency_started_at = None
        self.orbit_started_at = None
        self.orbit_progress_dialog = None
        self.aos_alarm_dialog = None
        self.aos_alarm_target = None
        self.aos_alarm_title = None
        self.aos_alarm_detail = None
        self.aos_alarm_silenced = False
        self.aos_alarm_last_second = None
        self._alarm_sound_effect = None
        self.web_server = None
        self._web_last_push = 0.0
        self.cat_selection_generation = 0
        self.cat_autotune_requested_generation = -1
        self.cat_retry_after = 0.0
        self.cat_consecutive_failures = 0
        self.cat_tune_manual_request = False
        self.cat_tracking_armed = False
        self.cat_connecting = False
        self.cat_connect_was_startup = False
        self.last_tracking_write = 0.0
        self.last_cat_poll_started = 0.0
        self.last_cat_track_completed = 0.0
        self.last_cat_frequency_readback = 0.0
        self.cat_live_queued = False
        self.cat_last_requested = (None,None)
        self.cat_last_roundtrip_ms = None
        self.last_cat_readback_requested = 0.0
        self.cat_last_preview_time = 0.0
        self.cat_last_gate = None
        self.cat_last_gate_time = 0.0
        self.cat_tracking_commands = 0
        self.cat_tracking_confirmed = 0
        self._mode_catalog_sat_id = None
        self._loading_satellites = False
        self._loading_catalog = False
        self._active_satellite_id = None
        self._passes_refresh_again = False
        self._pass_refresh_last = 0.0
        self._pass_refresh_sat = None
        self.pos_source = None
        self.map_pick_active = False
        self.map_pick_position = None
        self.init_ui()
        self.capture_static_language()
        self.load_fields()
        self.apply_language()
        self.populate_catalog(load_orbits(self.config.dir))
        self.update_ports()
        self.init_sdr_dock()
        if age_hours(self.config.dir,"amateur_omm.json") is None or age_hours(self.config.dir,"amateur_omm.json")>self.config.values.get("tle_update_hours",4):
            self.refresh_catalog()
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(1000)
        self.cat_live_timer=QTimer(self)
        self.cat_live_timer.timeout.connect(self.cat_live_tick)
        self.cat_live_timer.start(250)
        self.tick()
        self.diagnostic_timer=QTimer(self)
        self.diagnostic_timer.timeout.connect(heartbeat)
        self.diagnostic_timer.start(30000)
        # Delay startup network I/O until the UI is visible.
        QTimer.singleShot(1800, self.show_official_site_notice)
        QTimer.singleShot(12000, self.check_for_updates)
        if self.config.values.get("cat_auto_connect_startup",True) and self.config.values.get("port","").strip():
            QTimer.singleShot(1200, self.startup_cat_connect)
        if self.config.values.get("web_enabled",False):
            QTimer.singleShot(700,self.start_web_server)
        if self.config.values.get("display_detached",False):
            QTimer.singleShot(400,self.toggle_display_detached)
        self.install_display_shortcuts()
        if self.theme_options()!=THEME_DEFAULTS:
            QTimer.singleShot(0,self.apply_appearance)

    def install_display_shortcuts(self):
        """Atalhos do display: F6 = TIPO, F7 = LUZ, F8 = destacar/voltar."""
        from .qt_compat import QShortcut, QKeySequence
        self.display_shortcuts=[]
        for key,func in (("F6",lambda:self.cycle_display("model")),("F7",lambda:self.cycle_display("theme")),
                         ("F8",self.toggle_display_detached)):
            sc=QShortcut(QKeySequence(key),self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(func)
            self.display_shortcuts.append(sc)

    def show_official_site_notice(self):
        """Boas-vindas (v1.5.0): convite às demais aplicações PT2VHF, com link e botão Fechar."""
        from .qt_compat import QDialog, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle('PT2VHF Sat Tool')
        layout = QVBoxLayout(dialog)
        title = QLabel('Feito por radioamadores, para radioamadores')
        title.setStyleSheet('font-size:18px;font-weight:700')
        text = QLabel('Obrigado por usar o PT2VHF Sat Tool! Conheça também as outras aplicações gratuitas '
                      'desenvolvidas para a comunidade: APRS Client, Prop Tool, Mesh Analyzer, Prog Tool e mais.')
        text.setWordWrap(True)
        link = QLabel('<a href="https://www.pt2vhf.com" style="color:#6cc7ff;font-weight:700">www.PT2VHF.com</a>')
        link.setOpenExternalLinks(True)
        buttons = QDialogButtonBox()
        close = buttons.addButton('Fechar', QDialogButtonBox.RejectRole)
        close.setDefault(True)
        buttons.rejected.connect(dialog.reject)
        for widget in (title, text, link):
            layout.addWidget(widget)
        layout.addWidget(buttons)
        dialog.setMinimumWidth(520)
        qt_exec(dialog)

    def log(self,message):
        """Qt widgets may only be modified from the GUI thread.

        CAT polling and transmitter downloads run in Python background threads.
        Posting their messages directly to QPlainTextEdit can crash PySide/Qt.
        """
        msg=str(message)
        self.journal.append(msg)
        if not msg.startswith(("RX ","TX ")):
            report_event(msg)
        if threading.current_thread() is threading.main_thread():
            self._append_log(msg)
        else:
            try:
                self.events.record.emit(msg)
            except RuntimeError:
                # Application already closing; late worker result is discarded.
                pass

    @Slot(str)
    def _append_log(self,message):
        if hasattr(self,"log_view"):
            self.log_view.appendPlainText(
                f"{datetime.now().astimezone():%H:%M:%S}  {message}")

    def background(self, key, fn):
        if key in self.pending_jobs:
            return
        self.pending_jobs.add(key)
        def run():
            try:
                value = fn()
                self.events.result.emit(key, value)
            except Exception as exc:
                report_exception("Worker "+key,exc)
                try:self.events.failure.emit(key,str(exc))
                except RuntimeError:pass
        threading.Thread(target=run, name='sat-'+key, daemon=True).start()

    def init_ui(self):
        root = QTabWidget()
        self.tabs = root
        self.setCentralWidget(root)
        operation = QWidget(); op = QVBoxLayout(operation); op.setContentsMargins(8,6,8,6)
        op.setSpacing(5)
        header = QHBoxLayout()
        logo_path=branding_asset('icon-256.png')
        if logo_path.exists():
            icon=QLabel()
            icon.setPixmap(QPixmap(str(logo_path)).scaled(37,37,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            header.addWidget(icon)
        headline = QLabel(f'PT2VHF  SAT TOOL   v{__version__}')
        headline.setStyleSheet('font-size:20px;font-weight:800;color:#e9fbff;letter-spacing:1px')
        header.addWidget(headline)
        self.version_btn = QPushButton("Verificar atualizações")
        self.version_btn.setToolTip("Verificar versões em www.pt2vhf.com; iniciar atualização com autorização")
        self.version_btn.clicked.connect(lambda: self.request_update(manual=True))
        self.version_btn.setStyleSheet('background:#155a3e;border:1px solid #30a579;color:#e6fff4')
        header.addWidget(self.version_btn)
        self.summary = label("Dados orbitais não carregados")
        self.summary.setStyleSheet('color:#85aaba;font-size:11px')
        self.summary.setWordWrap(False)
        self.summary.setMinimumWidth(80)
        header.addWidget(self.summary, 1)
        self.cat_indicator=QPushButton("CAT")
        self.cat_indicator.setToolTip("Clique para conectar ou desconectar o TS-2000 pela porta CAT configurada")
        self.cat_indicator.clicked.connect(self.toggle_connection)
        self.cat_indicator.setFixedWidth(66)
        self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ef9a9a;padding:4px;background:#243143;border-radius:5px")
        header.addWidget(self.cat_indicator)
        self.sdr_toggle=QPushButton("SDR")
        self.sdr_toggle.setToolTip("Mostrar/ocultar o painel SDR (não liga nem desliga o receptor)")
        self.sdr_toggle.setFixedWidth(66)
        self.sdr_toggle.setStyleSheet("font-size:12px;font-weight:800")
        header.addWidget(self.sdr_toggle)
        self.build_rotor_top_button(header)  # v1.7.2: liga/desliga o controlador do rotor, como CAT e SDR
        self.build_language_menu(header)
        self.utc = QLabel("DATA/HORA UTC —")
        self.utc.setStyleSheet("font-size:12px;font-weight:700;color:#dff9ff;padding:4px;background:#153751;border:1px solid #34758c;border-radius:5px")
        self.utc.setWordWrap(False)
        self.utc.setMinimumWidth(0)
        header.addWidget(self.utc)
        op.addLayout(header)
        upcoming,upcoming_layout=group("PRÓXIMA PASSAGEM DO SATÉLITE SELECIONADO · CONTAGEM REGRESSIVA")
        upcoming_row=QHBoxLayout()
        self.next_event_label=label("Cadastre a estação e selecione FM / SSB / CW")
        self.next_event_label.setStyleSheet("font-size:14px;font-weight:800;color:#70d8ed")
        self.next_countdown=label("--:--:--")
        self.next_countdown.setStyleSheet("font-size:23px;font-weight:800;color:#e5faff")
        self.next_countdown.setAlignment(Qt.AlignRight)
        self.next_select=QPushButton("Mostrar no mapa")
        self.next_select.clicked.connect(self.select_next_candidate)
        self.next_select.setEnabled(False)
        upcoming_row.addWidget(self.next_event_label,4)
        upcoming_row.addWidget(self.next_countdown,1)
        upcoming_row.addWidget(self.next_select)
        upcoming_layout.addLayout(upcoming_row)
        self.next_event_label.setWordWrap(False)
        self.next_times=label("AOS — · TCA — · LOS — · Elevação máxima —")
        self.next_times.setStyleSheet("color:#b5cfde;font-size:11px")
        self.next_times.setWordWrap(False)
        upcoming_layout.addWidget(self.next_times)
        self.next_frequencies=label("RX/TX: aguardando transponder publicado e TLE válido")
        self.next_frequencies.setStyleSheet("color:#7ee5d4;font-size:12px;font-weight:700")
        self.next_frequencies.setWordWrap(False)
        upcoming_layout.addWidget(self.next_frequencies)
        self.pass_progress=QProgressBar()
        self.pass_progress.setRange(0,1000)
        self.pass_progress.setValue(0)
        self.pass_progress.setMaximumHeight(7)
        self.pass_progress.setTextVisible(False)
        self.pass_progress.setStyleSheet("QProgressBar{background:#10243c;border:0;border-radius:3px}QProgressBar::chunk{background:#35d9b6;border-radius:3px}")
        upcoming_layout.addWidget(self.pass_progress)
        # The next-pass countdown belongs to orbital telemetry, not a
        # separate banner consuming the full width above the operation.
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        left = QWidget()
        left_container=QVBoxLayout(left);left_container.setContentsMargins(0,0,0,0)
        left_scroll=QScrollArea();left_scroll.setWidgetResizable(True)
        left_body=QWidget();lv=QVBoxLayout(left_body);lv.setContentsMargins(3,0,3,0)
        left_scroll.setWidget(left_body);left_container.addWidget(left_scroll)
        pick,pv=group("SATÉLITE E TRANSPONDER")
        self.search = QLineEdit();self.search.setPlaceholderText("Filtrar satélites por nome / NORAD...")
        self.search.textChanged.connect(self.filter_sats)
        pv.addWidget(self.search)
        self.sat_list=QTableWidget(0,2)
        self.sat_list.setHorizontalHeaderLabels(["SATÉLITE / NORAD","MODOS"])
        self.sat_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sat_list.verticalHeader().setVisible(False)
        self.sat_list.setShowGrid(False)
        self.sat_list.setMinimumHeight(115);self.sat_list.setMaximumHeight(165)
        self.sat_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sat_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sat_list.cellClicked.connect(self.select_list_satellite)
        pv.addWidget(self.sat_list)
        self.sat_combo = QComboBox()
        self.sat_combo.setMinimumWidth(190)
        self.sat_combo.currentIndexChanged.connect(self.choose_satellite)
        self.sat_combo.activated.connect(self.arm_cat_tracking)
        self.sat_detail = label("Atualize o catálogo OMM")
        self.sat_detail.setStyleSheet("color:#a9c5d9")
        pv.addWidget(self.sat_detail)
        self.photo=QWebEngineView()
        self.photo.setMaximumHeight(120)
        self.photo.setHtml(photo_html(None))
        pv.addWidget(self.photo)
        self.refresh_omm_btn = QPushButton("Atualizar órbitas (OMM + TLE)")
        self.refresh_omm_btn.clicked.connect(self.refresh_catalog)
        pv.addWidget(self.refresh_omm_btn)
        self.mode_combo=QComboBox()
        self.mode_combo.currentIndexChanged.connect(self.choose_mode)
        self.mode_combo.activated.connect(self.arm_cat_tracking)
        self.mode_combo.setMinimumWidth(220)
        self.refresh_tx_btn=QPushButton("Atualizar frequências / modos")
        self.refresh_tx_btn.clicked.connect(lambda:self.refresh_modes(force=True))
        pv.addWidget(self.refresh_tx_btn)
        lv.addWidget(pick)
        freqs,fv=group("FREQUÊNCIAS NOMINAIS")
        form=QGridLayout()
        self.down_edit=QLineEdit();self.up_edit=QLineEdit()
        for inp in (self.down_edit,self.up_edit):
            inp.setPlaceholderText("145.825.00 ou 145,825000 MHz")
        form.addWidget(label("Downlink · RX (MHz)"),0,0)
        form.addWidget(self.down_edit,1,0)
        form.addWidget(label("Uplink · TX (MHz)"),2,0)
        form.addWidget(self.up_edit,3,0)
        self.down_edit.editingFinished.connect(self.pair_linear)
        self.down_edit.editingFinished.connect(self.on_cat_operator_changed)
        self.up_edit.editingFinished.connect(self.on_cat_operator_changed)
        self.rx_mode=QComboBox();self.tx_mode=QComboBox()
        for cb in (self.rx_mode,self.tx_mode):cb.addItems(["FM","USB","LSB","CW","AM","FSK"])
        self.rx_mode.activated.connect(self.on_cat_operator_changed)
        form.addWidget(label("Modo RX"),4,0);form.addWidget(self.rx_mode,5,0)
        form.addWidget(label("Modo TX (referência)"),6,0);form.addWidget(self.tx_mode,7,0)
        fv.addLayout(form)
        self.mode_note=label("Selecione uma frequência do SatNOGS ou informe manualmente.")
        self.mode_note.setStyleSheet("color:#e3c477")
        fv.addWidget(self.mode_note)
        # Retire the competing legacy Doppler control; use Auto CAT as the single control.
        self.doppler_checkbox=QCheckBox()
        self.doppler_checkbox.setChecked(False)
        # The old manual apply/sync buttons are removed: Auto CAT is the sole
        # user-authorized, continuously verified frequency/mode write path.
        lv.addWidget(freqs)
        lv.addStretch(1)
        # Old satellite editor moves to Settings without deleting its controls.
        # Predicted RX/TX operates without CAT or satellite visibility.
        operator_panel,ov=group("SATÉLITE · FREQUÊNCIAS")
        selectors=QHBoxLayout()
        selectors.addWidget(label("Satélite"))
        selectors.addWidget(self.sat_combo,2)
        selectors.addWidget(label("Serviço / modo"))
        selectors.addWidget(self.mode_combo,3)
        ov.addLayout(selectors)
        frequency_cards=QHBoxLayout()
        frequency_cards.setSpacing(4)
        frequency_cards.setContentsMargins(2,0,2,0)
        self.pred_rx=label("RX / DOWNLINK\nAguardando satélite")
        self.pred_tx=label("TX / UPLINK\nAguardando satélite")
        # v1.6.0: display LCD âmbar de matriz de pontos no lugar dos cartões RX/TX (textos mantidos ocultos
        # para acessibilidade/painel Web).
        from .lcd import LcdDisplay
        self.lcd=LcdDisplay(theme=str(self.config.values.get("lcd_theme","âmbar")),
                            model=str(self.config.values.get("display_model","matriz")),
                            font=str(self.config.values.get("display_font","normal")))
        self.lcd.swap_clicked.connect(self.toggle_main_sub)
        self.lcd.rx_only_clicked.connect(self.toggle_rx_only)
        # v1.7.1: teclas TIPO/LUZ, menu de contexto e destacar o display
        self.lcd.type_clicked.connect(lambda:self.cycle_display("model"))
        self.lcd.light_clicked.connect(lambda:self.cycle_display("theme"))
        self.lcd.model_chosen.connect(lambda code:self.set_display_choice(model=code))
        self.lcd.theme_chosen.connect(lambda name:self.set_display_choice(theme=name))
        self.lcd.scope_clicked.connect(self.display_scope_tune)
        self.lcd.detach_requested.connect(self.toggle_display_detached)
        self.lcd.set_state(rx_only=bool(self.config.values.get("rx_only",False)))
        for card in (self.pred_rx,self.pred_tx):
            card.setVisible(False)
        frequency_cards.addWidget(self.lcd,1)
        self.display_cards=frequency_cards
        self.display_window=None
        self.display_placeholder=label("Display destacado em outra janela · clique para trazer de volta")
        self.display_placeholder.setStyleSheet("color:#9fb8c4;font-size:11px;padding:4px")
        self.display_placeholder.setVisible(False)
        self.display_placeholder.mousePressEvent=lambda _e:self.toggle_display_detached()
        frequency_cards.addWidget(self.display_placeholder,1)
        ov.addLayout(frequency_cards)
        self.corrected_label=label("Previsão orbital sem CAT e sem transmissão")
        self.corrected_label.setStyleSheet("color:#a4d5df;font-size:11px")
        self.corrected_label.setVisible(False)
        ov.addWidget(self.corrected_label)
        # Distinguish calculated Doppler frequency from real FA/FB CAT state.
        # Never silently copy the radio dial to the mathematical prediction.
        self.pred_cat_status=label("CAT · sem leitura recente FA/FB")
        self.pred_cat_status.setStyleSheet("font-size:12px;color:#c5dbe7")
        ov.addWidget(self.pred_cat_status)
        op.insertWidget(1,operator_panel)
        mid=QWidget();mv=QVBoxLayout(mid);mv.setContentsMargins(0,0,0,0)
        trail_bar=QHBoxLayout()
        trail_bar.setContentsMargins(4,1,4,2)
        trail_bar.addWidget(label("Trajetória:"))
        self.trail_period=QComboBox()
        self.trail_period.addItems(["Última passagem","2 h","5 h","10 h","24 h","Personalizado"])
        self.trail_direction=QComboBox()
        self.trail_direction.addItems(["Futuro","Passado","Ambos"])
        self.trail_custom=QDoubleSpinBox()
        self.trail_custom.setRange(0.5,48);self.trail_custom.setDecimals(1)
        self.trail_custom.setSuffix(" h")
        self.trail_custom.setValue(3)
        trail_bar.addWidget(self.trail_period,2)
        trail_bar.addWidget(self.trail_direction,1)
        trail_bar.addWidget(self.trail_custom,1)
        self.map_edit_bar=QWidget()
        map_edit_layout=QVBoxLayout(self.map_edit_bar)
        map_edit_layout.setContentsMargins(4,2,4,2)
        self.map_edit_notice=label("MARCAÇÃO · Clique no mapa ou arraste o marcador · Coordenadas WGS-84")
        self.map_edit_notice.setStyleSheet("color:#f1dc89;font-weight:700")
        map_edit_layout.addWidget(self.map_edit_notice)
        location_row=QHBoxLayout()
        self.map_edit_lat=QLineEdit()
        self.map_edit_lon=QLineEdit()
        for box,placeholder in ((self.map_edit_lat,"Latitude ±90"),(self.map_edit_lon,"Longitude ±180")):
            box.setPlaceholderText(placeholder)
            box.setMinimumWidth(80)
            box.editingFinished.connect(self.update_station_map_numeric)
        location_row.addWidget(label("Latitude:"))
        location_row.addWidget(self.map_edit_lat,1)
        location_row.addWidget(label("Longitude:"))
        location_row.addWidget(self.map_edit_lon,1)
        map_edit_layout.addLayout(location_row)
        buttons_row=QHBoxLayout()
        self.map_edit_copy=QPushButton("Copiar")
        self.map_edit_copy.setToolTip("Copiar latitude, longitude decimais para a área de transferência")
        self.map_edit_copy.clicked.connect(self.copy_station_map)
        self.map_edit_restore=QPushButton("Restaurar anterior")
        self.map_edit_restore.clicked.connect(self.restore_station_map)
        self.map_edit_confirm=QPushButton("Confirmar posição")
        self.map_edit_confirm.setObjectName("primary")
        self.map_edit_confirm.clicked.connect(self.confirm_station_map)
        self.map_edit_cancel=QPushButton("Cancelar")
        self.map_edit_cancel.clicked.connect(self.cancel_station_map)
        for control in (self.map_edit_copy,self.map_edit_restore,self.map_edit_confirm,self.map_edit_cancel):
            buttons_row.addWidget(control)
        map_edit_layout.addLayout(buttons_row)
        self.map_edit_bar.setVisible(False)
        mv.addWidget(self.map_edit_bar)
        self.trail_period.currentTextChanged.connect(self.trail_changed)
        self.trail_direction.currentTextChanged.connect(self.trail_changed)
        self.trail_custom.valueChanged.connect(self.trail_changed)
        self.map=QWebEngineView()
        # A Chromium renderer crash may leave the GUI running, so record it.
        try:self.map.page().renderProcessTerminated.connect(self.web_renderer_terminated)
        except AttributeError:pass
        map_file=Path(__file__).with_name("map.html")
        self.map.setHtml(map_file.read_text(encoding="utf-8"),
                         QUrl.fromLocalFile(str(map_file.resolve())))
        # The built-in browser asks for geolocation only when the operator
        # explicitly clicks Solicitar coordenadas ao navegador.
        try:
            self.map.page().featurePermissionRequested.connect(self.grant_browser_geo)
        except (AttributeError,TypeError):
            self.log("Geolocalização QtWebEngine não suportada nesta edição")
        mv.addWidget(self.map,1)
        self.map_radio_label=label("CAT desconectado · RX — MHz · TX — MHz · Modo —")
        self.map_radio_label.setStyleSheet("font-size:13px;color:#f0c186;font-weight:700")
        mv.addWidget(self.map_radio_label)
        self.map_desc=label("Trajetória · cobertura · estação · mapa vetorial offline (Natural Earth)")
        self.map_desc.setStyleSheet('color:#8caec3')
        mv.addWidget(self.map_desc)
        # v1.7.0: o mapa é que cede largura quando a tabela de passagens precisa de espaço.
        for w in (self.map_radio_label,self.map_desc):
            w.setWordWrap(True);w.setMinimumWidth(0)
        mid.setMinimumWidth(220)
        splitter.addWidget(mid)
        right=QWidget();rv=QVBoxLayout(right);rv.setContentsMargins(2,0,2,0)
        stat,sv=group("TELEMETRIA ORBITAL")
        self.orbit_metrics={}
        for key,title in (("elevation","Elevação"),("azimuth","Azimute"),("range_km","Distância"),
                          ("radial_m_s","Velocidade radial"),("height_km","Altitude orbital")):
            r=QHBoxLayout();r.addWidget(label(title));v=label("—");v.setAlignment(Qt.AlignRight)
            v.setStyleSheet("font-size:14px;font-weight:600;color:#90e7df")
            v.setWordWrap(False)
            v.setMinimumHeight(max(28,v.fontMetrics().height()+10))
            self.orbit_metrics[key]=v;r.addWidget(v);sv.addLayout(r)
        self.visibility=label("Aguardando localização")
        self.visibility.setObjectName('metric')
        sv.addWidget(self.visibility)
        # v1.3.15: bloco "Próxima passagem do satélite selecionado" removido da
        # tela; os widgets continuam vivos (atualizados pelo timer) sem exibição.
        self._upcoming_group=upcoming
        self._telemetry_group=stat
        window_h=int(self.config.values.get("pass_window_hours",36) or 36)
        nextpass,np=group(f"PASSAGENS DO SATÉLITE SELECIONADO · {window_h} H")
        self.pass_group=nextpass
        nextpass.setMinimumWidth(0)
        pass_bar=QHBoxLayout();pass_bar.setContentsMargins(0,0,0,0)
        pass_bar.addWidget(label("Janela"))
        self.pass_window=QComboBox()
        for hours in (6,12,24,36,48,72,168):
            self.pass_window.addItem(f"{hours} h" if hours<168 else "7 dias",hours)
        idx=self.pass_window.findData(window_h)
        if idx<0:
            self.pass_window.addItem(f"{window_h} h",window_h);idx=self.pass_window.count()-1
        self.pass_window.setCurrentIndex(idx)
        self.pass_window.setToolTip("Quantas horas à frente a lista de passagens mostra (salvo nas configurações)")
        self.pass_window.currentIndexChanged.connect(self.change_pass_window)
        pass_bar.addWidget(self.pass_window)
        pass_bar.addStretch(1)
        self.pass_sort=QCheckBox("Ordenar por qualidade")
        self.pass_sort.setToolTip("Mostra primeiro as melhores passagens; desmarque para ordem cronológica")
        self.pass_sort.toggled.connect(lambda *_:self.render_pass_table())
        pass_bar.addWidget(self.pass_sort)
        np.addLayout(pass_bar)
        self.pass_table=QTableWidget(0,7)
        # Selected satellite appears in the combo; redundant table column removed.
        self.pass_table.setHorizontalHeaderLabels(["AOS","TCA","LOS","Duração","Máx °","Qualidade","Modos"])
        for col,tip in enumerate(("Início da passagem (horário local)","Máxima aproximação (horário local)",
                                  "Fim da passagem (horário local)")):
            self.pass_table.horizontalHeaderItem(col).setToolTip(tip)
        self.pass_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pass_table.customContextMenuRequested.connect(self.pass_context_menu)
        pass_header=self.pass_table.horizontalHeader()
        pass_header.setStretchLastSection(False)
        pass_header.setMinimumSectionSize(50)
        pass_header.setDefaultAlignment(Qt.AlignCenter)
        pass_header.setFixedHeight(max(46,self.pass_table.fontMetrics().height()*2+14))
        # v1.6.0: larguras pelo conteúdo e sobra repartida entre todas as colunas (fit_pass_columns).
        for col in range(7):
            pass_header.setSectionResizeMode(col,QHeaderView.Interactive)
        self.pass_table.viewport().installEventFilter(self)
        self.pass_table.setWordWrap(False)
        self.pass_table.setTextElideMode(Qt.ElideNone)
        self.pass_table.verticalHeader().setMinimumSectionSize(max(28,self.pass_table.fontMetrics().height()+10))
        self.pass_table.verticalHeader().setDefaultSectionSize(max(30,self.pass_table.fontMetrics().height()+12))
        self.pass_table.verticalHeader().hide()
        # Sem altura máxima: a tabela cresce no espaço livre abaixo da telemetria.
        self.pass_table.setMinimumHeight(self.pass_table.fontMetrics().height()*3+20)
        self.pass_table.setStyleSheet("QTableWidget::item { padding: 1px 2px; }")
        self.pass_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pass_table.cellDoubleClicked.connect(self.select_pass_satellite)
        self.pass_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        np.addWidget(self.pass_table)
        # v1.6.0: divisor arrastável entre Passagens e Telemetria (proporção lembrada; nunca sobrepõe).
        self.right_splitter=QSplitter(Qt.Vertical)
        self.right_splitter.setChildrenCollapsible(True)
        self.right_splitter.setHandleWidth(8)
        self.right_splitter.addWidget(nextpass)
        self.right_splitter.addWidget(stat)
        fm=self.pass_table.fontMetrics()
        nextpass.setMinimumHeight(fm.height()*4+80)   # cabeçalho + barra + linhas visíveis
        stat.setMinimumHeight(fm.height()*6+30)       # métricas com rolagem se faltar espaço
        saved=self.config.values.get("right_splitter_sizes")
        self.right_splitter.setSizes(saved if isinstance(saved,list) and len(saved)==2 else [3,2])
        self.right_splitter.splitterMoved.connect(
            lambda *_:self.config.values.__setitem__("right_splitter_sizes",self.right_splitter.sizes()))
        self.right_splitter.setToolTip("Arraste a divisória para ajustar Passagens × Telemetria; "
                                       "duplo clique na divisória recolhe/expande a telemetria")
        rv.insertWidget(0,self.right_splitter,1)
        catview,cv=group("RÁDIO / CAT  ·  KENWOOD TS-2000")
        self.cat_status=label("● Desconectado  ·  porta CAT indisponível")
        self.cat_status.setStyleSheet("color:#efc17b;font-size:12px")
        cv.addWidget(self.cat_status)
        catrow=QHBoxLayout()
        self.cat_rx=label("RX / DOWNLINK\n— MHz")
        self.cat_tx=label("TX / UPLINK\n— MHz")
        for widget,color in ((self.cat_rx,"#74e9c4"),(self.cat_tx,"#fa8e8e")):
            widget.setMinimumHeight(95)
            widget.setWordWrap(False)
            widget.setStyleSheet("font-size:15px;font-weight:800;color:"+color+";background:#10263b;border:1px solid #284e6e;padding:6px")
            catrow.addWidget(widget,1)
        cv.addLayout(catrow)
        self.cat_details=label("SAT: —  ·  MAIN: —  ·  Leitura CAT: —")
        self.cat_details.setStyleSheet("color:#a8cee0;font-size:12px")
        cv.addWidget(self.cat_details)
        self.cat_operating_detail=label("CTRL — · TRACE — · VFO/MEM — · TS-2000 sem telemetria CAT")
        self.cat_operating_detail.setStyleSheet("color:#bce4e1;font-size:12px")
        cv.addWidget(self.cat_operating_detail)
        meter=QHBoxLayout()
        self.smeter_main=QProgressBar();self.smeter_main.setRange(0,30);self.smeter_main.setTextVisible(True)
        self.smeter_sub=QProgressBar();self.smeter_sub.setRange(0,15);self.smeter_sub.setTextVisible(True)
        for w in (self.smeter_main,self.smeter_sub):
            w.setFormat("sem leitura");w.setValue(0);w.setMaximumHeight(19)
        meter.addWidget(label("S MAIN:"));meter.addWidget(self.smeter_main,1)
        meter.addWidget(label("S SUB:"));meter.addWidget(self.smeter_sub,1)
        cv.addLayout(meter)
        self.cat_telemetry=label("Potência ajustada: — W · Medidor: — · RX/TX: indisponível via CAT")
        self.cat_telemetry.setToolTip("Potência PC é um ajuste, não medição de potência RF. RM mostra medidor selecionado; PTT não é comandado.")
        cv.addWidget(self.cat_telemetry)
        splitter.addWidget(right)
        splitter.setSizes([910,640])
        op.addWidget(splitter,1)
        # Settings owns the COM port, baud, stop bits, SAT/TRACE and CAT telemetry.
        self.ports=QComboBox();self.ports.setEditable(True)
        self.refresh_ports=QPushButton("↻ Portas")
        self.refresh_ports.clicked.connect(self.update_ports)
        self.baud_combo=QComboBox();self.baud_combo.addItems(["4800","9600","19200","38400","57600"])
        self.stops_combo=QComboBox();self.stops_combo.addItems(["1","2"])
        self.connection=QPushButton("Conectar")
        self.connection.clicked.connect(self.toggle_connection)
        self.enable_sat=QPushButton("Ativar SAT / desativar TRACE")
        self.enable_sat.clicked.connect(self.enable_satellite)
        quick_cat=QHBoxLayout()
        self.radio_label=label("CAT desconectado · configure a porta em Configurações")
        self.radio_label.setStyleSheet("color:#ecc48f;font-size:12px")
        # v1.7.0: detalhes de CAT recolhidos por padrão (escolha salva); erros seguem no botão CAT do topo.
        self.cat_details_toggle=QPushButton("Detalhes CAT ▸")
        self.cat_details_toggle.setCheckable(True)
        self.cat_details_toggle.setToolTip("Mostrar/ocultar leitura FA/FB/FC/MD, orientação SAT, Auto CAT e diagnóstico")
        quick_cat.addWidget(self.cat_details_toggle)
        quick_cat.addWidget(self.radio_label,1)
        quick_cat.addWidget(self.connection)
        op.addLayout(quick_cat)
        self.build_rotor_bar(op)
        # v1.7.1 (mockup aprovado): faixa ROTOR entre o display e o mapa
        op.removeWidget(self.rotor_bar)
        op.insertWidget(op.indexOf(operator_panel)+1,self.rotor_bar)
        self.cat_details_box=QWidget()
        cdl=QVBoxLayout(self.cat_details_box);cdl.setContentsMargins(0,0,0,0);cdl.setSpacing(3)
        self.cat_live_label=label("RÁDIO REAL (CAT) · aguardando FA (RX SAT) / FB (TX SAT) / FC (SUB) / MD")
        self.cat_live_label.setStyleSheet("font-size:14px;font-weight:800;color:#d8f5c0")
        cdl.addWidget(self.cat_live_label)
        self.cat_sat_orientation=label("SAT: aguardando resposta SA do TS-2000")
        self.cat_sat_orientation.setStyleSheet("font-size:12px;font-weight:700;color:#d8c399")
        cdl.addWidget(self.cat_sat_orientation)
        self.cat_diagnose=QPushButton("Diagnosticar comunicação CAT · somente leitura")
        self.cat_diagnose.setToolTip("Consulta ID, SA, FA, FB, FC e MD; sem alterar SAT, VFO ou PTT")
        self.cat_diagnose.setEnabled(False)
        self.cat_diagnose.clicked.connect(self.diagnose_cat)
        cdl.addWidget(self.cat_diagnose)
        self.cat_tune_status=label("Auto CAT desligado · ative em Configurações para acompanhar a seleção")
        self.cat_tune_status.setStyleSheet("font-size:12px;font-weight:700;color:#b4d7e7")
        cdl.addWidget(self.cat_tune_status)
        self.cat_sync_status=label("CAT SYNC · previsto — · confirmado — · atraso —")
        self.cat_sync_status.setStyleSheet("font-size:11px;color:#a8d7e5")
        cdl.addWidget(self.cat_sync_status)
        op.addWidget(self.cat_details_box)
        shown=bool(self.config.values.get("cat_details_visible",False))
        self.cat_details_toggle.setChecked(shown)
        self.cat_details_box.setVisible(shown)
        self.cat_details_toggle.setText("Detalhes CAT ▾" if shown else "Detalhes CAT ▸")
        self.cat_details_toggle.toggled.connect(self.toggle_cat_details)
        # v1.6.0: com o painel SDR aberto em telas baixas a aba rola em vez de espremer/sobrepor blocos.
        operation.setMinimumHeight(640)
        operation_scroll=QScrollArea();operation_scroll.setWidgetResizable(True)
        operation_scroll.setFrameShape(QScrollArea.NoFrame)
        operation_scroll.setWidget(operation)
        self.operation_scroll=operation_scroll
        root.addTab(operation_scroll,"Operação")
        catalog_page=QWidget(); catalog_layout=QVBoxLayout(catalog_page)
        catalog_layout.addWidget(label("Satélites atuais no catálogo orbital CelesTrak. 'Canal publicado' não comprova serviço ativo nem autoriza TX. Clique duas vezes para selecionar."))
        self.catalog_search=QLineEdit()
        self.catalog_search.setPlaceholderText("Filtrar nome, NORAD, modo ou frequência…")
        self.catalog_search.textChanged.connect(self.refresh_satellite_table)
        catalog_layout.addWidget(self.catalog_search)
        self.catalog_category=QPushButton("Categorias · múltipla seleção")
        self.catalog_category_menu=QMenu(self.catalog_category)
        self.catalog_category_actions={}
        initial=set(self.config.values.get("catalog_category_filter",list(DEFAULT_GROUPS)))
        for name in DEFAULT_GROUPS:
            action=self.catalog_category_menu.addAction(name.upper())
            action.setCheckable(True)
            action.setChecked(name in initial)
            action.toggled.connect(self.change_catalog_categories)
            self.catalog_category_actions[name]=action
        self.catalog_category_menu.addSeparator()
        mark_all=self.catalog_category_menu.addAction("Marcar todas")
        mark_all.triggered.connect(lambda:self.set_catalog_categories(True))
        clear_all=self.catalog_category_menu.addAction("Limpar filtro")
        clear_all.triggered.connect(lambda:self.set_catalog_categories(False))
        self.catalog_category.setMenu(self.catalog_category_menu)
        catalog_layout.addWidget(self.catalog_category)
        catalog_actions=QHBoxLayout()
        self.scope_filtered=QCheckBox("Somente resultados filtrados")
        self.scope_filtered.setToolTip("Marcar/desmarcar somente os satélites exibidos; desmarcado: catálogo inteiro")
        self.mark_catalog_all=QPushButton("Marcar todos")
        self.mark_catalog_none=QPushButton("Desmarcar todos")
        self.mark_catalog_all.clicked.connect(lambda:self.bulk_catalog_selection(True))
        self.mark_catalog_none.clicked.connect(lambda:self.bulk_catalog_selection(False))
        # Frequency catalog update always covers ALL downloaded OMM/TLE NORAD IDs;
        # selection/favorites and search filters affect only visibility/monitoring.
        self.refresh_catalog_freq=QPushButton("Baixar/atualizar frequências · todos")
        self.refresh_catalog_freq.setToolTip(
            "Consulta frequências de TODOS os satélites do catálogo, inclusive não selecionados. "
            "Pode envolver milhares de consultas; há confirmação, progresso e cancelamento.")
        self.refresh_catalog_freq.clicked.connect(self.refresh_catalog_transmitters)
        self.stop_catalog_freq=QPushButton("Cancelar download")
        self.stop_catalog_freq.clicked.connect(self.cancel_catalog_transmitters)
        self.stop_catalog_freq.setEnabled(False)
        for widget in (self.scope_filtered,self.mark_catalog_all,self.mark_catalog_none,
                       self.refresh_catalog_freq,self.stop_catalog_freq):
            catalog_actions.addWidget(widget)
        catalog_layout.addLayout(catalog_actions)
        self.catalog_progress=label("SatNOGS: frequências em cache; atualização sob demanda.")
        catalog_layout.addWidget(self.catalog_progress)
        self.catalog_table=QTableWidget(0, 7)
        self.catalog_table.setObjectName("catalogSatellites")
        self.catalog_table.setStyleSheet(
            "QTableWidget#catalogSatellites::item:selected {"
            "background:#ffe36a;color:#111111;}"
        )
        self.catalog_table.setHorizontalHeaderLabels(
            ["Satélite", "NORAD", "Inclinação", "Período", "Modos", "Downlink MHz", "Situação"])
        self.catalog_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.catalog_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Favorito é marcado por cores persistentes, não pela seleção visual
        # temporária do Qt. Não deixar uma linha desmarcada amarela só
        # por continuar com o foco após o clique.
        self.catalog_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.catalog_table.setMouseTracking(True)
        self.catalog_table.itemEntered.connect(self.catalog_item_hovered)
        self.catalog_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.catalog_table.setToolTip(
            "Clique uma vez na linha para marcar/desmarcar o favorito (amarelo). "
            "Duplo clique abre a operação do satélite.")
        self.catalog_table.cellDoubleClicked.connect(self.select_catalog_satellite)
        self.catalog_table.cellClicked.connect(self.queue_catalog_single_click)
        self.catalog_click_timer=QTimer(self)
        self.catalog_click_timer.setSingleShot(True)
        self.catalog_click_timer.timeout.connect(self.commit_catalog_single_click)
        self.catalog_click_norad=None
        self.catalog_ignore_clicks_until=0.0
        catalog_layout.addWidget(self.catalog_table)
        self.catalog_note=label("Dados orbitais: CelesTrak OMM/TLE · Frequências e modos: SatNOGS · Não confundir catálogo com atividade confirmada.")
        catalog_layout.addWidget(self.catalog_note)
        root.addTab(catalog_page,"Satélites")
        config_page=QWidget();config_root=QVBoxLayout(config_page)
        config_root.setContentsMargins(0,0,0,0)
        # v1.7.0: Configurações em abas (Apresentação, Estação, Rádio, Rotor, Geral), cada uma com rolagem.
        self.settings_tabs=QTabWidget()
        config_root.addWidget(self.settings_tabs)
        self.settings_pages={}
        def settings_page(title):
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.NoFrame)
            frame=QWidget();lay=QVBoxLayout(frame);lay.setContentsMargins(20,16,20,16)
            scroll.setWidget(frame);self.settings_tabs.addTab(scroll,title)
            self.settings_pages[title]=scroll
            return lay
        look_l=settings_page("Aparência")
        station_l=settings_page("Estação")
        radio_l=settings_page("Rádio")
        rotor_l=settings_page("Rotores")
        cfg=settings_page("Geral")
        self.build_presentation_settings(look_l)
        station_group,sg=group("ESTAÇÃO TERRENA")
        grid=QGridLayout();grid.setColumnStretch(1,1)
        self.callsign=QLineEdit();self.lat=QLineEdit();self.lon=QLineEdit()
        self.altitude=QDoubleSpinBox();self.altitude.setRange(-500,9000);self.altitude.setDecimals(1)
        self.min_el=QDoubleSpinBox();self.min_el.setRange(0,90);self.min_el.setSuffix(" °")
        fields=[("Indicativo",self.callsign),("Latitude decimal (S negativa)",self.lat),
                ("Longitude decimal (O negativa)",self.lon),("Altitude estação (m)",self.altitude),
                ("Elevação mínima (°)",self.min_el)]
        for i,(txt,widget) in enumerate(fields):
            grid.addWidget(label(txt),i,0);grid.addWidget(widget,i,1)
        sg.addLayout(grid)
        locator_row=QHBoxLayout()
        locator_row.addWidget(label("Grid Locator / QTH (Maidenhead):"))
        self.grid_locator=QLineEdit()
        self.grid_locator.setPlaceholderText("Ex.: GH64ab")
        self.grid_locator.setToolTip(
            "Informe um Grid Locator de 2, 4, 6, 8 ou 10 caracteres. "
            "O centro da quadrícula preenche latitude/longitude; não é posição GPS exata.")
        self.grid_locator.returnPressed.connect(self.apply_grid_locator)
        self.grid_apply=QPushButton("Converter grid em coordenadas")
        self.grid_apply.clicked.connect(self.apply_grid_locator)
        locator_row.addWidget(self.grid_locator,1)
        locator_row.addWidget(self.grid_apply)
        sg.addLayout(locator_row)
        place=QHBoxLayout()
        self.get_position=QPushButton("Solicitar coordenadas ao navegador")
        self.get_position.setToolTip(
            "Solicita permissão explícita de localização ao navegador incorporado; "
            "pode estar indisponível dependendo do Windows, permissões e QtWebEngine.")
        self.get_position.clicked.connect(self.geolocate)
        self.save_station_btn=QPushButton("Salvar estação")
        self.save_station_btn.setObjectName("primary")
        self.save_station_btn.clicked.connect(self.save_station)
        self.station_map_button=QPushButton()  # obsolete map-picker methods stay inert
        self.station_map_button.hide()
        place.addWidget(self.get_position)
        place.addWidget(self.save_station_btn)
        sg.addLayout(place)
        self.location_status=label(
            "Escolha: latitude/longitude manual, Grid Locator, ou autorização de "
            "geolocalização do navegador. Revise e salve a estação.")
        self.location_status.setStyleSheet("color:#a6cede;font-size:11px")
        sg.addWidget(self.location_status)
        sg.addWidget(label(
            "Grid Locator preenche o centro da quadrícula, não uma posição exata. "
            "A localização do navegador depende de autorização e suporte do sistema; "
            "nada será salvo nem enviado ao rádio sem clicar em Salvar estação."))
        station_l.addWidget(station_group)
        profile_group,pg=group("PERFIL OPERACIONAL — MODOS E BANDAS")
        pg.addWidget(label("Modos selecionados determinam candidatos automáticos; as escolhas manuais permanecem salvas."))
        mode_row=QHBoxLayout();self.station_modes={}
        for name in ("FM","SSB","CW"):
            w=QCheckBox(name);self.station_modes[name]=w;mode_row.addWidget(w)
        pg.addLayout(mode_row)
        band_row=QHBoxLayout();self.station_bands={}
        for name in ("VHF","UHF","23cm"):
            w=QCheckBox(name);self.station_bands[name]=w;band_row.addWidget(w)
        pg.addLayout(band_row)
        profile_save=QPushButton("Salvar capacidades e recalcular")
        profile_save.clicked.connect(self.save_profile)
        pg.addWidget(profile_save);station_l.addWidget(profile_group)
        station_l.addStretch(1)

        radio_settings,rs=group("CONEXÃO CAT — RÁDIO")
        rr=QHBoxLayout()
        self.radio_brand=QComboBox();self.radio_brand.addItem("Kenwood")
        self.radio_model=QComboBox();self.radio_model.addItem("TS-2000")
        rr.addWidget(label("Fabricante"));rr.addWidget(self.radio_brand)
        rr.addWidget(label("Modelo"));rr.addWidget(self.radio_model)
        rr.addWidget(label("Porta COM"));rr.addWidget(self.ports,1)
        rr.addWidget(self.refresh_ports)
        rs.addLayout(rr)
        cat_options=QHBoxLayout()
        cat_options.addWidget(label("Baud"));cat_options.addWidget(self.baud_combo)
        cat_options.addWidget(label("Stop bits"));cat_options.addWidget(self.stops_combo)
        cat_options.addWidget(self.enable_sat,1)
        rs.addLayout(cat_options)
        self.auto_cat=QCheckBox("Auto CAT contínuo · acompanhar Doppler a cada segundo")
        self.auto_cat.setToolTip("Acompanha o Doppler acima e abaixo do horizonte. Reprograma FA/FB quando a previsão muda ou diverge da leitura CAT. Sem PTT; exige SAT ON e crossband.")
        self.auto_cat.toggled.connect(self.change_auto_cat)
        rs.addWidget(self.auto_cat)
        self.auto_cat_startup=QCheckBox("Conectar ao abrir e seguir satélite se Auto CAT estiver habilitado")
        self.auto_cat_startup.toggled.connect(self.change_startup_connect)
        rs.addWidget(self.auto_cat_startup)
        rs.addWidget(label("O programa pode conectar ao abrir, mas só rastreia após escolha explícita do satélite. Não habilita SAT nem transmite."))
        rs.addWidget(catview)
        connect_btn=QPushButton("Conectar pela porta selecionada")
        connect_btn.clicked.connect(self.connect_from_settings)
        rs.addWidget(connect_btn);radio_l.addWidget(radio_settings)
        track_settings,tsv=group("MAPA E TRAJETÓRIA")
        tsv.addLayout(trail_bar)
        tsv.addWidget(label("O mapa respeita as preferências salvas. Para marcar a estação, use Estação Terrena."))
        look_l.addWidget(track_settings)

        sel_group,ss=group("SATÉLITES VISÍVEIS NA PÁGINA PRINCIPAL")
        ss.addWidget(label("Auto sugere satélites por FM/SSB/CW e banda. A confirmação de funcionamento depende das fontes atuais."))
        self.tracked_search=QLineEdit()
        self.tracked_search.setPlaceholderText("Pesquisar por nome ou NORAD…")
        self.tracked_search.textChanged.connect(self.refresh_tracked_table)
        ss.addWidget(self.tracked_search)
        self.tracked_search_summary=label("Nenhum satélite carregado")
        ss.addWidget(self.tracked_search_summary)
        self.tracked_table=QTableWidget(0,3)
        self.tracked_table.setHorizontalHeaderLabels(["Selecionado","Satélite / NORAD","Compatibilidade"])
        self.tracked_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tracked_table.cellChanged.connect(self.satellite_checked)
        self.tracked_table.setMinimumHeight(200)
        ss.addWidget(self.tracked_table)
        action_row=QHBoxLayout()
        for title,func in (("Sugestões automáticas",self.restore_auto_selection),
                           ("Marcar tudo",lambda:self.bulk_select_satellites(True)),
                           ("Desmarcar tudo",lambda:self.bulk_select_satellites(False))):
            button=QPushButton(title);button.clicked.connect(func);action_row.addWidget(button)
        ss.addLayout(action_row);cfg.addWidget(sel_group)

        tle_group,tg=group("TLE / EFEMÉRIDES ORBITAIS")
        tg.addWidget(label("CelesTrak OMM prioritário; TLE de contingência. Intervalo mínimo de 2 h por conjunto."))
        self.tle_hours=QDoubleSpinBox();self.tle_hours.setRange(2,24)
        self.tle_hours.setDecimals(0);self.tle_hours.setSuffix(" horas")
        tg.addWidget(self.tle_hours)
        tg.addWidget(label("Categorias orbitais para download automático em lote:"))
        self.orbit_group_checks={}
        group_grid=QGridLayout()
        for index,group_name in enumerate(DEFAULT_GROUPS):
            check=QCheckBox(group_name.upper())
            self.orbit_group_checks[group_name]=check
            group_grid.addWidget(check,index//4,index%4)
        tg.addLayout(group_grid)
        save_groups=QPushButton("Salvar categorias / Atualizar órbitas")
        save_groups.clicked.connect(self.save_orbit_groups)
        tg.addWidget(save_groups)
        button=QPushButton("Salvar intervalo TLE")
        button.clicked.connect(self.save_tle_settings);tg.addWidget(button)
        cfg.addWidget(tle_group)
        alert_group,alert_layout=group("ALARMES DE PASSAGEM")
        self.aos_enabled=QCheckBox("Avisar antes da entrada do satélite selecionado (AOS)")
        self.aos_enabled.toggled.connect(lambda v:self.set_alarm_option("aos_alarm_enabled",v))
        self.aos_sound=QCheckBox("Alarme sonoro")
        self.aos_sound.toggled.connect(lambda v:self.set_alarm_option("aos_alarm_sound",v))
        alert_layout.addWidget(self.aos_enabled)
        alert_layout.addWidget(self.aos_sound)
        lead_row=QHBoxLayout()
        lead_row.addWidget(label("Antecedência do AOS"))
        self.aos_lead=QDoubleSpinBox()
        self.aos_lead.setRange(1,120)
        self.aos_lead.setDecimals(0)
        self.aos_lead.setSuffix(" s")
        self.aos_lead.setValue(int(self.config.values.get("aos_alarm_lead_seconds",10)))
        self.aos_lead.valueChanged.connect(self.save_aos_lead)
        lead_row.addWidget(self.aos_lead)
        alert_layout.addLayout(lead_row)
        alarm_test=QPushButton("Testar som")
        alarm_test.clicked.connect(lambda:self.play_aos_sound(critical=True))
        alert_layout.addWidget(alarm_test)
        cfg.addWidget(alert_group)
        web_group,wg=group("ACESSO PELA REDE · INTERFACE WEB")
        self.web_enabled=QCheckBox("Habilitar painel Web ao abrir o Sat Tool")
        self.web_enabled.setChecked(bool(self.config.values.get("web_enabled",False)))
        self.web_enabled.toggled.connect(self.change_web_settings)
        wg.addWidget(self.web_enabled)
        webrow=QHBoxLayout()
        self.web_lan=QCheckBox("Permitir outros dispositivos da rede local (LAN)")
        self.web_lan.setChecked(bool(self.config.values.get("web_allow_lan",False)))
        self.web_lan.toggled.connect(self.change_web_settings)
        webrow.addWidget(self.web_lan)
        webrow.addWidget(label("Porta TCP"))
        self.web_port=QDoubleSpinBox()
        self.web_port.setDecimals(0)
        self.web_port.setRange(1024,65535)
        self.web_port.setValue(int(self.config.values.get("web_port",8094)))
        self.web_port.valueChanged.connect(self.change_web_settings)
        webrow.addWidget(self.web_port)
        webrow.addWidget(label("Sessão expira em"))
        self.web_session_hours=QDoubleSpinBox()
        self.web_session_hours.setDecimals(0)
        self.web_session_hours.setRange(1,72)
        self.web_session_hours.setSuffix(" h")
        self.web_session_hours.setValue(int(self.config.values.get("web_session_hours",8)))
        self.web_session_hours.valueChanged.connect(self.change_web_settings)
        webrow.addWidget(self.web_session_hours)
        wg.addLayout(webrow)
        addr=QHBoxLayout()
        addr.addWidget(label("Endereços desta máquina"))
        self.web_addresses=QComboBox()
        self.web_addresses.setToolTip("Todos os IPv4 da rede local deste computador. Use o da mesma rede do outro aparelho.")
        addr.addWidget(self.web_addresses)
        web_copy=QPushButton("Copiar endereço")
        web_copy.clicked.connect(self.copy_web_url)
        addr.addWidget(web_copy)
        wg.addLayout(addr)
        controls=QHBoxLayout()
        web_launch=QPushButton("Abrir interface Web")
        web_launch.clicked.connect(self.open_web_dashboard)
        self.web_firewall_btn=QPushButton("Liberar no firewall do Windows")
        self.web_firewall_btn.setToolTip("Cria uma regra de entrada só para esta porta TCP, perfil Privado, só da rede local (pede confirmação do Windows).")
        self.web_firewall_btn.clicked.connect(self.web_request_firewall)
        self.web_firewall_btn.setEnabled(sys.platform=="win32")
        web_rotate=QPushButton("Renovar chave")
        web_rotate.setToolTip("Gera uma nova chave: links copiados antes e navegadores conectados deixam de ter acesso.")
        web_rotate.clicked.connect(self.web_rotate_key)
        for b in (web_launch,self.web_firewall_btn,web_rotate):
            controls.addWidget(b)
        wg.addLayout(controls)
        ctl=QHBoxLayout()
        self.web_controls=QCheckBox("Permitir controle pela rede (sem PTT)")
        self.web_controls.setToolTip("Pelo navegador: satélite, Auto CAT, A/B, RX ONLY, rastrear/estacionar/PARAR do rotor. "
                                     "PTT/TX nunca. Cada ação pede o PIN e fica registrada no log com o IP.")
        self.web_controls.setChecked(bool(self.config.values.get("web_controls",False)))
        self.web_controls.toggled.connect(self.change_web_settings)
        ctl.addWidget(self.web_controls)
        ctl.addWidget(label("PIN da estação"))
        self.web_pin=QLineEdit()
        self.web_pin.setEchoMode(QLineEdit.Password)
        self.web_pin.setMaxLength(12)
        self.web_pin.setPlaceholderText("definido" if self.config.values.get("web_pin_hash") else "4 a 12 dígitos")
        ctl.addWidget(self.web_pin)
        web_pin_save=QPushButton("Salvar PIN")
        web_pin_save.clicked.connect(self.web_save_pin)
        ctl.addWidget(web_pin_save)
        wg.addLayout(ctl)
        self.web_status=label("Interface Web desativada")
        self.web_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.web_status.setStyleSheet("color:#98d8e7;font-size:11px")
        wg.addWidget(self.web_status)
        self.web_diag=label("")
        self.web_diag.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.web_diag.setStyleSheet("color:#c5dbe7;font-size:11px")
        wg.addWidget(self.web_diag)
        wg.addWidget(label("Acesso local: 127.0.0.1. LAN: requer a chave do endereço copiado; só aparelhos da rede privada "
                           "(IP público é recusado). Sem controle pela rede, o navegador só consulta. "
                           "HTTP na LAN não tem criptografia; nunca encaminhe a porta à Internet."))
        cfg.addWidget(web_group)
        advanced,adv=group("DOPPLER E SEGURANÇA")
        self.interval=QDoubleSpinBox();self.interval.setRange(0.25,15);self.interval.setSingleStep(0.25);self.interval.setDecimals(2);self.interval.setSuffix(' segundos')
        self.threshold=QDoubleSpinBox();self.threshold.setRange(1,1000);self.threshold.setDecimals(0);self.threshold.setSuffix(' Hz')
        ag=QGridLayout();ag.addWidget(label("Intervalo de ajuste automático"),0,0);ag.addWidget(self.interval,0,1)
        ag.addWidget(label("Mínima variação para reprogramar CAT"),1,0);ag.addWidget(self.threshold,1,1)
        adv.addLayout(ag)
        adv.addWidget(label("Auto CAT acompanha o Doppler sempre, inclusive abaixo do horizonte, enquanto estiver habilitado e com CAT conectado. Requer SAT ON, efeméride recente e perfil crossband válido; nunca aciona PTT."))
        radio_l.addWidget(advanced)
        radio_l.addStretch(1)
        local_group,lg=group("IDIOMA E FORMATO DE FREQUÊNCIA")
        local_row=QHBoxLayout()
        local_row.addWidget(label("Idioma da aplicação"))
        self.language_combo=QComboBox()
        for code,native in LANGUAGES.items():
            self.language_combo.addItem(native,code)
        self.language_combo.currentIndexChanged.connect(self.change_language)
        local_row.addWidget(self.language_combo,1)
        local_row.addWidget(label("Formato de frequência"))
        self.freq_style_combo=QComboBox()
        for name,code in (("426.252.12 MHz (10 Hz)","radio10"),
                          ("426.252.120 MHz (1 Hz)","radio1"),
                          ("426,252120 MHz (decimal)","decimal")):
            self.freq_style_combo.addItem(name,code)
        self.freq_style_combo.currentIndexChanged.connect(self.change_frequency_style)
        local_row.addWidget(self.freq_style_combo,1)
        lg.addLayout(local_row)
        look_l.addWidget(local_group)
        look_l.addStretch(1)
        update_group, ug=group("ATUALIZAÇÕES DO APLICATIVO")
        self.update_minutes=QDoubleSpinBox();self.update_minutes.setRange(5,1440);self.update_minutes.setDecimals(0)
        self.update_minutes.setSuffix(' min')
        ug.addWidget(label("Verificar novas versões automaticamente a cada"))
        ug.addWidget(self.update_minutes)
        self.include_prerelease=QCheckBox("Incluir versões de testes / pré-lançamentos")
        ug.addWidget(self.include_prerelease)
        self.auto_update_check=QCheckBox("Atualizar automaticamente, sem perguntar (recomendado)")
        self.auto_update_check.setChecked(bool(self.config.values.get("auto_update",True)))
        self.auto_update_check.setToolTip("Ao detectar versão nova em www.pt2vhf.com: baixa, confere SHA-256 e instala. "
                                          "Adia durante passagem com CAT/SDR/rotor ativos ou transmissão.")
        ug.addWidget(self.auto_update_check)
        ug.addWidget(label("Ligado: a versão nova é baixada, verificada (SHA-256) e instalada sozinha, nunca no meio de uma "
                           "passagem em operação, transmissão, gravação ou rastreamento do rotor. Desligado: aparece o aviso "
                           "'Atualizar agora / Depois' e o botão de versão no topo. Linux/macOS: abre a página de download. "
                           "Configurações preservadas."))
        self.save_update_btn=QPushButton("Salvar preferências de atualização")
        self.save_update_btn.clicked.connect(self.save_update_preferences)
        ug.addWidget(self.save_update_btn)
        cfg.addWidget(update_group)
        extra_controls,extras=group("EDITOR AVANÇADO DE SATÉLITE E TRANSPONDER")
        extras.addWidget(left)
        cfg.addWidget(extra_controls)
        cfg.addStretch(1)
        self.build_rotor_settings(rotor_l)
        # v1.7.1: menus e campos do tamanho do conteúdo, não esticados na largura toda
        from .form_sizing import fit_settings
        fit_settings(self,self.settings_tabs)
        root.addTab(config_page,"Configurações")
        logs=QWidget();ll=QVBoxLayout(logs)
        self.log_view=QPlainTextEdit();self.log_view.setReadOnly(True)
        self.log_view.document().setMaximumBlockCount(4000)
        self.log_view.setToolTip("Últimas 4.000 linhas na tela; o histórico CAT persistido pode ser exportado localmente em ZIP.")
        ll.addWidget(self.log_view)
        log_actions=QHBoxLayout()
        clear=QPushButton("Limpar logs da tela");clear.clicked.connect(self.log_view.clear)
        self.export_logs=QPushButton("Baixar log completo (ZIP)")
        self.export_logs.setToolTip("Salva CAT RX/TX, eventos SAT e arquivos de diagnóstico localmente")
        self.export_logs.clicked.connect(self.save_complete_logs)
        log_actions.addWidget(clear)
        log_actions.addWidget(self.export_logs)
        log_actions.addStretch(1)
        ll.addLayout(log_actions)
        root.addTab(logs,"LOGs / CAT")
        about=QWidget();about_layout=QVBoxLayout(about)
        about_layout.addWidget(label(f"PT2VHF Sat Tool v{__version__} — Controle CAT do TS-2000"))
        about_layout.addWidget(label("Distribuição: Windows 10/11 x64 (Setup e Portátil), Linux x64 e macOS Apple Silicon. Win7 pausado."))
        about_layout.addWidget(label("Elementos orbitais: CelesTrak OMM/TLE. Transponders e modos: SatNOGS (créditos e licenças nos provedores)."))
        about_layout.addWidget(label("Site oficial e downloads: https://www.pt2vhf.com/sat · Licença MIT"))
        btn=QPushButton("Verificar versão");btn.clicked.connect(lambda:self.request_update(manual=True))
        about_layout.addWidget(btn);about_layout.addStretch()
        root.addTab(about,"Sobre")
        self.statusBar().showMessage("PT2VHF Sat Tool | Mapa offline Natural Earth | CAT passivo · PTT não controlado | CelesTrak OMM / SatNOGS")

    def init_sdr_dock(self):
        """v1.4.0: painel acoplável SDR · Equipamentos RX/TX · Telemetria."""
        from .sdr_panel import make_dock
        self.sdr_dock,self.sdr_panel=make_dock(self)
        self.addDockWidget(Qt.BottomDockWidgetArea,self.sdr_dock)
        self.sdr_dock.setVisible(bool(self.config.values.get("sdr_dock_visible",False)))
        # v1.6.0: altura menor por padrão e lembrada; flutuante também lembrado.
        self.resizeDocks([self.sdr_dock],[int(self.config.values.get("sdr_dock_height",200) or 200)],Qt.Vertical)
        self.sdr_dock.setFloating(bool(self.config.values.get("sdr_dock_floating",False)))
        self.sdr_dock.topLevelChanged.connect(lambda f:self.config.values.__setitem__("sdr_dock_floating",bool(f)))
        self.sdr_dock.visibilityChanged.connect(self._remember_sdr_dock)
        self.sdr_toggle.clicked.connect(self.toggle_sdr_dock)

    def toggle_sdr_dock(self):
        """Botão SDR: a escolha do operador vale até ele mudar (v1.7.1: o painel não reabre sozinho)."""
        show=not self.sdr_dock.isVisible()
        self.config.values["sdr_dock_user_hidden"]=not show
        self.sdr_dock.setVisible(show)
        self.config.save()

    def _remember_sdr_dock(self,visible):
        if self.isVisible() and not self.isMinimized():
            self.config.values["sdr_dock_visible"]=bool(visible)
            # fechado pelo X do painel ou pelo botão: não reabrir automaticamente; aberto: volta ao normal
            self.config.values["sdr_dock_user_hidden"]=not visible

    def doppler_snapshot(self):
        """Estado Doppler atual para SDR/equipamentos (chamado a 4 Hz; nunca escreve CAT)."""
        if not self.sat:
            return None
        ul,dl=self.nominal_hz()
        from .operations import frequency_prediction
        from .telemetry import pipeline_for
        pos=position(self.sat,self.saved_station(),ts=self.ts)
        calc=frequency_prediction({"downlink_hz":dl,"uplink_hz":ul},pos["radial_m_s"])
        i=self.mode_combo.currentData()
        opt=self.options[i] if isinstance(i,int) and 0<=i<len(self.options) else {"mode":self.rx_mode.currentText()}
        band=None
        if opt.get("downlink_high",0)>opt.get("downlink",0):
            band=(opt["downlink"]+calc["rx_offset_hz"],opt["downlink_high"]+calc["rx_offset_hz"])
        return {"norad":str(self.sat_combo.currentData() or ""),"name":self.sat.name,
                "rx_hz":int(calc["rx_hz"]),"tx_hz":int(calc["tx_hz"]) if calc["tx_hz"] else None,
                "rx_offset_hz":int(calc["rx_offset_hz"]),"rx_mode":self.rx_mode.currentText(),
                "tx_mode":self.tx_mode.currentText(),"visible":bool(pos["visible"]),
                "pipeline":pipeline_for(opt),"band":band}

    def retune_nominal_downlink(self,delta_hz):
        """Clique no waterfall: move a frequência nominal; em lineares o uplink acompanha."""
        try:
            dl=parse_mhz_input(self.down_edit.text())
        except ValueError:
            return
        self.down_edit.setText(f"{(dl+int(delta_hz))/1e6:.6f}")
        self.pair_linear()
        self.preview_doppler()
        self.log(f"Sintonia pelo waterfall: {delta_hz:+d} Hz")

    def load_fields(self):
        c=self.config.values
        self.callsign.setText(str(c['callsign']))
        self.lat.setText(str(c['lat']))
        self.lon.setText(str(c['lon']))
        self.altitude.setValue(float(c['altitude_m']))
        self.min_el.setValue(float(c['min_elevation']))
        self.baud_combo.setCurrentText(str(c['baud']))
        for name,w in self.station_modes.items():
            w.setChecked(name in c.get("radio_modes",["FM","SSB","CW"]))
        for name,w in self.station_bands.items():
            w.setChecked(name in c.get("radio_bands",["VHF","UHF"]))
        self.tle_hours.setValue(float(c.get("tle_update_hours",4)))
        enabled_groups=set(c.get("orbit_groups",DEFAULT_GROUPS))
        for group_name,check in self.orbit_group_checks.items():
            check.setChecked(group_name in enabled_groups)
        self.aos_enabled.setChecked(bool(c.get("aos_alarm_enabled",True)))
        self.aos_sound.setChecked(bool(c.get("aos_alarm_sound",True)))
        self.auto_cat.blockSignals(True)
        self.auto_cat.setChecked(bool(c.get("cat_auto_select",True)))
        self.auto_cat.blockSignals(False)
        self.auto_cat_startup.blockSignals(True)
        self.auto_cat_startup.setChecked(bool(c.get("cat_auto_connect_startup",True)))
        self.auto_cat_startup.blockSignals(False)
        self.cat_tune_status.setText("Auto CAT habilitado · conecte rádio com SAT ON" if self.auto_cat.isChecked() else "Auto CAT desligado · ative em Configurações para sintonizar ao selecionar")
        self.stops_combo.setCurrentText(str(c['stopbits']))
        self.interval.setValue(float(c['update_interval_s']))
        self.threshold.setValue(float(c['tune_threshold_hz']))
        self.update_minutes.setValue(float(c.get('version_check_minutes',15)))
        self.include_prerelease.setChecked(bool(c.get('include_prereleases', True)))
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(max(0,self.language_combo.findData(self.ui_language())))
        self.language_combo.blockSignals(False)
        self.freq_style_combo.blockSignals(True)
        self.freq_style_combo.setCurrentIndex(max(0,self.freq_style_combo.findData(c.get("frequency_style","radio10"))))
        self.freq_style_combo.blockSignals(False)
        self.trail_period.blockSignals(True)
        self.trail_direction.blockSignals(True)
        period=str(c.get("trail_period","2 h"))
        self.trail_period.setCurrentText(period if period in ["Última passagem","2 h","5 h","10 h","24 h","Personalizado"] else "2 h")
        self.trail_direction.setCurrentText(str(c.get("trail_direction","Futuro")))
        self.trail_custom.blockSignals(True)
        self.trail_custom.setValue(float(c.get("trail_custom_hours",3)))
        self.trail_custom.blockSignals(False)
        self.trail_custom.setVisible(self.trail_period.currentText()=="Personalizado")
        self.trail_period.blockSignals(False)
        self.trail_direction.blockSignals(False)
        # Always require an explicit enable on each launch to avoid surprise CAT writes.
        self.doppler_checkbox.setChecked(False)

    def ui_language(self):
        """Idioma da interface: o salvo, ou o do sistema quando suportado (padrão pt-BR)."""
        return resolve_language(self.config.values.get("language",""))

    def capture_static_language(self):
        """Snapshot only creation-time UI strings; do not translate live CAT telemetry.
        v1.7.1: inclui tooltips, textos de exemplo, sub-abas das Configurações e itens de menus com dados."""
        self._language_texts=[]
        for widget in self.findChildren(QWidget):
            if isinstance(widget,QGroupBox):
                original=widget.title()
                if original:self._language_texts.append((widget,"group",original))
            elif isinstance(widget,(QPushButton,QCheckBox,QLabel)):
                original=widget.text()
                if original:self._language_texts.append((widget,"text",original))
            if widget.toolTip() and "<" not in widget.toolTip():
                self._language_texts.append((widget,"tooltip",widget.toolTip()))
            if isinstance(widget,QLineEdit) and widget.placeholderText():
                self._language_texts.append((widget,"placeholder",widget.placeholderText()))
            if isinstance(widget,QComboBox) and not widget.isEditable() and widget is not getattr(self,"language_combo",None):
                # só menus cujo código vem do itemData: traduzir o texto não muda o comportamento
                if widget.count() and all(widget.itemData(i) is not None for i in range(widget.count())):
                    self._language_texts.append((widget,"items",[widget.itemText(i) for i in range(widget.count())]))
        self._language_tabs=[(tabs,[tabs.tabText(i) for i in range(tabs.count())]) for tabs in self.findChildren(QTabWidget)]
        self._language_tables=[]
        for widget in self.findChildren(QTableWidget):
            labels=[]
            for i in range(widget.columnCount()):
                item=widget.horizontalHeaderItem(i)
                labels.append(item.text() if item is not None else "")
            self._language_tables.append((widget,labels))

    def apply_language(self):
        locale=self.ui_language()
        old=getattr(self,"_language_active","pt-BR")
        for widget,kind,original in self._language_texts:
            if kind=="items":
                for i,text in enumerate(original):
                    if i<widget.count():widget.setItemText(i,translated(text,locale))
                continue
            names={"group":("title","setTitle"),"text":("text","setText"),"tooltip":("toolTip","setToolTip"),
                   "placeholder":("placeholderText","setPlaceholderText")}[kind]
            getter,setter=getattr(widget,names[0]),getattr(widget,names[1])
            old_value=translated(original,old)
            current=getter()
            if current in (old_value,original):  # não sobrescreve textos que mudaram em tempo de execução
                setter(translated(original,locale))
        for tabs,originals in self._language_tabs:
            for i,original in enumerate(originals):
                if i<tabs.count():tabs.setTabText(i,translated(original,locale))
        for widget,originals in self._language_tables:
            for i,original in enumerate(originals):
                item=widget.horizontalHeaderItem(i)
                if item:item.setText(translated(original,locale))
        if hasattr(self,"language_menu_button"):
            self.language_menu_button.setIcon(flag_icon(locale))
            self.language_menu_button.setText(LANGUAGES[locale])
            self.language_menu_button.setToolTip(translated("Idioma",locale))
            for action in self.language_actions:
                action.setChecked(action.data()==locale)
        if hasattr(self,"language_combo"):
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(max(0,self.language_combo.findData(locale)))
            self.language_combo.blockSignals(False)
        self._language_active=locale

    def build_language_menu(self,header):
        """v1.7.1: seletor de idioma no topo (bandeira + nome nativo), sincronizado com Configurações."""
        from .qt_compat import QMenu
        try:
            from PySide6.QtWidgets import QToolButton
        except ImportError:  # pragma: no cover
            from PySide2.QtWidgets import QToolButton
        self.language_menu_button=QToolButton()
        self.language_menu_button.setPopupMode(QToolButton.InstantPopup)
        self.language_menu_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.language_menu_button.setStyleSheet("font-size:12px;font-weight:700;padding:3px 6px")
        menu=QMenu(self.language_menu_button)
        self.language_actions=[]
        for code,native in LANGUAGES.items():
            action=menu.addAction(flag_icon(code),native)
            action.setData(code);action.setCheckable(True)
            action.triggered.connect(lambda _=False,c=code:self.set_language(c))
            self.language_actions.append(action)
        self.language_menu_button.setMenu(menu)
        header.addWidget(self.language_menu_button)

    def set_language(self,locale):
        """Troca o idioma na hora, sem reiniciar, e salva em settings.json."""
        if locale not in LANGUAGES:return
        self.config.values["language"]=locale
        self.config.save()
        self.apply_language()
        self.log(f"Idioma da interface: {LANGUAGES[locale]}")

    def change_language(self,*args):
        self.set_language(self.language_combo.currentData())

    def change_frequency_style(self,*args):
        style=self.freq_style_combo.currentData()
        if style not in ("radio10","radio1","decimal"):return
        self.config.values["frequency_style"]=style
        self.config.save()
        self.preview_doppler()
        if self.radio.connected and self.radio.state.downlink is not None:
            self.render_radio_state(self.radio.state)

    def save_update_preferences(self):
        self.config.values['version_check_minutes']=int(self.update_minutes.value())
        self.config.values['include_prereleases']=self.include_prerelease.isChecked()
        self.config.values['auto_update']=self.auto_update_check.isChecked()
        self.config.save()
        self.log('Preferências de atualizações salvas')
        # Saving preferences only refreshes the quiet top-menu indicator.
        # It must never install a release without clicking the version button.
        self.manual_update_requested = False
        self.check_for_updates(force=True)

    def check_for_updates(self, force=False):
        import time
        interval=int(self.config.values.get('version_check_minutes',15))*60
        now=time.monotonic()
        if not force and self.update_last_checked and now-self.update_last_checked<interval:
            return
        if not self.update_distribution:
            self.version_btn.setText('Desenvolvimento')
            return
        self.update_last_checked=now
        variant,kind=self.update_distribution
        self.version_btn.setText('Verificando…')
        self.background('update-check', lambda: check_for_update(
            __version__,variant,kind,
            include_prereleases=bool(self.config.values.get('include_prereleases',True))))

    def request_update(self,manual=False,silent=False):
        if not self.update_distribution:
            QMessageBox.information(self,'Atualizações','O atualizador funciona apenas nos executáveis Windows instalável ou portátil. Compile ou instale uma versão para testar.')
            return
        if self.available_update is None:
            # Clicking the version button first checks the release. If a newer
            # build exists, launch the download immediately after that check.
            self.manual_update_requested = bool(manual)
            self.check_for_updates(force=True)
            return
        if 'update-download' in self.pending_jobs:
            return
        u=self.available_update
        if self.update_distribution[1]=='Manual':
            # Linux/macOS: sem instalação automática; abre a página oficial de downloads.
            import webbrowser
            webbrowser.open(u.html_url or 'https://www.pt2vhf.com/sat')
            self.log(f'Versão {u.version} disponível em www.pt2vhf.com/sat')
            return
        # The version button click is authorization. No separate confirmation
        # or changelog popup; keep progress and SHA256 integrity checks.
        # v1.7.0: no OTA automático (opção ligada por padrão) o download é discreto: progresso no botão do topo.
        if not silent:
            self.update_dialog=QProgressDialog('Baixando e verificando atualização…','',0,100,self)
            self.update_dialog.setCancelButton(None)
            self.update_dialog.setAutoClose(False)
            self.update_dialog.setMinimumDuration(0)
            self.update_dialog.setValue(0)
        self._auto_update_running=bool(silent)
        self.version_btn.setText('Atualização em andamento…')
        self.background('update-download', lambda: download_update(u, lambda n,total:self.events.progress.emit(n,total)))

    AUTO_UPDATE_RETRY_SECONDS = 6 * 3600

    def operation_busy(self):
        """Motivo para adiar o OTA automático, ou '' se o programa está livre (v1.7.0)."""
        try:
            if bool((self.radio.state.extras or {}).get("if",{}).get("tx")):
                return "rádio transmitindo"
            event=getattr(self,"next_candidate",None)
            in_pass=bool(event and event.get("in_progress"))
            if in_pass and self.radio.connected and self.cat_tracking_armed:
                return "passagem em curso com Auto CAT"
            if getattr(self,"rotor_tracking",False):
                return "rotor rastreando"
            rec=getattr(getattr(self,"sdr_panel",None),"receiver",None)
            if rec is not None and rec.status.running and (in_pass or rec.status.recording):
                return "SDR recebendo/gravando"
            if QApplication.activeModalWidget() is not None:
                return "janela de diálogo aberta"
        except Exception:
            return ""
        return ""

    def try_auto_update(self,data=None):
        """OTA automático: baixa, confere SHA-256 e instala sem perguntar, fora de operação (v1.7.0)."""
        data=data or self.available_update
        if data is None or 'update-download' in self.pending_jobs or not self.config.values.get('auto_update',True):
            return
        failed=getattr(self,'_auto_update_failed',None) or {}
        if failed.get('version')==data.version and time.time()-float(failed.get('at') or 0)<self.AUTO_UPDATE_RETRY_SECONDS:
            return
        busy=self.operation_busy()
        if busy:
            self.version_btn.setText(f'Nova versão {data.version} · instala ao ficar livre')
            self.version_btn.setToolTip('Atualização automática adiada: '+busy)
            if not getattr(self,'_auto_update_timer_armed',False):
                self._auto_update_timer_armed=True
                def retry():
                    self._auto_update_timer_armed=False
                    self.try_auto_update()
                QTimer.singleShot(60_000,retry)
            return
        self.log(f'Atualização automática para {data.version} iniciada (www.pt2vhf.com)')
        self.show_tray_message('PT2VHF Sat Tool',f'Atualizando para a versão {data.version}…')
        self.request_update(manual=True,silent=True)

    def show_tray_message(self,title,text):
        try:
            tray=getattr(self,'_tray',None)
            if tray is None:
                try:
                    from PySide6.QtWidgets import QSystemTrayIcon
                except ImportError:
                    from PySide2.QtWidgets import QSystemTrayIcon
                if not QSystemTrayIcon.isSystemTrayAvailable():
                    return
                self._tray=tray=QSystemTrayIcon(self.windowIcon(),self);tray.show()
            if tray is not None:
                tray.showMessage(title,text)
        except Exception:
            pass

    UPDATE_PROMPT_SNOOZE_SECONDS = 24 * 3600

    def maybe_prompt_update(self, data):
        """Pergunta se deseja atualizar ao detectar versão nova (v1.3.13; manifesto do site desde v1.3.14).

        Só "Atualizar agora" inicia o download, como o clique no botão de
        versão; "Depois" adia a mesma versão por 24 h. Não abre sobre outro
        diálogo nem repete a pergunta da mesma versão na sessão.
        """
        import time
        if data is None or 'update-download' in self.pending_jobs:
            return
        if self._update_prompted_version == data.version:
            return
        snooze = self.config.values.get('update_prompt_snooze') or {}
        if (snooze.get('version') == data.version
                and time.time() - float(snooze.get('at') or 0) < self.UPDATE_PROMPT_SNOOZE_SECONDS):
            return
        if QApplication.activeModalWidget() is not None:
            QTimer.singleShot(5000, lambda: self.maybe_prompt_update(self.available_update))
            return
        self._update_prompted_version = data.version
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle('Nova versão disponível')
        box.setText(f'PT2VHF Sat Tool {data.version} está disponível (instalada: {__version__}).\n\n'
                    'Deseja atualizar agora?')
        update_now = box.addButton('Atualizar agora', QMessageBox.AcceptRole)
        box.addButton('Depois', QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is update_now:
            self.request_update(manual=True)
        else:
            self.config.values['update_prompt_snooze'] = {'version': data.version, 'at': time.time()}
            self.config.save()
            self.log(f'Atualização {data.version} adiada por 24 h')

    def download_progress(self, current, total):
        if getattr(self,'_auto_update_running',False) and total:
            self.version_btn.setText(f'Atualizando para {getattr(self.available_update,"version","")}… {min(99,int(current*100/total))}%')
        if self.update_dialog:
            if total:
                self.update_dialog.setMaximum(100)
                self.update_dialog.setValue(min(99,int(current*100/total)))
            else:
                self.update_dialog.setMaximum(0)

    def update_ready(self,package):
        if self.update_dialog:
            self.update_dialog.setValue(100)
            self.update_dialog.close()
            self.update_dialog=None
        try:
            base=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
            script=base/'scripts'/'apply-update.ps1'
            version=getattr(self.available_update,'version','')
            launch_staged_update(Path(package), portable=self.update_distribution[1]=='Portable', script_path=script,
                                 version=version)
            self.doppler_checkbox.setChecked(False)
            self.cat_tracking_armed=False
            self.radio.disconnect()
            self.log('Atualização verificada; fechando para atualização externa')
            self._quitting_for_update=True
            self.close()
            # v1.6.0: encerra o processo inteiro (inclusive o mapa/QtWebEngine) para liberar os arquivos.
            QApplication.quit()
            QTimer.singleShot(8000,lambda:os._exit(0))
        except Exception as exc:
            self.version_btn.setText('Falha ao instalar · tentar novamente')
            QMessageBox.critical(self,'Atualização não aplicada',str(exc))

    def show_last_update_result(self):
        from .updater import read_update_result
        result=read_update_result()
        if not result:
            return
        status,version,detail=result
        self.log(f"Resultado da última atualização: {status} {version} {detail}")
        if status=="ok":
            QMessageBox.information(self,"Atualização concluída",f"PT2VHF Sat Tool atualizado para a versão {version or __version__}.")
        else:
            from .updater import update_failure_message
            box=QMessageBox(QMessageBox.Warning,"Atualização não concluída",update_failure_message(detail),parent=self)
            box.setTextFormat(Qt.RichText)
            box.setTextInteractionFlags(Qt.TextBrowserInteraction)
            box.exec() if hasattr(box,"exec") else box.exec_()

    def station(self):
        if not self.lat.text().strip() or not self.lon.text().strip():
            raise ValueError("Cadastre latitude e longitude na aba Configurações")
        st=Station(self.callsign.text().strip().upper(),float(self.lat.text().replace(',','.')),
                   float(self.lon.text().replace(',','.')),
                   self.altitude.value(),self.min_el.value())
        st.validate()
        return st

    def saved_station(self):
        """Only the confirmed station coordinates may drive orbit/Doppler/CAT."""
        c=self.config.values
        if c.get("lat") in ("",None) or c.get("lon") in ("",None):
            raise ValueError("Cadastre e salve latitude/longitude da estação")
        st=Station(str(c.get("callsign","")).strip().upper(),
                   float(c["lat"]),float(c["lon"]),
                   float(c.get("altitude_m",0)),float(c.get("min_elevation",10)))
        st.validate()
        return st

    def stored_map_position(self):
        try:
            st=self.saved_station()
            return {"lat":st.lat,"lon":st.lon}
        except (ValueError,TypeError):
            return None

    def begin_station_map(self):
        """No change to saved station until explicit confirmation AND Save station."""
        if self.map_pick_active:
            self.tabs.setCurrentIndex(0)
            return
        self.map_pick_active=True
        self.map_pick_position=self.stored_map_position()
        self.map_edit_bar.setVisible(True)
        self.station_map_button.setEnabled(False)
        self.tabs.setCurrentIndex(0)
        self.show_station_map_preview(self.map_pick_position)
        payload=json.dumps(self.map_pick_position,ensure_ascii=False)
        self.map.page().runJavaScript("window.beginLocationPick && window.beginLocationPick("+payload+")")
        if self.map_pick_position is not None:
            self.map.page().runJavaScript(
                "window.focusLocation && window.focusLocation("+
                str(self.map_pick_position["lat"])+","+
                str(self.map_pick_position["lon"])+")")
        self.log("Modo de marcação manual no mapa ativo; CAT e dados salvos permanecem inalterados")

    def show_station_map_preview(self,point):
        if point is None:
            self.map_edit_lat.clear();self.map_edit_lon.clear()
            self.map_edit_notice.setText("Clique no mapa para marcar a antena · coordenadas WGS-84")
            return
        lat,lon=valid_coordinates(point["lat"],point["lon"])
        self.map_edit_lat.setText(f"{lat:.7f}")
        self.map_edit_lon.setText(f"{lon:.7f}")
        self.map_edit_notice.setText("PRÉVIA NÃO SALVA · arraste o marcador ou ajuste números")

    def poll_station_map(self):
        if not self.map_pick_active:return
        self.map.page().runJavaScript(
            "window.takeLocationPick && window.takeLocationPick()",
            self.receive_station_map_pick)

    def receive_station_map_pick(self,pick):
        if not self.map_pick_active or pick is None:return
        try:
            lat,lon=sanitize_map_pick(pick)
            self.map_pick_position={"lat":lat,"lon":lon}
            self.show_station_map_preview(self.map_pick_position)
        except (ValueError,TypeError) as exc:
            self.log(f"Marcação no mapa ignorada: {exc}")

    def update_station_map_numeric(self):
        if not self.map_pick_active:return
        try:
            lat,lon=parse_coordinate_fields(self.map_edit_lat.text(),self.map_edit_lon.text())
            self.map_pick_position={"lat":lat,"lon":lon}
            self.map_edit_notice.setText("PRÉVIA NÃO SALVA · valores ajustados manualmente")
            self.map.page().runJavaScript(
                f"window.setLocationPickPreview && window.setLocationPickPreview({lat},{lon})")
        except ValueError as exc:
            self.map_edit_notice.setText(str(exc)+" · ajuste os valores antes de confirmar")

    def copy_station_map(self):
        if not self.map_pick_active:return
        try:
            lat,lon=parse_coordinate_fields(self.map_edit_lat.text(),self.map_edit_lon.text())
            QApplication.clipboard().setText(f"{lat:.7f}, {lon:.7f}")
            self.map_edit_notice.setText("Coordenadas copiadas · ainda não salvas")
        except ValueError as exc:
            self.map_edit_notice.setText(str(exc))

    def restore_station_map(self):
        if not self.map_pick_active:return
        original=self.stored_map_position()
        self.map_pick_position=original
        self.show_station_map_preview(original)
        self.map.page().runJavaScript(
            "window.beginLocationPick && window.beginLocationPick("+
            json.dumps(original)+")")
        self.log("Posição de edição restaurada à última estação salva")

    def cancel_station_map(self):
        self.map_pick_active=False
        self.map_pick_position=None
        self.map_edit_bar.setVisible(False)
        self.station_map_button.setEnabled(True)
        self.map.page().runJavaScript("window.finishLocationPick && window.finishLocationPick()")

    def confirm_station_map(self):
        if not self.map_pick_active:return
        try:
            lat,lon=parse_coordinate_fields(self.map_edit_lat.text(),self.map_edit_lon.text())
        except ValueError as exc:
            QMessageBox.warning(self,"Posição inválida",str(exc));return
        before=self.stored_map_position()
        previous=(f"{before['lat']:.7f}, {before['lon']:.7f}" if before else "Nenhuma estação cadastrada")
        summary=(f"Posição anterior: {previous}\\n"
                 f"Posição proposta (WGS-84): {lat:.7f}, {lon:.7f}\\n"
                 f"Origem: marcador no mapa offline\\n"
                 "A altitude atual será mantida.\\n\\n"
                 "Preencher os campos para revisão? A estação, as órbitas e o rádio"
                 " só serão alterados após clicar em Salvar estação.")
        if QMessageBox.question(self,"Confirmar marcador",summary,
                                QMessageBox.Yes | QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
            return
        self.lat.setText(f"{lat:.7f}")
        self.lon.setText(f"{lon:.7f}")
        self.location_status.setText(
            "Posição marcada manualmente no mapa; campos preenchidos, ainda NÃO salvos. "
            "Confira a altitude e clique em Salvar estação.")
        self.log("Coordenadas do mapa preenchidas para revisão; estação salva permanece inalterada")
        self.cancel_station_map()
        self.open_settings("Estação")
        self.lat.setFocus()

    def save_station(self):
        try: st=self.station()
        except Exception as exc:
            QMessageBox.warning(self,"Localização inválida",str(exc));return
        c=self.config.values
        c.update({"callsign":st.callsign,"lat":st.lat,"lon":st.lon,
                  "altitude_m":st.altitude_m,"min_elevation":st.min_elevation,
                  "update_interval_s":float(self.interval.value()),"tune_threshold_hz":int(self.threshold.value())})
        self.config.save()
        self.log(f"Estação salva: {st.callsign} lat={st.lat:.5f} lon={st.lon:.5f}")
        self.track_cache_key=None
        self.map_desc.setText("Trajetória prevista por TLE/OMM · mapa offline Natural Earth")
        self.refresh_passes()
        self.update_map()
        self.map.page().runJavaScript("window.finishLocationPick && window.finishLocationPick()")
        self.map_pick_active=False
        self.map_edit_bar.setVisible(False)
        self.station_map_button.setEnabled(True)

    def apply_grid_locator(self):
        """Preview the geometric center; only Salvar estação persists location."""
        try:
            lat,lon=maidenhead_to_latlon(self.grid_locator.text())
        except ValueError as exc:
            self.location_status.setText("Grid Locator inválido: "+str(exc))
            self.grid_locator.setFocus()
            return
        self.lat.setText(f"{lat:.8f}")
        self.lon.setText(f"{lon:.8f}")
        self.location_status.setText(
            f"Grid {self.grid_locator.text().strip().upper()}: centro da quadrícula "
            f"{lat:.8f}, {lon:.8f} · confira e clique em Salvar estação.")
        self.log("Grid Locator convertido para prévia; estação salva permanece inalterada")

    def geolocate(self):
        """Request browser-native geolocation on operator click, never via IP/GPS."""
        self.location_waiting=True
        self.browser_geo_started=time.monotonic()
        self.get_position.setEnabled(False)
        self.location_status.setText(
            "Navegador: solicitando permissão de localização; nenhuma informação foi salva.")
        try:
            self.map.page().runJavaScript(
                "window.requestBrowserGeolocation && window.requestBrowserGeolocation()")
            if not hasattr(self,"browser_geo_timer"):
                self.browser_geo_timer=QTimer(self)
                self.browser_geo_timer.timeout.connect(self.poll_browser_geolocation)
            self.browser_geo_timer.start(700)
        except Exception as exc:
            self.finish_browser_geolocation("Navegador não disponível: "+str(exc))

    def grant_browser_geo(self,security_origin,feature):
        """Grant only an explicitly requested geolocation permission."""
        page=self.map.page()
        try:
            from .qt_compat import QT_BINDING
            if QT_BINDING=="PySide6":
                from PySide6.QtWebEngineCore import QWebEnginePage
            else:
                from PySide2.QtWebEngineWidgets import QWebEnginePage
            geo=getattr(QWebEnginePage,"Geolocation",None)
            if geo is None:geo=QWebEnginePage.Feature.Geolocation
            granted=getattr(QWebEnginePage,"PermissionGrantedByUser",None)
            denied=getattr(QWebEnginePage,"PermissionDeniedByUser",None)
            if granted is None:
                granted=QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                denied=QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
            page.setFeaturePermission(
                security_origin,feature,
                granted if self.location_waiting and feature==geo else denied)
        except Exception as exc:
            self.log("Navegador: serviço de permissão de localização indisponível: "+str(exc))

    def finish_browser_geolocation(self,message):
        self.location_waiting=False
        self.get_position.setEnabled(True)
        if hasattr(self,"browser_geo_timer"):self.browser_geo_timer.stop()
        self.location_status.setText(message)

    def poll_browser_geolocation(self):
        if not self.location_waiting:return
        if time.monotonic()-self.browser_geo_started>18:
            self.finish_browser_geolocation(
                "Tempo excedido ao solicitar localização do navegador. "
                "Informe latitude/longitude ou Grid Locator.")
            return
        self.map.page().runJavaScript(
            "window.takeBrowserGeolocation && window.takeBrowserGeolocation()",
            self.browser_geolocation_result)

    def browser_geolocation_result(self,reply):
        if not self.location_waiting or not isinstance(reply,dict):return
        if reply.get("pending"):return
        if reply.get("error"):
            self.finish_browser_geolocation(
                "Navegador não forneceu coordenadas: "+str(reply["error"])+
                ". Use inserção manual ou Grid Locator.")
            return
        try:
            fix=GeoFix(
                float(reply["lat"]),float(reply["lon"]),"Navegador (geolocalização autorizada)",
                accuracy_m=float(reply["accuracy"]) if reply.get("accuracy") is not None else None
            ).validate()
        except (ValueError,TypeError,KeyError) as exc:
            self.finish_browser_geolocation("Posição do navegador inválida: "+str(exc))
            return
        self.finish_browser_geolocation(
            "Navegador retornou coordenadas; confirme a prévia antes de salvar.")
        self.apply_location_fix(fix)

    def apply_location_fix(self,fix):
        """Explicit preview; applies to edit controls only after confirmation."""
        fix=fix.validate()
        alt=f" · altitude {fix.altitude_m:.1f} m" if fix.altitude_m is not None else ""
        accuracy=(f" · precisão informada ±{fix.accuracy_m:.0f} m"
                  if fix.accuracy_m is not None else " · precisão não informada")
        approximate="\nATENÇÃO: resultado aproximado; não use como localização precisa da antena." if fix.approximate else ""
        summary=(f"Fonte: {fix.source}\n"
                 f"Latitude: {fix.latitude:.7f}\nLongitude: {fix.longitude:.7f}"
                 f"{alt}{accuracy}\n{fix.description}{approximate}\n\n"
                 "Preencher os campos? A estação só será alterada ao clicar em Salvar estação.")
        if QMessageBox.question(self,"Conferir coordenadas",summary,
                                QMessageBox.Yes | QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
            self.location_status.setText("Sugestão recusada; coordenadas anteriores preservadas.")
            return
        self.lat.setText(f"{fix.latitude:.7f}")
        self.lon.setText(f"{fix.longitude:.7f}")
        if fix.altitude_m is not None and -500<=fix.altitude_m<=9000:
            self.altitude.setValue(fix.altitude_m)
        self.location_status.setText(f"{fix.source}: campos preenchidos, aguardando Salvar estação.")
        self.log(f"Nova posição pré-preenchida (origem: {fix.source}); salvar estação requer ação manual")

    def update_ports(self):
        previous=self.ports.currentText() or self.config.values['port']
        ports=available_ports()
        self.ports.clear()
        self.ports.addItems(ports)
        if previous:self.ports.setCurrentText(previous)
        if hasattr(self,"gps_port"):
            old_gps=self.gps_port.currentText() or self.config.values.get("gps_port","")
            self.gps_port.clear();self.gps_port.addItems(ports)
            if old_gps:self.gps_port.setCurrentText(old_gps)

    def change_startup_connect(self,enabled):
        self.config.values["cat_auto_connect_startup"]=bool(enabled)
        self.config.save()

    def startup_cat_connect(self):
        """Autoconnect; only the configured Auto CAT opt-in can authorize tuning."""
        if not self.radio.connected and self.config.values.get("port","").strip():
            self.request_cat_connection(startup=True)

    def request_cat_connection(self,startup=False):
        if self.cat_connecting or "cat-connect" in self.pending_jobs:
            return
        port=self.config.values.get("port","").strip() if startup else self.ports.currentText().strip()
        if not port:
            if not startup:
                self.start_cat_scan()  # v1.5.0: sem porta configurada, procura o rádio sozinho
            return
        baud=int(self.baud_combo.currentText())
        stopbits=int(self.stops_combo.currentText())
        self.cat_connecting=True
        self.cat_connect_was_startup=bool(startup)
        self.cat_indicator.setText("CAT")
        self.cat_indicator.setToolTip("CAT conectando · "+port)
        self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ffe4b0;background:#755225;border:1px solid #e0aa55")
        self.cat_indicator.setEnabled(False)
        self.connection.setEnabled(False)
        self.cat_tune_status.setText("CAT: conectando "+port+" (somente leitura inicial)…")
        self.log("CAT: iniciando conexão "+port+"; auto="+str(startup))
        self.background("cat-connect",lambda:self.radio.connect(port,baud,stopbits))

    def start_cat_scan(self):
        """Varre portas/velocidades em segundo plano e conecta ao rádio encontrado (somente leitura)."""
        if "cat-scan" in self.pending_jobs:
            return
        from .cat import available_ports
        from .cat_scan import scan
        self._cat_scan_cancel=threading.Event()
        self._cat_scan_progress="Procurando o rádio nas portas seriais…"
        saved=self.config.values.get("port","").strip()
        preferred=(saved,int(self.config.values.get("baud",9600) or 9600)) if saved else None
        self.cat_indicator.setToolTip("Procurando o rádio · clique para cancelar")
        self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ffe4b0;background:#755225;border:1px solid #e0aa55")
        self.cat_tune_status.setText(self._cat_scan_progress)
        self.log("CAT: varredura automática de portas iniciada")
        def progress(text):
            self._cat_scan_progress="Procurando o rádio: "+text
        self.background("cat-scan",lambda:scan(available_ports(),preferred=preferred,progress=progress,
                                                cancel=self._cat_scan_cancel))

    def cat_scan_finished(self,result):
        found,report=result
        self._cat_scan_progress=""
        for line in report:
            self.log("CAT varredura: "+line)
        if found is None:
            cancelled=report[-1:]==["Varredura cancelada"]
            self.cat_tune_status.setText("Varredura cancelada" if cancelled else "Nenhum rádio encontrado nas portas seriais")
            self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ffe7e7;background:#783437;border:1px solid #db565e")
            if not cancelled:
                QMessageBox.warning(self,"CAT não encontrado",
                    "Nenhum TS-2000 ou FT-817/818 respondeu nas portas seriais.\n\nConfira cabo, driver USB-serial, "
                    "se o rádio está ligado e se outro programa não está usando a porta.\n\n"+"\n".join(report[-8:]))
            return
        self.log(f"CAT: {found.model} encontrado em {found.port} · {found.baud} bps ({found.detail})")
        if found.model=="TS-2000":
            self.config.values.update({"port":found.port,"baud":found.baud,"stopbits":found.stopbits})
            self.config.save()
            if self.ports.findText(found.port)<0:self.ports.addItem(found.port)
            self.ports.setCurrentText(found.port)
            self.baud_combo.setCurrentText(str(found.baud))
            self.stops_combo.setCurrentText(str(found.stopbits))
            self.cat_tune_status.setText(f"TS-2000 encontrado em {found.port} · {found.baud} bps · conectando…")
            self._cat_after_scan=True
            self.request_cat_connection(startup=False)
        else:
            panel=getattr(self,"sdr_panel",None)
            c=self.config.values
            c.update({"ft817_port":found.port,"ft817_baud":found.baud,"tx_device":"FT-817"})
            if c.get("rx_device") in ("TS-2000","NONE",""):
                c["rx_device"]="FT-817"
            self.config.save()
            self.cat_tune_status.setText(f"{found.model} encontrado em {found.port} · {found.baud} bps")
            if panel is not None:
                panel._select(panel.rx_dev,c["rx_device"]);panel._select(panel.tx_dev,"FT-817")
                panel.ft_port.setCurrentText(found.port);panel.ft_baud.setCurrentText(str(found.baud))
                self.sdr_dock.setVisible(True)
                panel.connect_rigs()
            QMessageBox.information(self,"Rádio encontrado",
                f"Yaesu {found.model}/818 encontrado em {found.port} ({found.baud} bps, {found.detail}).\n\n"
                "Ele foi configurado no painel SDR · Equipamentos RX/TX. Para o Doppler automático, marque "
                "\"Doppler automático nos equipamentos\" (nunca aciona PTT).")

    def toggle_connection(self):
        if "cat-scan" in self.pending_jobs:
            self._cat_scan_cancel.set()
            return
        if self.cat_connecting or "cat-connect" in self.pending_jobs:
            return
        if not self.radio.connected:
            self.request_cat_connection(startup=False)
            return
        self.cat_tracking_armed=False
        self.last_freqs=(None,None)
        self.doppler_checkbox.setChecked(False)
        self.radio.disconnect()
        self.cat_selection_generation+=1
        self.cat_diagnose.setEnabled(False)
        self.cat_live_label.setText("RÁDIO REAL (CAT) · desconectado")
        self.cat_sat_orientation.setText("SAT: rádio desconectado")
        self.last_cat_success=None
        self.cat_indicator.setText("CAT")
        self.cat_indicator.setToolTip("CAT desconectado · clique para conectar")
        self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ffe7e7;background:#783437;border:1px solid #db565e")
        self.connection.setText("Conectar")
        self.radio_label.setText("Desconectado")
        self.map_radio_label.setText("CAT desconectado · RX — MHz · TX — MHz · Modo —")
        self.cat_status.setText("● Desconectado · CAT inativo")
        self.cat_status.setStyleSheet("color:#efc17b;font-size:12px")
        self.cat_rx.setText("RX / DOWNLINK (CAT)\\n— MHz")
        self.cat_tx.setText("TX / UPLINK (CAT)\\n— MHz")
        self.cat_details.setText("SAT — · MAIN — · sem leitura atual")
        self.cat_telemetry.setText("Potência: — · Medidor: — · sem leitura CAT")
        self.cat_operating_detail.setText("CTRL — · TRACE — · VFO/MEM — · CAT desconectado")
        self.last_cat_telemetry=None
        for widget in (self.smeter_main,self.smeter_sub):
            widget.setValue(0);widget.setFormat("sem leitura")
        self.cat_tune_status.setText("CAT desconectado · rastreamento pausado")
        self.log("CAT desconectado pelo operador")

    def enable_satellite(self):
        try:
            if not self.radio.connected: raise ConnectionError("Conecte ao TS-2000 primeiro")
            msg="O TS-2000 será colocado em modo SAT, com MAIN=RX, SUB=TX e TRACE desativado. Continuar?"
            if QMessageBox.question(self,"Configurar SAT",msg) != QMessageBox.Yes:return
            self.render_radio_state(self.radio.enable_satellite_mode())
            if self.config.values.get("cat_auto_select",False):
                self.arm_cat_tracking()
        except Exception as exc:
            QMessageBox.critical(self,"CAT",str(exc))

    def render_radio_state(self, st):
        # v1.6.0: medidores e estado do rádio no display LCD (somente leitura).
        try:
            ex=dict(getattr(st,"extras",{}) or {})
            swapped=not getattr(st,"main_downlink",True)
            # v1.7.0: a orientação real lida (SA) manda — inclusive troca feita no painel do rádio.
            if st.sat and getattr(st,"main_downlink",True)!=self.radio.main_downlink_expected \
                    and "cat-swap" not in self.pending_jobs:
                self.radio.main_downlink_expected=bool(st.main_downlink)
                ident=str(self.sat_combo.currentData() or "")
                if ident:
                    self.config.values.setdefault("main_sub_swapped",{})[ident]=swapped
                    self.config.save()
                self.last_freqs=(None,None)
                self.log("TS-2000: orientação "+("MAIN TX / SUB RX" if swapped else "MAIN RX / SUB TX")+
                         " lida do rádio; display e Auto CAT acompanham")
            signal=st.signal_sub if swapped else st.signal_main
            # RM SWR do TS-2000 vem em 0–30 pontos do medidor; 1+pontos/10 é uma aproximação exibida como SWR.
            swr=(1+st.meter_value/10.0 if st.meter_type.upper().startswith("SWR") and st.meter_value is not None else None)
            self.lcd.set_state(sat_on=bool(st.sat),link="CAT",signal=signal,power_w=st.power_set_w,swr=swr,
                               transmitting=bool((ex.get("if") or {}).get("tx")),extras=ex,swapped=swapped)
        except Exception:
            pass
        self.radio_label.setText(f"{st.model} · SAT {'ON' if st.sat else 'OFF'} · RX {self.radio_freq(st.downlink)} | TX {self.radio_freq(st.uplink)} · Modo {st.mode}")
        self.radio_label.setStyleSheet("color:#69e3bc" if st.sat else "color:#f0c186")
        self.last_cat_success=now_utc()
        self.cat_indicator.setText("CAT")
        self.cat_indicator.setToolTip("CAT conectado e validado · "+self.ports.currentText()+" · clique para desconectar")
        self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ddfff0;background:#12533f;border:1px solid #36b88a")
        self.cat_live_label.setText(
            "RÁDIO REAL (CAT) · MAIN RX [FA] "+self.radio_freq(st.downlink)+
            "  |  SAT UPLINK [FB] "+self.radio_freq(st.uplink)+
            "  |  SUB VFO [FC] "+self.radio_freq(st.sub_receiver)+
            "  |  MAIN "+str(st.mode))
        try:
            sat_status=decode_satellite_status(st.sat_raw)
            if sat_status["sat"] and not sat_status["main_downlink"]:
                orientation="SAT ON · MAIN=UPLINK / SUB=DOWNLINK (orientação inversa)"
                self.cat_sat_orientation.setStyleSheet("font-size:12px;font-weight:800;color:#ffbd73")
            elif sat_status["sat"]:
                orientation="SAT ON · MAIN=DOWNLINK (RX) / SUB=UPLINK (TX)"
                self.cat_sat_orientation.setStyleSheet("font-size:12px;font-weight:800;color:#85f2c2")
            else:
                orientation="SAT OFF no retorno CAT"
                self.cat_sat_orientation.setStyleSheet("font-size:12px;font-weight:800;color:#ffbd73")
            self.cat_sat_orientation.setText(orientation)
        except ValueError as exc:
            self.cat_sat_orientation.setText("SA não interpretável: "+str(exc))
        self.map_radio_label.setText(f"CAT · {st.model} · SAT {'ON' if st.sat else 'OFF'} · RX {self.radio_freq(st.downlink)} · TX {self.radio_freq(st.uplink)} · Modo {st.mode} · {self.last_cat_success.astimezone():%H:%M:%S}")
        self.map_radio_label.setStyleSheet("font-size:13px;color:#69e3bc;font-weight:700")
        self.cat_status.setText(f"● Conectado · {st.model} · SAT {'ON' if st.sat else 'OFF'}")
        self.cat_status.setStyleSheet("color:#69e3bc;font-size:12px")
        self.cat_rx.setText(f"MAIN RX / FA (CAT)\n{self.radio_freq(st.downlink)}")
        self.cat_tx.setText(f"SAT UPLINK / FB (CAT)\n{self.radio_freq(st.uplink)}")
        self.cat_details.setText(f"SAT {'ON' if st.sat else 'OFF'} · MAIN {st.mode} · FC SUB independente {self.radio_freq(st.sub_receiver)} · Última leitura {self.last_cat_success.astimezone():%H:%M:%S} local")
        for widget,value,scale in ((self.smeter_main,st.signal_main,30),(self.smeter_sub,st.signal_sub,15)):
            widget.setValue(value if value is not None else 0)
            widget.setFormat(f"{value:02d}/{scale}" if value is not None else "sem leitura")
        watts=f"{st.power_set_w} W (ajuste)" if st.power_set_w is not None else "—"
        meter=f"{st.meter_type} {st.meter_value}/30" if st.meter_value is not None else "—"
        telemetry_age=(
            (now_utc()-self.last_cat_telemetry).total_seconds()
            if self.last_cat_telemetry is not None else None)
        telemetry_status=(
            f"há {telemetry_age:.0f} s" if telemetry_age is not None
            else "aguardando leitura periódica CAT")
        self.cat_telemetry.setText(
            f"Potência configurada: {watts} · Medidor CAT: {meter} · "
            f"Telemetria {telemetry_status}")
        try:
            current=decode_satellite_status(st.sat_raw)
            self.cat_operating_detail.setText(
                f"CTRL {'SUB' if current['ctrl_sub'] else 'MAIN'} · "
                f"TRACE {'ON' if current['trace'] else 'OFF'} · "
                f"{'MEMÓRIA' if current['memory_mode'] else 'VFO'} · "
                f"SUB RX [FC] {self.radio_freq(st.sub_receiver)} · "
                f"MD MAIN {st.mode}")
        except (TypeError,ValueError):
            self.cat_operating_detail.setText(
                "Estado operacional SA/MD: aguardando leitura válida do rádio")

    def refresh_catalog(self,force=False):
        groups=self.config.values.get("orbit_groups",list(DEFAULT_GROUPS))
        age=age_hours(self.config.dir,"amateur_omm.json")
        missing=any(age_hours(self.config.dir,"group_"+g+".json") is None for g in groups)
        if age is not None and age<2 and not force and not missing:
            self.summary.setText(f"OMM em cache há {age:.1f} h; aguarde o intervalo de 2 h")
            return
        if "omm" in self.pending_jobs:return
        self.orbit_started_at=time.monotonic()
        dlg=QProgressDialog("Baixando catálogo orbital por categorias…","",0,len(groups),self)
        dlg.setWindowTitle("Atualização TLE / OMM")
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.resize(540,150)
        dlg.move(self.frameGeometry().center()-dlg.rect().center())
        dlg.show()
        self.orbit_progress_dialog=dlg
        self.summary.setText("Atualizando elementos orbitais…")
        def notify(index,total,group,count,errors):
            self.events.result.emit("omm-stage",(index,total,group,count,errors))
        self.background("omm",lambda:refresh_orbits(self.config.dir,groups=groups,progress=notify))

    def populate_catalog(self, objects):
        old=self.sat_combo.currentData() or self.config.values.get('selected_norad')
        self.omm={str(o['NORAD_CAT_ID']):o for o in objects if o.get('NORAD_CAT_ID')}
        self.plan_satellites.clear()
        self._active_satellite_id=None  # Reload orbital elements even for the same NORAD
        self.track_cache_key=None
        self.filter_sats(self.search.text())
        if old:
            idx=self.sat_combo.findData(str(old))
            if idx>=0:self.sat_combo.setCurrentIndex(idx)
        self.summary.setText(f"{len(self.omm):,} satélites · OMM/TLE".replace(",","."))
        self.summary.setToolTip(f"{len(self.omm)} satélites no catálogo de múltiplas categorias · CelesTrak OMM/TLE")
        self.refresh_satellite_table()
        self.refresh_tracked_table()
        self.refresh_passes()

    def catalog_filtered_ids(self):
        """Full search result including off-screen rows, not just the first page."""
        return list(getattr(self,"_catalog_filtered_ids",[]))

    def bulk_catalog_selection(self,select):
        """Explicit marked NORAD IDs work even before their frequency data exists."""
        updated,affected=change_selection(self.omm,self.catalog_filtered_ids(),
            self.enabled_satellite_ids(),select,self.scope_filtered.isChecked())
        if not affected:
            self.catalog_progress.setText("Nenhum satélite corresponde à pesquisa")
            return
        self.config.values["satellite_selection"]=updated
        self.config.save()
        self.refresh_satellite_table()
        self.refresh_tracked_table()
        self.filter_sats(self.search.text())
        self.refresh_passes()
        self.catalog_progress.setText(f"Seleção salva: {len(updated)} de {len(self.omm)} satélites · ação em {len(affected)} registros")
        self.log(f"Seleção: {'marcados' if select else 'desmarcados'} {len(affected)} satélites (sem CAT)")

    def refresh_catalog_transmitters(self):
        """Execute download without requiring a double-click on an individual satellite."""
        ids=transmitter_batch_ids(3,None,[],[],self.omm)
        if not ids:
            self.catalog_progress.setText("Catálogo orbital vazio: atualize as órbitas antes das frequências")
            return
        if "tx-batch" in self.pending_jobs:
            self.catalog_progress.setText("Já existe atualização em execução")
            return
        if len(ids)>25:
            reply=QMessageBox.question(self,"Atualizar frequências",
                f"Consultar SatNOGS para {len(ids)} satélites? Requisições sequenciais e canceláveis.",
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if reply!=QMessageBox.Yes:return
        self.freq_update_cancel=False
        self.frequency_started_at=time.monotonic()
        self.refresh_catalog_freq.setEnabled(False)
        self.stop_catalog_freq.setEnabled(True)
        self.catalog_progress.setText(f"SatNOGS: iniciando 0/{len(ids)}")
        self.frequency_progress_dialog=QProgressDialog(
            f"Consultando frequências SatNOGS…\n0 de {len(ids)} satélites", "Cancelar",0,len(ids),self)
        self.frequency_progress_dialog.setWindowTitle("Atualizar frequências dos satélites")
        self.frequency_progress_dialog.setMinimumDuration(0)
        self.frequency_progress_dialog.setAutoClose(False)
        self.frequency_progress_dialog.setAutoReset(False)
        self.frequency_progress_dialog.setWindowModality(Qt.WindowModal)
        self.frequency_progress_dialog.resize(520,142)
        center=self.frameGeometry().center()
        self.frequency_progress_dialog.move(center-self.frequency_progress_dialog.rect().center())
        self.frequency_progress_dialog.canceled.connect(self.cancel_catalog_transmitters)
        self.frequency_progress_dialog.setValue(0)
        self.frequency_progress_dialog.show()
        data_dir=self.config.dir
        def work():
            import time
            stats={"total":len(ids),"ok":0,"no_data":0,"failed":[],"cancelled":False}
            for i,ident in enumerate(ids,1):
                if self.freq_update_cancel:
                    stats["cancelled"]=True;break
                try:
                    rows=refresh_transmitters(data_dir,int(ident))
                    if rows:stats["ok"]+=1
                    else:stats["no_data"]+=1
                    self.events.result.emit("tx-batch-item",(ident,rows,i,len(ids)))
                except Exception as exc:
                    stats["failed"].append(f"{ident}: {exc}")
                    self.events.result.emit("tx-batch-item",(ident,None,i,len(ids)))
                if i<len(ids):time.sleep(0.4)
            return stats
        self.background("tx-batch",work)

    def cancel_catalog_transmitters(self):
        if "tx-batch" not in self.pending_jobs:return
        self.freq_update_cancel=True
        self.catalog_progress.setText("Cancelamento solicitado; aguardando consulta atual")
        if self.frequency_progress_dialog:
            self.frequency_progress_dialog.setLabelText(
                "Cancelamento solicitado; aguardando a consulta SatNOGS atual…")

    def change_catalog_categories(self,*args):
        selected=[name for name,action in self.catalog_category_actions.items() if action.isChecked()]
        self.config.values["catalog_category_filter"]=selected
        self.config.save()
        self.catalog_category.setText(f"Categorias: {len(selected)}/{len(self.catalog_category_actions)}")
        self.refresh_satellite_table()

    def set_catalog_categories(self,checked):
        for action in self.catalog_category_actions.values():
            action.blockSignals(True)
            action.setChecked(bool(checked))
            action.blockSignals(False)
        self.change_catalog_categories()
    def refresh_satellite_table(self, text=None):
        """Virtualized search: thousands of cached satellites must not freeze Qt."""
        query=normalized_satellite_search(
            text if isinstance(text,str) else self.catalog_search.text())
        old_row=self.catalog_table.currentRow()
        previous=self.catalog_table.item(old_row,0) if old_row>=0 else None
        previous_id=str(previous.data(Qt.UserRole)) if previous is not None else None
        checked=set(self.enabled_satellite_ids())
        categories={name for name,action in self.catalog_category_actions.items()
                    if action.isChecked()} if hasattr(self,"catalog_category_actions") else set(DEFAULT_GROUPS)
        ids=[]
        for ident,obj in self.omm.items():
            if not categories.intersection(obj.get("CATEGORIES",["amateur"])):
                continue
            if query and query not in satellite_search_text(ident,obj):
                continue
            ids.append(ident)
        ids.sort(key=lambda ident:str(self.omm[ident].get("OBJECT_NAME",ident)).casefold())
        self._catalog_filtered_ids=ids
        shown=ids[:350]
        self._loading_catalog=True
        try:
            self.catalog_table.setSortingEnabled(False)
            self.catalog_table.setRowCount(len(shown))
            for row,ident in enumerate(shown):
                obj=self.omm[ident]
                orb=orbital_characteristics(obj)
                info=operational_characteristics(load_transmitters(self.config.dir,int(ident)))
                cols=[orb["name"],ident,
                      f"{orb['inclination_deg']:.1f}°" if orb["inclination_deg"] is not None else "—",
                      f"{orb['period_min']:.1f} min" if orb["period_min"] is not None else "—",
                      ", ".join(info["modes"]) or "—",
                      ", ".join(f"{n:.3f}" for n in info["downlinks_mhz"][:3]) or "—",
                      info["status"]]
                for column,value in enumerate(cols):
                    cell=QTableWidgetItem(str(value))
                    cell.setFlags(cell.flags()&~Qt.ItemIsEditable)
                    cell.setData(Qt.UserRole,ident)
                    if ident in checked:
                        cell.setBackground(QBrush(QColor("#ffe36a")))
                        cell.setForeground(QBrush(QColor("#111111")))
                    self.catalog_table.setItem(row,column,cell)
            self.catalog_table.setSortingEnabled(True)
            if previous_id is not None:
                for row in range(self.catalog_table.rowCount()):
                    item=self.catalog_table.item(row,0)
                    if item is not None and str(item.data(Qt.UserRole))==previous_id:
                        self.catalog_table.selectRow(row)
                        break
        finally:
            self._loading_catalog=False
        self.catalog_note.setText(
            f"Exibindo {len(shown)} de {len(ids)} resultados · "
            f"{len(self.omm)} órbitas em cache · {len(checked)} selecionados. "
            "Pesquise por nome, NORAD ou apelido para refinar.")

    def queue_catalog_single_click(self,row,col):
        """Delay a single click so a double click does not toggle twice."""
        if self._loading_catalog or time.monotonic()<self.catalog_ignore_clicks_until:return
        item=self.catalog_table.item(row,0)
        if item is None:return
        self.catalog_click_norad=str(item.data(Qt.UserRole))
        self.catalog_click_timer.start(QApplication.doubleClickInterval()+40)

    def commit_catalog_single_click(self):
        ident=self.catalog_click_norad
        self.catalog_click_norad=None
        if ident:self.toggle_catalog_favorite(ident)

    def toggle_catalog_satellite_selection(self,row,col):
        """Compatible single-row action for programmatic use."""
        item=self.catalog_table.item(row,0)
        if item is not None:self.toggle_catalog_favorite(str(item.data(Qt.UserRole)))

    def toggle_catalog_favorite(self,ident):
        """Persist favorite state; repaint the row, stay on Satélites."""
        if self._loading_catalog or ident not in self.omm:return
        enabled=set(self.enabled_satellite_ids())
        updated,_=change_selection(self.omm,[ident],enabled,ident not in enabled,True)
        self.config.values["satellite_selection"]=updated
        self.config.save()
        selected=ident in updated
        for row in range(self.catalog_table.rowCount()):
            item=self.catalog_table.item(row,0)
            if item is None or str(item.data(Qt.UserRole))!=ident:continue
            for col in range(self.catalog_table.columnCount()):
                cell=self.catalog_table.item(row,col)
                if cell is not None:
                    cell.setBackground(QBrush(QColor("#ffe36a" if selected else "#0b1b2e")))
                    cell.setForeground(QBrush(QColor("#111111" if selected else "#e8edf5")))
            break
        self.refresh_tracked_table()
        self.filter_sats(self.search.text())
        self.refresh_passes()
        self.catalog_progress.setText(
            f"NORAD {ident}: {'favorito marcado' if selected else 'favorito desmarcado'} · "
            f"{len(updated)} de {len(self.omm)} satélites selecionados")

    def select_catalog_satellite(self,row,col):
        """Double click toggles the favorite; never navigates to Operação."""
        self.catalog_ignore_clicks_until=time.monotonic()+0.45
        self.catalog_click_timer.stop()
        self.catalog_click_norad=None
        item=self.catalog_table.item(row,0)
        if item is not None:self.toggle_catalog_favorite(str(item.data(Qt.UserRole)))

    def filter_sats(self,text):
        selected=self.sat_combo.currentData() or self.config.values.get('selected_norad')
        self.sat_combo.blockSignals(True)
        self.sat_combo.clear()
        search=text.casefold().strip()
        enabled=set(self.enabled_satellite_ids())
        for ident,o in sorted(self.omm.items(),key=lambda item:item[1].get('OBJECT_NAME','')):
            if ident not in enabled:continue
            name=o.get('OBJECT_NAME',ident)
            if normalized_satellite_search(search) in satellite_search_text(ident,o):
                self.sat_combo.addItem(f"{name}  ·  {ident}",ident)
        if selected:
            idx=self.sat_combo.findData(str(selected))
            if idx>=0:self.sat_combo.setCurrentIndex(idx)
        self.sat_combo.blockSignals(False)
        if hasattr(self,"sat_list"):
            self.sat_list.blockSignals(True)
            self.sat_list.setRowCount(self.sat_combo.count())
            for row_index in range(self.sat_combo.count()):
                ident=str(self.sat_combo.itemData(row_index))
                sat_obj=self.omm.get(ident,{})
                name=str(sat_obj.get("OBJECT_NAME",ident))
                item=QTableWidgetItem(name[:28]+"\nNORAD "+ident)
                item.setData(Qt.UserRole,ident)
                mode=self.suggested_mode_text(ident)
                self.sat_list.setItem(row_index,0,item)
                self.sat_list.setItem(row_index,1,QTableWidgetItem(mode))
                self.sat_list.setRowHeight(row_index,46)
            self.sat_list.blockSignals(False)
        self.choose_satellite()

    def select_list_satellite(self,row,column):
        if 0 <= row < self.sat_combo.count():
            self.sat_combo.setCurrentIndex(row)
            self.arm_cat_tracking()  # table click is an explicit operator selection

    def choose_satellite(self):
        ident=self.sat_combo.currentData()
        swapped=bool(self.config.values.get("main_sub_swapped",{}).get(str(ident or ""),False))
        self.radio.main_downlink_expected=not swapped
        if hasattr(self,"lcd"):
            self.lcd.set_state(swapped=swapped)
        if ident and str(ident) in self.omm:
            self.request_satinfo(str(ident),self.omm[str(ident)].get("OBJECT_NAME",str(ident)))
        if ident==self._active_satellite_id and self.sat is not None:
            return  # The same satellite must not interrupt CAT.
        self.last_freqs=(None,None)
        self.cat_autotune_requested_generation=-1
        self.cat_retry_after=0.0
        self.cat_consecutive_failures=0
        self.cat_last_requested=(None,None)
        self._mode_catalog_sat_id=None
        if self.aos_alarm_dialog is not None:
            self.aos_alarm_dialog.close()
            self.aos_alarm_dialog=None
            self.aos_alarm_target=None
        self.cat_selection_generation+=1
        self._active_satellite_id=ident
        if hasattr(self,"sat_list") and self.sat_combo.currentIndex()>=0 and self.sat_list.rowCount():
            self.sat_list.selectRow(self.sat_combo.currentIndex())
        if not ident or ident not in self.omm:
            self.sat=None;self.sat_detail.setText("Nenhum satélite selecionado");return
        item=self.omm[ident]
        try:
            self.sat=make_satellite(item,self.ts)
        except Exception as exc:
            self.log(f"Erro OMM {ident}: {exc}")
            self.sat=None;return
        self.track_cache_key=None
        self.config.values['selected_norad']=ident
        self.config.save()
        age=(now_utc()-self.sat.epoch.utc_datetime().replace(tzinfo=timezone.utc)).total_seconds()/86400
        self.photo.setHtml(photo_html(None))
        photo_name=str(item.get("OBJECT_NAME",ident))
        self.background('photo:'+str(ident),lambda:find_photo(self.config.dir,photo_name,ident))
        self.sat_detail.setText(
            characteristics_text(item,load_transmitters(self.config.dir,int(ident))) +
            f"\nÉpoca {'TLE' if item.get('TLE_LINE1') else 'OMM'}: {self.sat.epoch.utc_strftime('%d/%m/%Y %H:%M UTC')} ({age:+.1f} d)")
        self.options=[]
        self.choose_cached_modes(int(ident))
        self.refresh_modes(force=False)
        self.update_map()
        self.preview_doppler()
        self.refresh_passes()
        self.update_next_indicator()

    def refresh_modes(self,force=False):
        ident=self.sat_combo.currentData()
        if not ident:return
        hours=age_hours(self.config.dir,f"tx_{ident}.json")
        if force or hours is None or hours>24:
            self.background('tx:'+str(ident),lambda:refresh_transmitters(self.config.dir,int(ident)))

    def choose_cached_modes(self,ident):
        # The API might list telemetry/obsolete entries before FM voice.
        # Preserve explicitly selected mode on background catalog refresh.
        old_choice=self.mode_combo.currentData() if self._mode_catalog_sat_id==str(ident) else None
        old_uuid=(self.options[old_choice].get("uuid")
                  if isinstance(old_choice,int) and 0<=old_choice<len(self.options)
                  else None)
        manual_was_selected=(old_choice==-1 and bool(self.options))
        self._mode_catalog_sat_id=str(ident)
        self.options=prioritized_transponders(ident,
                transponder_options(load_transmitters(self.config.dir,ident)))
        self.mode_combo.blockSignals(True);self.mode_combo.clear()
        self.mode_combo.addItem("Manual (frequências customizadas)",-1)
        for i, opt in enumerate(self.options):
            info='RX apenas' if opt['receive_only'] else 'RX/TX'
            self.mode_combo.addItem(f"{opt['name'][:43]} · {opt['mode']} · {info}",i)
        index=1 if self.options else 0
        if manual_was_selected:
            index=0
        elif old_uuid:
            for pos,item in enumerate(self.options,1):
                if item.get("uuid")==old_uuid:
                    index=pos
                    break
        self.mode_combo.setCurrentIndex(index)
        self.mode_combo.blockSignals(False)
        self.choose_mode()
        self.refresh_satellite_table()

    def choose_mode(self):
        self.last_freqs=(None,None)
        self.cat_autotune_requested_generation=-1
        self.cat_retry_after=0.0
        self.cat_consecutive_failures=0
        i=self.mode_combo.currentData()
        if not isinstance(i,int) or i<0 or i>=len(self.options):
            self.mode_note.setText("Modo manual: confira cada frequência e modo antes de usar.")
            self.preview_doppler()
            self.cat_selection_generation+=1
            if self.cat_tracking_armed:
                self.auto_tune_selected_satellite()
            return
        opt=self.options[i]
        low,high=opt['downlink'],opt['downlink_high']
        center=round((low+high)/2)
        self.down_edit.setText(f"{center/1e6:.6f}")
        if opt['uplink'] is not None:
            ul=paired_linear_uplink(center,low,high,opt['uplink'],opt['uplink_high'],opt['inverted']) if (high>low and opt['uplink_high']>opt['uplink']) else opt['uplink']
            self.up_edit.setText(f"{ul/1e6:.6f}")
        else:self.up_edit.clear()
        mode=opt['mode'].replace('FMN','FM').replace('AFSK','FM')
        if mode in ('USB','LSB','FM','CW','AM','FSK'):
            self.rx_mode.setCurrentText(mode)
            self.tx_mode.setCurrentText('LSB' if mode=='USB' and opt['inverted'] else 'USB' if mode=='LSB' and opt['inverted'] else mode)
        source=opt.get("source","SatNOGS")
        self.mode_note.setText(f"{source} · {'Inversor' if opt['inverted'] else 'Não inversor'} · {'somente recepção (sem TX CAT)' if opt['receive_only'] else 'uplink/downlink'} · confira a situação operacional do satélite")
        self.preview_doppler()
        self.cat_selection_generation+=1
        if self.cat_tracking_armed:
            self.auto_tune_selected_satellite()

    def on_cat_operator_changed(self,*args):
        """Explicit changes to RX mode/frequency must immediately rearm Auto CAT."""
        if not self.config.values.get("cat_auto_select",False):
            return
        if not self.radio.connected or not self.sat:
            return
        self.cat_selection_generation+=1
        self.arm_cat_tracking()

    def arm_cat_tracking(self,*args):
        """Called only for an explicit user selection, not session restoration."""
        if not self.config.values.get("cat_auto_select",True):
            self.cat_tune_status.setText("Auto CAT desativado pelo operador")
            return
        self.cat_tracking_armed=True
        self.last_freqs=(None,None)
        self.cat_autotune_requested_generation=-1
        self.cat_retry_after=0.0
        self.cat_consecutive_failures=0
        self.last_tracking_write=0.0
        self.cat_tune_status.setText("Auto CAT online · sintonizando seleção e acompanhando em tempo real…")
        self.auto_tune_selected_satellite()

    def save_complete_logs(self):
        """Export retained CAT and SAT logs to an operator-chosen local ZIP."""
        suggested="PT2VHF-Sat-Tool-LOGs-"+datetime.now().strftime("%Y-%m-%d_%H-%M-%S")+".zip"
        path,_=QFileDialog.getSaveFileName(self,"Baixar log completo",
                        str(Path.home()/suggested),"Arquivo ZIP (*.zip)")
        if not path:return
        self.export_logs.setEnabled(False)
        self.log("Exportação local solicitada: "+str(path))
        visible=self.log_view.toPlainText()
        self.background("logs-export",lambda:self.journal.export(
            Path(path),visible_log=visible,diagnostics_dir=diagnostic_dir(),version=__version__))

    def is_safe_crossband(self,ul,dl):
        """Validate the selected CAT channel rather than an assumed band pair."""
        return cat_pair_diagnostic(ul,dl)[0]

    def selected_cat_pair_info(self,ul,dl):
        """Detailed evidence for CAT block, without writing any PTT commands."""
        safe,reason=cat_pair_diagnostic(ul,dl)
        norad=str(self.sat_combo.currentData() or "não selecionado")
        selection=self.mode_combo.currentText()
        rx="—" if dl is None else f"{dl/1e6:.6f}"
        tx="—" if ul is None else f"{ul/1e6:.6f}"
        if not safe:
            self.log(f"CAT PERFIL BLOQUEADO: NORAD={norad}; transponder={selection}; "
                     f"RX={rx} MHz; TX={tx} MHz; avaliação={reason}")
        hint=(" Para SO-50, selecione 'SO-50 · repetidor FM V/U (AMSAT)' "
              "e confira RX 436,795 / TX 145,850 MHz.") if norad=="27607" else ""
        return safe,(f"{reason}. NORAD {norad} · transponder: {selection} · "
                     f"RX {rx} MHz / TX {tx} MHz."+hint)

    def cat_tracking_gate(self,reason):
        """Journal only transitions/repeated diagnostics every 20 seconds."""
        moment=time.monotonic()
        if reason!=self.cat_last_gate or moment-self.cat_last_gate_time>=20.0:
            self.cat_last_gate=reason
            self.cat_last_gate_time=moment
            self.log("Auto CAT ciclo · "+reason)

    def _track_rx_only(self,note=None):
        """Somente RX (v1.6.0): acompanha só o downlink pelo CAT; nunca escreve uplink nem PTT."""
        try:
            from .operations import frequency_prediction
            _,dl=self.nominal_hz()
            dl=int(frequency_prediction({"downlink_hz":dl,"uplink_hz":None},self.last_pos["radial_m_s"])["rx_hz"])
            threshold=max(1,int(self.threshold.value()))
            last=self.last_freqs[1] if self.last_freqs else None
            observed=self.radio.state.downlink
            if (last is not None and abs(dl-last)<threshold and observed is not None and abs(dl-observed)<threshold):
                if callable(note):note("Doppler RX dentro do limiar")
                return False
            generation=self.cat_selection_generation
            self.last_tracking_write=time.monotonic()
            started=self.last_tracking_write
            def task():
                if generation!=self.cat_selection_generation or not self.radio.connected:
                    return generation,None,None,None,0.0
                return generation,self.radio.set_rx_only(dl),None,dl,time.monotonic()-started
            self.background("cat-track",task)
            return True
        except Exception as exc:
            self.cat_tune_status.setText("CAT (somente RX) aguardando: "+str(exc))
            return False

    def toggle_cat_details(self,shown):
        self.cat_details_box.setVisible(bool(shown))
        self.cat_details_toggle.setText("Detalhes CAT ▾" if shown else "Detalhes CAT ▸")
        self.config.values["cat_details_visible"]=bool(shown)
        self.config.save()

    def show_cat_port_error(self,message):
        """v1.7.1: falha de porta CAT com causa clara, orientação e atalho para Configurações → Rádio."""
        from .cat import port_error_text
        title,advice=port_error_text(message,str(self.config.values.get("port","") or ""))
        box=QMessageBox(QMessageBox.Warning,title,f"{title}.\n\n{advice}\n\nDetalhe técnico: {message[:300]}",parent=self)
        settings=box.addButton("Abrir Configurações → Rádio",QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Close)
        box.exec() if hasattr(box,"exec") else box.exec_()
        if box.clickedButton() is settings:
            self.open_settings("Rádio")

    def open_settings(self,page="Rádio"):
        """Abre Configurações direto na aba pedida (Apresentação, Estação, Rádio, Rotores, Geral)."""
        page={"Rotor":"Rotores","Apresentação":"Aparência"}.get(page,page)  # nomes até a v1.7.0
        self.tabs.setCurrentIndex(2)
        widget=getattr(self,"settings_pages",{}).get(page)
        if widget is not None:
            self.settings_tabs.setCurrentWidget(widget)

    def build_presentation_settings(self,layout):
        """v1.7.1: aba Aparência — tema do programa + display (tipo, fonte, cores e prévia ao vivo)."""
        from .lcd import LcdDisplay, MODELS, FONTS, THEMES
        self.build_theme_settings(layout)
        box,bv=group("DISPLAY DE RÁDIO")
        grid=QGridLayout();grid.setColumnStretch(1,1)
        self.display_model=QComboBox()
        for code,name in MODELS.items():
            self.display_model.addItem(name,code)
        self.display_font=QComboBox()
        for code,name in FONTS.items():
            self.display_font.addItem(name,code)
        self.display_theme=QComboBox()
        from .lcd import THEME_ORDER
        for name in THEME_ORDER:
            self.display_theme.addItem(name.capitalize(),name)
        for row,(txt,widget) in enumerate((("Tipo de display",self.display_model),
                                           ("Fonte (matriz de pontos)",self.display_font),
                                           ("Cor",self.display_theme))):
            grid.addWidget(label(txt),row,0);grid.addWidget(widget,row,1)
        bv.addLayout(grid)
        self.display_preview=LcdDisplay()
        self.display_preview.setMinimumHeight(132)
        self.display_preview.set_state(rx_hz=436_795_120,tx_hz=145_850_340,rx_mode="FM",tx_mode="FM",signal=18,
                                       power_w=25,swr=1.2,sat_on=True,link="CAT",auto=True,doppler_hz=-6800,
                                       visible=True,elevation=38,los_s=342)
        bv.addWidget(label("Prévia (dados de exemplo):"))
        bv.addWidget(self.display_preview)
        bv.addWidget(label("A troca vale na hora, sem reiniciar. As teclas A/B e RX ONLY funcionam em todos os modelos."))
        for combo,key,default in ((self.display_model,"display_model","matriz"),
                                  (self.display_font,"display_font","normal"),
                                  (self.display_theme,"lcd_theme","âmbar")):
            idx=combo.findData(str(self.config.values.get(key,default)))
            combo.setCurrentIndex(max(0,idx))
            combo.currentIndexChanged.connect(self.change_display_settings)
        layout.addWidget(box)
        self.change_display_settings(save=False)

    def build_theme_settings(self,layout):
        """Tema do programa: pronto + ajustes finos, prévia ao vivo (aplica na hora) e Restaurar padrão."""
        from .appearance import PRESETS, ACCENT_HUES, DEFAULTS
        box,bv=group("TEMA DO PROGRAMA")
        grid=QGridLayout()
        c=self.config.values
        self.theme_preset=QComboBox()
        for code,name in PRESETS.items():
            self.theme_preset.addItem(name,code)
        self.theme_accent=QComboBox()
        for name,hue in ACCENT_HUES.items():
            self.theme_accent.addItem(name,hue)
        def spin(lo,hi,suffix):
            w=QDoubleSpinBox();w.setRange(lo,hi);w.setDecimals(0);w.setSingleStep(5 if hi>50 else 1);w.setSuffix(suffix);return w
        self.theme_brightness=spin(50,150," %");self.theme_contrast=spin(50,160," %")
        self.theme_saturation=spin(0,150," %");self.theme_font=spin(9,18," px")
        self.theme_follow_display=QCheckBox("Display acompanha o brilho")
        self.theme_follow_map=QCheckBox("Mapa acompanha o brilho")
        rows=(("Tema",self.theme_preset),("Cor de destaque",self.theme_accent),("Brilho",self.theme_brightness),
              ("Contraste",self.theme_contrast),("Saturação",self.theme_saturation),("Tamanho da fonte",self.theme_font))
        for i,(txt,w) in enumerate(rows):
            grid.addWidget(label(txt),i,0);grid.addWidget(w,i,1)
        bv.addLayout(grid)
        follow=QHBoxLayout();follow.addWidget(self.theme_follow_display);follow.addWidget(self.theme_follow_map)
        self.theme_reset=QPushButton("Restaurar padrão")
        follow.addWidget(self.theme_reset)
        bv.addLayout(follow)
        self.theme_status=label("")
        self.theme_status.setStyleSheet("font-size:11px")
        bv.addWidget(self.theme_status)
        layout.addWidget(box)
        self.load_theme_controls()
        for w in (self.theme_preset,self.theme_accent):
            w.currentIndexChanged.connect(self.change_theme)
        for w in (self.theme_brightness,self.theme_contrast,self.theme_saturation,self.theme_font):
            w.valueChanged.connect(self.change_theme)
        for w in (self.theme_follow_display,self.theme_follow_map):
            w.toggled.connect(self.change_theme)
        self.theme_reset.clicked.connect(self.reset_theme)

    def theme_options(self):
        from .appearance import DEFAULTS
        return {k:self.config.values.get(k,v) for k,v in DEFAULTS.items()}

    def load_theme_controls(self):
        o=self.theme_options()
        widgets=(self.theme_preset,self.theme_accent,self.theme_brightness,self.theme_contrast,self.theme_saturation,
                 self.theme_font,self.theme_follow_display,self.theme_follow_map)
        for w in widgets:w.blockSignals(True)
        self.theme_preset.setCurrentIndex(max(0,self.theme_preset.findData(o["theme_preset"])))
        self.theme_accent.setCurrentIndex(max(0,self.theme_accent.findData(int(o["theme_accent_hue"]))))
        self.theme_brightness.setValue(o["theme_brightness"]);self.theme_contrast.setValue(o["theme_contrast"])
        self.theme_saturation.setValue(o["theme_saturation"]);self.theme_font.setValue(o["theme_font_px"])
        self.theme_follow_display.setChecked(bool(o["theme_follow_display"]))
        self.theme_follow_map.setChecked(bool(o["theme_follow_map"]))
        for w in widgets:w.blockSignals(False)

    def change_theme(self,*_):
        self.config.values.update(
            theme_preset=self.theme_preset.currentData() or "escuro",
            theme_accent_hue=int(self.theme_accent.currentData() if self.theme_accent.currentData() is not None else -1),
            theme_brightness=int(self.theme_brightness.value()),theme_contrast=int(self.theme_contrast.value()),
            theme_saturation=int(self.theme_saturation.value()),theme_font_px=int(self.theme_font.value()),
            theme_follow_display=self.theme_follow_display.isChecked(),theme_follow_map=self.theme_follow_map.isChecked())
        self.config.save()
        self.apply_appearance()

    def reset_theme(self):
        from .appearance import DEFAULTS
        self.config.values.update(DEFAULTS)
        self.config.save()
        self.load_theme_controls()
        self.apply_appearance()

    def apply_appearance(self):
        """Gera a folha de estilo do tema e aplica na hora em toda a janela, painéis, janelas destacadas e diálogos."""
        from .appearance import transform_qss, text_contrast, display_dim
        o=self.theme_options()
        app=QApplication.instance()
        if app is not None:
            app.setStyleSheet(transform_qss(STYLE,o))
            identity=o==THEME_DEFAULTS
            for w in app.allWidgets():
                original=w.property("pt2vhf_qss")
                if original is None:
                    current=w.styleSheet()
                    if not current:
                        continue
                    w.setProperty("pt2vhf_qss",current)
                    original=current
                w.setStyleSheet(original if identity else transform_qss(original,o))
        ratio=text_contrast(o)
        if hasattr(self,"theme_status"):
            ok=ratio>=4.5
            self.theme_status.setText(f"Contraste do texto: {ratio:.1f}:1 · "+("OK (WCAG AA)" if ok else
                                      "abaixo de 4,5:1 — texto pode ficar ilegível; reduza o brilho/ajuste o contraste"))
            from .appearance import transform
            self.theme_status.setProperty("pt2vhf_qss",None)
            self.theme_status.setStyleSheet("font-size:11px;font-weight:700;color:"+
                                            (transform("#2fae5f" if o["theme_preset"]=="claro" else "#5af08a",o) if ok else "#d93030"))
        dim=display_dim(o)
        for lcd in (getattr(self,"lcd",None),getattr(self,"display_preview",None)):
            if lcd is not None:
                lcd.set_dim(dim if o["theme_follow_display"] else 1.0)
        try:
            self.map.page().runJavaScript("document.documentElement.style.filter="+
                                          json.dumps(f"brightness({dim:.2f})" if o["theme_follow_map"] else "none"))
        except Exception:
            pass

    def change_display_settings(self,*_,save=True):
        model=self.display_model.currentData() or "matriz"
        font=self.display_font.currentData() or "normal"
        theme=self.display_theme.currentData() or "âmbar"
        self.display_font.setEnabled(model=="matriz")
        for widget in (getattr(self,"lcd",None),getattr(self,"display_preview",None)):
            if widget is not None:
                widget.set_model(model);widget.set_font_style(font);widget.set_theme(theme)
        if save:
            self.config.values.update(display_model=model,display_font=font,lcd_theme=theme)
            self.config.save()

    def toggle_display_detached(self):
        """Destaca o display numa janela própria (outro monitor) ou o devolve à aba Operação."""
        from .display_window import DisplayWindow, MAX_HEIGHT_DOCKED
        if self.display_window is None:
            self.display_window=DisplayWindow(self.lcd,self.config,self._dock_display)
            self.display_placeholder.setVisible(True)
            if self.config.values.get("display_window_fullscreen",False):
                self.display_window.showFullScreen()
            else:
                self.display_window.show()
            self.config.values["display_detached"]=True
            self.config.save()
            self.log("Display destacado em janela própria (F11 tela cheia; fechar a janela devolve o display)")
        else:
            self.display_window.close()

    def _dock_display(self):
        from .display_window import MAX_HEIGHT_DOCKED
        window,self.display_window=self.display_window,None
        self.lcd.detached=False
        self.lcd.setMinimumHeight(118)
        self.lcd.setMaximumHeight(MAX_HEIGHT_DOCKED)
        self.display_cards.insertWidget(0,self.lcd,1)
        self.lcd.show()
        self.display_placeholder.setVisible(False)
        if not getattr(self,"_closing_app",False):
            self.config.values["display_detached"]=False
            self.config.save()

    def set_display_choice(self,model=None,theme=None):
        """Escolhe modelo/cor do display pelas mesmas caixas de Apresentação (salva e aplica na hora)."""
        for combo,value in ((self.display_model,model),(self.display_theme,theme)):
            if value is not None:
                index=combo.findData(value)
                if index>=0:
                    combo.setCurrentIndex(index)

    def display_scope_tune(self,frac):
        """Clique no escopo do display: mesma regra do clique no waterfall do painel SDR."""
        wf=getattr(getattr(self,"sdr_panel",None),"waterfall",None)
        if wf is None or not self.lcd.state.scope:
            return
        wf.on_click((float(frac)-0.5)*2*wf.span_hz)

    def cycle_display(self,what):
        """Teclas TIPO (modelo) e LUZ (cor do backlight) do display: passam para o próximo item."""
        from .lcd import MODELS, next_in
        if what=="model":
            self.set_display_choice(model=next_in(MODELS,self.display_model.currentData()))
            self.log("Display: "+self.display_model.currentText())
        else:
            from .lcd import themes_for
            model=self.display_model.currentData()
            self.set_display_choice(theme=next_in(themes_for(model),self.display_theme.currentData()))
            self.log("Display: backlight "+self.display_theme.currentText())

    def toggle_rx_only(self):
        enabled=not bool(self.config.values.get("rx_only",False))
        self.config.values["rx_only"]=enabled
        self.config.save()
        self.last_freqs=(None,None)
        self.cat_selection_generation+=1
        self.lcd.set_state(rx_only=enabled)
        self.log("Modo Somente RX "+("ligado: nenhum uplink/TX é calculado ou enviado" if enabled else "desligado"))
        self.preview_doppler()
        if self.cat_tracking_armed:
            self.auto_tune_selected_satellite()

    def toggle_main_sub(self):
        """Botão A/B do display: inverte MAIN↔SUB (TX/RX) no TS-2000 (SA P3), com confirmação."""
        ident=str(self.sat_combo.currentData() or "")
        swaps=self.config.values.setdefault("main_sub_swapped",{})
        target=not bool(swaps.get(ident,False))
        if not self.config.values.get("main_sub_confirmed",False):
            if QMessageBox.question(self,"Inverter MAIN↔SUB",
                "Trocar os papéis das bandas do TS-2000: "+("MAIN transmite e SUB recebe" if target else
                "MAIN recebe e SUB transmite")+"?\n\nSó com SAT ligado e fora de transmissão; o programa confere "
                "pela leitura SA/FA/FB e nunca aciona PTT. A escolha fica salva para este satélite.")!=QMessageBox.Yes:
                return
            self.config.values["main_sub_confirmed"]=True
        if not self.radio.connected:
            swaps[ident]=target;self.config.save()
            self.radio.main_downlink_expected=not target
            self.lcd.set_state(swapped=target)
            self.cat_tune_status.setText("A/B: "+("MAIN TX / SUB RX" if target else "MAIN RX / SUB TX")+
                                         " salvo para este satélite · aplicado ao conectar o TS-2000")
            self.log("MAIN↔SUB salvo para este satélite; será aplicado ao conectar o TS-2000")
            return
        if "cat-swap" in self.pending_jobs:
            self.cat_tune_status.setText("A/B: inversão MAIN↔SUB em andamento…")
            return
        if bool((self.radio.state.extras or {}).get("if",{}).get("tx")):
            QMessageBox.information(self,"Inverter MAIN↔SUB","O rádio está transmitindo. Solte o PTT e clique A/B de novo.")
            return
        self.cat_tune_status.setText("A/B: pedindo ao TS-2000 "+("MAIN TX / SUB RX" if target else "MAIN RX / SUB TX")+"…")
        def task():
            return self.radio.set_orientation(main_downlink=not target),ident,target
        self.background("cat-swap",task)

    def track_cat_frequencies(self,now):
        """Prioritize changed Doppler frequencies over optional CAT telemetry."""
        note=getattr(self,"cat_tracking_gate",None)
        if not self.cat_tracking_armed or not self.config.values.get("cat_auto_select",True):
            if callable(note):note("desabilitado")
            return False
        rx_only=bool(self.config.values.get("rx_only",False))
        if not self.radio.connected or (not self.radio.state.sat and not rx_only):
            if callable(note):note("desconectado ou SAT OFF")
            self.cat_tune_status.setText("CAT: rastreamento pausado · desconectado ou SAT OFF")
            return False
        if not self.sat or not self.last_pos or not self.omm_fresh():
            if callable(note):note("aguardando satélite/posição/OMM válido")
            return False
        if (self.last_freqs==(None,None)
                and time.monotonic()>=self.cat_retry_after
                and self.down_edit.text().strip()
                and "cat-autotune" not in self.pending_jobs):
            # When a saved/updated catalog becomes ready, initiate once.
            if callable(note):note("sintonia inicial pendente")
            self.auto_tune_selected_satellite()
            return False
        if self.last_freqs==(None,None):
            if callable(note):note("aguardando primeira confirmação CAT/backoff")
            return False
        busy=tuple(k for k in ("cat-autotune","cat-track","cat-readback","cat-connect","cat-diagnostic")
                   if k in self.pending_jobs)
        if busy:
            if callable(note):note("worker pendente: "+",".join(busy))
            return False
        # Operator-enabled Auto CAT tracks Doppler regardless of elevation.
        # The initial preset must not succeed below the horizon while later
        # corrections are silently blocked by a legacy visibility preference.
        # Readback FA/FB remains authoritative for hardware confirmation.
        if time.monotonic()<getattr(self,"cat_retry_after",0.0):
            if callable(note):note("aguardando backoff de falha CAT")
            return False
        if time.monotonic()-self.last_tracking_write < max(0.25,float(
                self.interval.value())):
            if callable(note):note("aguardando intervalo de atualização CAT")
            return False
        if rx_only:
            return self._track_rx_only(note)
        try:
            ul,dl=self.corrected()
            safe,reason=self.selected_cat_pair_info(ul,dl)
            if not safe:
                self.cat_tracking_armed=False
                self.cat_tune_status.setText("CAT: acompanhamento bloqueado · "+reason)
                if callable(note):note("perfil CAT inseguro: "+reason)
                return False
            threshold=max(1,int(self.threshold.value()))
            # v1.3.11: 'last_freqs' is only what this program previously
            # requested. Real FA/FB may change by physical tuning, another
            # CAT client, or an incomplete CAT write. Reconcile against the
            # last *actual* SA/FA/FB readback as well, never just the request.
            last_request_delta=max(abs(ul-self.last_freqs[0]),
                                   abs(dl-self.last_freqs[1]))
            observed=self.radio.state
            observed_delta=(
                max(abs(ul-observed.uplink),abs(dl-observed.downlink))
                if observed.uplink is not None and observed.downlink is not None
                else None)
            if (last_request_delta<threshold
                    and observed_delta is not None and observed_delta<threshold):
                if callable(note):note("Doppler dentro do limiar: "+str(threshold)+" Hz")
                return False
            generation=self.cat_selection_generation
            self.last_tracking_write=time.monotonic()
            self.cat_last_requested=(ul,dl)
            started=self.last_tracking_write
            self.cat_tune_status.setText("Auto CAT · corrigindo Doppler no TS-2000…")
            self.log(f"Auto CAT Doppler · elevação {self.last_pos.get('elevation', float('nan')):+.1f}°"
                     f" · RX {dl} Hz · TX {ul} Hz · diferença CAT {observed_delta} Hz")
            def task():
                if generation!=self.cat_selection_generation or not self.radio.connected:
                    return generation,None,None,None,0.0
                state=self.radio.set_frequencies(ul,dl)
                return generation,state,ul,dl,time.monotonic()-started
            if callable(note):note("enviando novo setpoint Doppler FA/FB")
            self.cat_tracking_commands=getattr(self,"cat_tracking_commands",0)+1
            self.background("cat-track",task)
            return True
        except (ValueError,TypeError,KeyError) as exc:
            self.cat_tune_status.setText("CAT rastreio aguardando: "+str(exc))
            if callable(note):note("falha no cálculo Doppler: "+str(exc))
            return False

    def cat_live_tick(self):
        """High-priority CAT scheduler, independent of full GUI/map refresh.

        Update orbital Doppler even when the main map is rendering. One write
        worker at a time; the radio readback always determines SYNC status.
        """
        if (not self.cat_tracking_armed
                or not self.config.values.get("cat_auto_select",False)
                or not self.radio.connected or not self.sat):
            return
        try:
            now=now_utc()
            self.last_pos=position(self.sat,self.saved_station(),when=now,ts=self.ts)
            # Do not update Qt widgets at the 250 ms CAT scheduler cadence.
            moment=time.monotonic()
            if moment-getattr(self,"cat_last_preview_time",0.0)>=1.0:
                self.preview_doppler(pos=self.last_pos,when=now)
                self.cat_last_preview_time=moment
            if any(k in self.pending_jobs for k in
                   ("cat-readback","cat-autotune","cat-track","cat-connect","cat-diagnostic")):
                return
            # A fresh prediction that differs from FA/FB has priority over a
            # routine readback: the old readback-first path could delay writes.
            self.track_cat_frequencies(now)
            if "cat-track" in self.pending_jobs or "cat-autotune" in self.pending_jobs:
                return
            if (self.last_freqs!=(None,None)
                    and moment-max(getattr(self,"last_cat_readback_requested",0.0),
                                   self.last_cat_frequency_readback)>=1.0):
                self.last_cat_readback_requested=moment
                self.background("cat-readback",self.radio.poll_tracking)
        except Exception as exc:
            self.cat_sync_status.setText("CAT SYNC · previsão indisponível: "+str(exc)[:105])
            note=getattr(self,"cat_tracking_gate",None)
            if callable(note):note("exceção no ciclo CAT: "+str(exc)[:100])

    def update_cat_sync_status(self,state):
        """Compare current Doppler calculation with read FA/FB, not old TX intent."""
        if not hasattr(self,"pred_cat_status"):
            # Minimal test fixtures or older UI embedding may omit this label.
            self.pred_cat_status=self.cat_sync_status
        if not state.sat:
            message="CAT INATIVO · modo SAT OFF no TS-2000; Auto CAT não pode sintonizar"
            self.cat_sync_status.setText(message)
            self.pred_cat_status.setText(message)
            return
        if state.uplink is None or state.downlink is None:
            message="CAT SEM LEITURA · aguardando resposta FA/FB"
            self.cat_sync_status.setText(message)
            self.pred_cat_status.setText(message)
            return
        try:
            ul,dl=self.corrected()
        except (ValueError,TypeError,KeyError) as exc:
            message="CAT · frequência prevista indisponível: "+str(exc)
            self.cat_sync_status.setText(message)
            self.pred_cat_status.setText(message)
            return
        rx_delta=dl-state.downlink
        tx_delta=ul-state.uplink
        lag="—" if self.cat_last_roundtrip_ms is None else str(self.cat_last_roundtrip_ms)+" ms"
        threshold=max(1,int(self.threshold.value()))
        synced=max(abs(rx_delta),abs(tx_delta))<threshold
        # The status is specific to the *current* selected transponder, not
        # the last frequency that was sent or an old "sync" result.
        status=("SINCRONIZADO" if synced else "DIVERGENTE")
        age=time.monotonic()-getattr(self,"last_cat_frequency_readback",0.0)
        fresh=age<2.5
        if not fresh:
            status="AGUARDANDO READBACK FA/FB"
        summary=(
            f"CAT {status} · previsto menos rádio: RX {rx_delta:+d} Hz · "
            f"TX {tx_delta:+d} Hz")
        self.pred_cat_status.setText(summary)
        self.pred_cat_status.setStyleSheet(
            "font-size:12px;font-weight:700;color:"+
            ("#69e3bc" if synced and fresh else "#efc17b"))
        self.cat_sync_status.setText(
            summary+f" · FA {state.downlink/1e6:.6f} / FB {state.uplink/1e6:.6f} MHz "
            f"· último comando {lag}")


    def diagnose_cat(self):
        """Operator-initiated read-only TS-2000 serial CAT probe."""
        if not self.radio.connected:
            QMessageBox.warning(self,"Diagnóstico CAT","Rádio não conectado.")
            return
        if "cat-diagnostic" in self.pending_jobs:
            return
        self.cat_diagnose.setEnabled(False)
        self.cat_tune_status.setText("CAT: consultando somente ID / SA / FA / FB / FC / MD…")
        self.log("Diagnóstico CAT: início da leitura de ID, SA, FA, FB, FC e MD; sem comandos de escrita")
        self.background("cat-diagnostic",self.radio.read_diagnostics)

    def show_cat_diagnostic(self,diag):
        """Show exact protocol evidence without claiming hardware compatibility."""
        raw=diag["raw"]
        errors=diag["errors"]
        status=diag["sat"]
        freq=diag["frequency_hz"]
        parts=["TESTE CAT SOMENTE LEITURA · TS-2000",
               "Porta COM: "+self.ports.currentText().strip(),
               "Nenhuma alteração de frequência, modo SAT ou PTT foi enviada.",
               "",
               "RESPOSTAS BRUTAS:"]
        for command in ("ID","SA","FA","FB","FC","MD"):
            parts.append(command+"; → "+str(raw.get(command,"SEM RESPOSTA")))
        parts.append("")
        if status:
            parts.append("SAT: "+("ON" if status["sat"] else "OFF"))
            parts.append("Direção: "+("MAIN=RX/downlink · SUB=TX/uplink" if status["main_downlink"]
                                     else "MAIN=TX/uplink · SUB=RX/downlink (inverso)"))
            parts.append("Canal SAT: "+str(status["channel"]))
            parts.append("TRACE: "+("ON" if status["trace"] else "OFF"))
            if status["sat"] and not status["main_downlink"]:
                parts.append("ALERTA: SA P3=0; Auto CAT bloqueado por orientação inversa.")
        else:
            parts.append("SA não interpretável; conferir comunicação CAT.")
        if "FA" in freq:
            parts.append("FA real: "+self.radio_freq(freq["FA"]))
        if "FB" in freq:
            parts.append("FB · uplink SAT / VFO B: "+self.radio_freq(freq["FB"]))
        if "FC" in freq:
            parts.append("FC · VFO do sub-receptor (não é uplink SAT): "+self.radio_freq(freq["FC"]))
        parts.append("Modo MAIN: "+str(diag["main_mode"] or "indisponível"))
        if errors:
            parts.extend(["","ERROS DE LEITURA:"]+[k+": "+v for k,v in errors.items()])
        report="\n".join(parts)
        self.log("CAT diagnóstico resultado:\n"+report)
        self.cat_tune_status.setText(
            "CAT: diagnóstico com falhas · veja LOGs / CAT" if errors else
            ("CAT: SAT ON, orientação MAIN/SUB inversa · leia diagnóstico"
             if status.get("sat") and not status.get("main_downlink") else
             "CAT: leitura FA/FB/FC/MD concluída · veja LOGs / CAT"))
        QMessageBox.information(self,"Diagnóstico CAT · somente leitura",report)

    def auto_tune_selected_satellite(self,force=False):
        """Set the selected satellite frequency once, then track Doppler each second.

        Persisted Auto CAT preference authorizes writes only under SAT and safety gates.
        """
        if not force and not self.config.values.get("cat_auto_select",False):
            return False
        def blocked(reason):
            self.cat_tune_status.setText("CAT: "+reason)
            self.log("CAT não sintonizado: "+reason)
            if force:
                QMessageBox.warning(self,"Sintonia CAT indisponível",reason)
            return False
        if not self.radio.connected:
            return blocked("rádio desconectado")
        if not self.sat or not self.sat_combo.currentData():
            return blocked("selecione um satélite no menu superior")
        if not self.radio.state.sat and not self.config.values.get("rx_only",False):
            return blocked("SAT está OFF no TS-2000; ative em Configurações → Conexão CAT")
        if not self.omm_fresh():
            return blocked("OMM/TLE vencido; atualize elementos orbitais antes de sintonizar")
        if "cat-autotune" in self.pending_jobs:
            self.cat_tune_status.setText("CAT: nova seleção aguardando sintonia anterior…")
            return False
        if time.monotonic()<self.cat_retry_after:
            return False
        try:
            ul,dl=self.nominal_hz()
            safe,reason=self.selected_cat_pair_info(ul,dl)
            if not safe:
                return blocked("Perfil não sintonizado: "+reason)
            station=self.saved_station()
            pos=position(self.sat,station,ts=self.ts)
            if ul is not None:
                ul_new,dl_new=doppler_frequencies(ul,dl,pos["radial_m_s"])
            else:
                ul_new=None
                dl_new=frequency_prediction(
                    {"downlink_hz":dl,"uplink_hz":None},pos["radial_m_s"])["rx_hz"]
            mode=self.rx_mode.currentText()
            if mode not in ("FM","USB","LSB","CW","AM","FSK"):
                return blocked("modo RX não suportado pelo TS-2000")
            generation=self.cat_selection_generation
            self.cat_autotune_requested_generation=generation
            self.cat_tune_manual_request=bool(force)
            self.cat_tune_status.setText("CAT: sintonizando RX/TX e modo MAIN…")
            self.log(f"Auto CAT: solicitação NORAD {self.sat_combo.currentData()} "
                     f"RX {dl_new} TX {ul_new or 'somente RX'} MAIN {mode}")
            def task():
                if generation!=self.cat_selection_generation or not self.radio.connected:
                    return generation,None
                if self.config.values.get("rx_only",False):
                    return generation,self.radio.set_rx_only(dl_new,mode)
                return generation,self.radio.set_satellite_channel(dl_new,ul_new,mode)
            self.background("cat-autotune",task)
            return True
        except Exception as exc:
            return blocked(str(exc))

    def pair_linear(self):
        i=self.mode_combo.currentData()
        if not isinstance(i,int) or i<0 or i>=len(self.options):return
        opt=self.options[i]
        if opt['uplink'] is None or opt['downlink_high']<=opt['downlink'] or opt['uplink_high']<=opt['uplink']:return
        try:
            dl=round(float(self.down_edit.text().replace(',','.'))*1e6)
            ul=paired_linear_uplink(dl,opt['downlink'],opt['downlink_high'],opt['uplink'],opt['uplink_high'],opt['inverted'])
            self.up_edit.setText(f"{ul/1e6:.6f}")
            self.preview_doppler()
        except ValueError:pass

    def radio_freq(self,hz):
        return frequency_label(hz,self.config.values.get("frequency_style","radio10"))

    def suspend_cat_doppler(self,reason):
        """Selection changes may update predictions but never silently retune VFOs."""
        if self.doppler_checkbox.isChecked():
            self.doppler_checkbox.blockSignals(True)
            self.doppler_checkbox.setChecked(False)
            self.doppler_checkbox.blockSignals(False)
            self.log("Doppler CAT suspenso: "+reason+"; nova autorização necessária")
            self.mode_note.setText("CAT Doppler suspenso: "+reason+" · reative após conferir RX/TX")

    def preview_doppler(self,pos=None,when=None):
        """Continuous RX/TX prediction, including below horizon, never writes CAT."""
        try:
            if not self.sat:
                raise ValueError("Selecione um satélite")
            when=when or now_utc()
            p=pos if pos is not None else position(self.sat,self.saved_station(),when=when,ts=self.ts)
            self.last_pos=p
            ul,dl=self.nominal_hz()
            from .operations import frequency_prediction
            calc=frequency_prediction({"downlink_hz":dl,"uplink_hz":ul},p["radial_m_s"])
            age=abs((when-self.sat.epoch.utc_datetime().replace(tzinfo=timezone.utc)).total_seconds())/86400
            if age>7:
                self.pred_rx.setText("RX / DOWNLINK\nTLE/OMM antigo\nAtualize órbitas")
                self.pred_tx.setText("TX / UPLINK\nTLE/OMM antigo\nAtualize órbitas")
                self.corrected_label.setText(f"Previsão indisponível: efeméride antiga ({age:.1f} dias)")
                return
            rx_mode=self.rx_mode.currentText()
            tx_mode=self.tx_mode.currentText()
            self.pred_rx.setText(
                f"RX / DOWNLINK · {rx_mode}\n{self.radio_freq(calc['rx_hz'])}")
            self.pred_tx.setText(
                f"TX / UPLINK · {tx_mode}\n{self.radio_freq(calc['tx_hz'])}"
                if ul is not None else "TX / UPLINK\nSOMENTE RECEPÇÃO\nSem frequência TX")
            self.lcd.set_state(rx_hz=int(calc['rx_hz']),rx_mode=rx_mode,
                               tx_hz=int(calc['tx_hz']) if ul is not None else None,tx_mode=tx_mode,
                               doppler_hz=int(calc['rx_offset_hz']),elevation=float(p['elevation']),
                               visible=bool(p['visible']),auto=bool(self.cat_tracking_armed),
                               rx_only=bool(self.config.values.get("rx_only",False)),
                               sat_name=self.sat_combo.currentText())
            self.lcd.setToolTip(f"RX nominal {self.radio_freq(dl)}"
                                +(f" · TX nominal {self.radio_freq(ul)}" if ul is not None else " · somente recepção")
                                +" · A/B inverte MAIN↔SUB · RX ONLY opera só em recepção")
            self.pred_rx.setToolTip("Frequência nominal: "+self.radio_freq(dl))
            self.pred_tx.setToolTip("Frequência nominal: "+self.radio_freq(ul) if ul is not None else "Canal somente recepção")
            tx=("TX "+self.radio_freq(calc["tx_hz"])+f" ({calc['tx_offset_hz']:+d} Hz)") if ul is not None else "RX apenas"
            self.corrected_label.setText(
                f"PREVISÃO · RX nominal {self.radio_freq(dl)} | "
                f"{'TX nominal '+self.radio_freq(ul) if ul is not None else 'sem uplink'} · "
                f"{'EM PASSAGEM' if p['visible'] else 'FORA DA VISADA'} · "
                f"{when.astimezone():%H:%M:%S} · CAT independente")
        except (ValueError,TypeError,KeyError) as exc:
            self.pred_rx.setText("RX / DOWNLINK\nAguardando frequência")
            self.pred_tx.setText("TX / UPLINK\nAguardando frequência")
            self.corrected_label.setText("Previsão Doppler: "+str(exc))
        except Exception as exc:
            self.pred_rx.setText("RX / DOWNLINK\nPrevisão indisponível")
            self.pred_tx.setText("TX / UPLINK\nPrevisão indisponível")
            self.corrected_label.setText("Previsão Doppler indisponível")
            self.log("Previsão Doppler: "+str(exc))

    def nominal_hz(self):
        try:dl=parse_mhz_input(self.down_edit.text())
        except ValueError:raise ValueError('Informe a frequência nominal de RX')
        try:ul=parse_mhz_input(self.up_edit.text()) if self.up_edit.text().strip() else None
        except ValueError:raise ValueError('Frequência nominal de TX inválida')
        if not (100000<=dl<=1_299_999_999):raise ValueError("Downlink fora do intervalo CAT")
        if ul is not None and not (100000<=ul<=1_299_999_999):raise ValueError("Uplink fora do intervalo CAT")
        if self.config.values.get("rx_only",False):
            ul=None  # v1.6.0: Somente RX — nenhum uplink é calculado nem enviado
        return ul,dl

    def corrected(self):
        ul,dl=self.nominal_hz()
        if ul is None:raise ValueError('Não há uplink definido; modo somente recepção')
        if not self.last_pos:raise ValueError('Aguardando cálculo Doppler / localização')
        return doppler_frequencies(ul,dl,self.last_pos['radial_m_s'])

    def apply_freqs(self, silent=False):
        try:
            if not self.radio.connected:raise ConnectionError('Conecte o TS-2000')
            uplink,downlink=self.corrected()
            if not silent:
                msg=f"Programar RX {downlink/1e6:.6f} MHz / TX {uplink/1e6:.6f} MHz, sem transmitir?"
                if QMessageBox.question(self,"Aplicar CAT",msg)!=QMessageBox.Yes:return
            st=self.radio.set_frequencies(uplink,downlink)
            self.last_freqs=(uplink,downlink)
            self.render_radio_state(st)
        except Exception as exc:
            if silent:
                self.doppler_checkbox.setChecked(False)
                self.log('Doppler interrompido: '+str(exc))
            else:QMessageBox.warning(self,'CAT - frequências',str(exc))

    def apply_rx_mode(self):
        try:
            if QMessageBox.question(self,'CAT modo','Alterar o modo atual da banda MAIN (RX)?')!=QMessageBox.Yes:return
            self.render_radio_state(self.radio.set_main_mode(self.rx_mode.currentText()))
        except Exception as exc:QMessageBox.warning(self,'CAT modo',str(exc))

    def doppler_state_changed(self):
        if self.doppler_checkbox.isChecked():
            try:
                rx_only=bool(self.config.values.get("rx_only",False))
                self.saved_station()
                if not rx_only:self.corrected()
                if not self.radio.connected or (not self.radio.state.sat and not rx_only):
                    raise ValueError("Conecte ao TS-2000 e ative SAT antes de habilitar o Doppler")
                if not self.omm_fresh():
                    raise ValueError('OMM antigo: atualize antes de controlar o rádio automaticamente')
                if QMessageBox.question(self,'Ativar Doppler','Permitir alterar periodicamente FA/FB, inclusive fora da visada?') != QMessageBox.Yes:
                    raise ValueError('Operação cancelada')
                self.log('Doppler automático habilitado pelo operador')
            except Exception as exc:
                self.doppler_checkbox.blockSignals(True);self.doppler_checkbox.setChecked(False)
                self.doppler_checkbox.blockSignals(False)
                self.log(f'Doppler não habilitado: {exc}')
                if str(exc)!='Operação cancelada':QMessageBox.warning(self,'Doppler indisponível',str(exc))
        else:
            self.log('Doppler automático desabilitado')

    def omm_fresh(self):
        if self.sat is None:return False
        age=abs((now_utc()-self.sat.epoch.utc_datetime().replace(tzinfo=timezone.utc)).total_seconds()/86400)
        return age<=7

    def trail_changed(self,*args):
        period=self.trail_period.currentText()
        self.trail_custom.setVisible(period=="Personalizado")
        self.config.values.update({
            "trail_period":period,"trail_direction":self.trail_direction.currentText(),
            "trail_custom_hours":float(self.trail_custom.value())})
        self.config.save()
        self.track_cache_key=None
        self.update_map()

    def requested_track_period(self):
        period=self.trail_period.currentText()
        direction=self.trail_direction.currentText()
        hours=float(self.trail_custom.value()) if period=="Personalizado" else float(period.split()[0]) if period!="Última passagem" else 2.0
        return hours, ("Última passagem" if period=="Última passagem" else direction)

    def refresh_track_async(self):
        if self.sat is None:return
        ident=str(self.sat_combo.currentData())
        span,direction=self.requested_track_period()
        timestamp=now_utc()
        key=(ident,span,direction,int(timestamp.timestamp()//300))
        if key==self.track_cache_key or "trail" in self.pending_jobs:return
        self.track_pending_key=key
        sat=self.sat
        try:site=self.saved_station()
        except Exception:return
        def work():
            last_pass=None
            if direction=="Última passagem":
                recent=predict_passes(sat,site,now=timestamp-timedelta(hours=26),hours=26,ts=self.ts)
                completed=[p for p in recent if p["los"]<=timestamp]
                last_pass=completed[-1] if completed else None
            old_bounds,future_bounds=track_period_bounds(timestamp,span,direction,last_pass)
            past=ground_track_between(sat,*old_bounds,ts=self.ts) if old_bounds else []
            future=ground_track_between(sat,*future_bounds,ts=self.ts) if future_bounds else []
            caption="Última passagem reconstruída" if last_pass is not None else "Histórico reconstruído + previsão por OMM"
            return key,past,future,caption
        self.background("trail",work)

    def select_next_candidate(self):
        event=self.next_candidate
        if not event:return
        ident=str(event["id"])
        self.search.clear()
        index=self.sat_combo.findData(ident)
        if index<0:return
        self.sat_combo.setCurrentIndex(index)
        self.arm_cat_tracking()
        ch=event["channel"]
        for i,option in enumerate(self.options):
            # Match the operating service without applying any CAT command.
            if option.get("downlink")==ch["downlink_hz"] or (
                    option.get("downlink",0)<=ch["downlink_hz"]<=option.get("downlink_high",0)):
                self.mode_combo.setCurrentIndex(i+1)
                break

    def update_next_indicator(self):
        now=now_utc()
        try:site=self.saved_station()
        except Exception:
            self.next_candidate=None
            self.next_select.setEnabled(False)
            self.next_event_label.setText("Cadastre latitude/longitude e escolha os modos da estação")
            self.next_countdown.setText("--:--:--")
            self.next_times.setText("AOS — · TCA — · LOS —")
            self.next_frequencies.setText("RX/TX: aguardando localização")
            self.pass_progress.setValue(0)
            return
        selected=str(self.sat_combo.currentData() or "")
        try:
            uplink,downlink=self.nominal_hz()
        except ValueError:
            uplink,downlink=None,None
        channel={"downlink_hz":downlink,"uplink_hz":uplink,
                 "rx_only":uplink is None,"mode":self.rx_mode.currentText(),
                 "name":self.mode_combo.currentText()}
        event=select_selected_satellite_pass(self.passes,selected,channel,now) if selected else None
        self.next_candidate=event
        # v1.7.0: contagem da passagem no display (mesmo AOS/LOS da tabela de passagens).
        if event is None:
            self.lcd.set_state(los_s=None,aos_s=None)
        elif event["in_progress"]:
            self.lcd.set_state(los_s=(event["los"]-now).total_seconds(),aos_s=None)
        else:
            self.lcd.set_state(los_s=None,aos_s=(event["aos"]-now).total_seconds())
        self.next_select.setEnabled(event is not None)
        if event is None:
            self.next_event_label.setText("Sem passagem compatível para o satélite selecionado")
            self.next_countdown.setText("--:--:--")
            self.next_times.setText("Consulte seleção FM/SSB/CW, bandas, elevação e dados SatNOGS")
            self.next_frequencies.setText("Sem dados de frequências compatíveis · não inferir uplink")
            self.pass_progress.setValue(0)
            return
        status,countdown=status_at(event,now)
        channel=event["channel"]
        self.next_event_label.setText(f'{status} · {event["name"]} · {channel["mode"]}'+
                                      (" · RX apenas" if channel["rx_only"] else " · RX/TX"))
        self.next_countdown.setText(countdown)
        if event["in_progress"]:
            self.next_event_label.setStyleSheet("font-size:14px;font-weight:800;color:#69e3bc")
        else:
            self.next_event_label.setStyleSheet("font-size:14px;font-weight:800;color:#70d8ed")
        fmt=lambda dt:dt.astimezone().strftime("%d/%m %H:%M:%S") if dt else "—"
        self.next_times.setText(f'AOS {fmt(event["aos"])} · TCA {fmt(event.get("tca"))} · LOS {fmt(event["los"])} · Máx {event["max_el"]:.0f}° (hora local)')
        progress=(now-event["aos"]).total_seconds()/max(1,(event["los"]-event["aos"]).total_seconds())
        self.pass_progress.setValue(round(max(0,min(1,progress))*1000))
        try:
            ident=event["id"]
            sat=self.plan_satellites.get(ident)
            if sat is None:
                sat=make_satellite(self.omm[ident],self.ts)
                self.plan_satellites[ident]=sat
            age=orbital_age_days(sat.epoch.utc_datetime().replace(tzinfo=timezone.utc),now)
            if age>7:
                self.next_frequencies.setText(f"OMM/TLE antigo ({age:.1f} dias); previsão Doppler indisponível. Atualize dados.")
                return
            if channel["downlink_hz"] is None:
                self.next_frequencies.setText(
                    "AOS/TCA/LOS calculados para o satélite selecionado · "
                    "informe downlink para previsão Doppler")
                return
            when=now if event["in_progress"] else event["aos"]
            radial=position(sat,site,when=when,ts=self.ts)["radial_m_s"]
            f=frequency_prediction(channel,radial)
            rx=f'RX {f["rx_hz"]/1e6:.6f} MHz ({f["rx_offset_hz"]:+d} Hz)'
            tx=f'TX {f["tx_hz"]/1e6:.6f} MHz ({f["tx_offset_hz"]:+d} Hz)' if f["tx_hz"] is not None else "TX indisponível (RX apenas)"
            moment="AGORA" if event["in_progress"] else "PREVISTO NO AOS"
            self.next_frequencies.setText(f'{moment} · {rx} · {tx} · TLE/OMM {age:.1f} d · apenas cálculo (CAT não acionado)')
        except Exception as exc:
            self.next_frequencies.setText(f"Doppler indisponível: {exc}")

    def refresh_passes(self):
        """Recalculate selected satellite passes in background; countdown is live.

        Refresh on satellite selection and every five minutes to avoid blocking
        the GUI. Ignore stale results when the selected NORAD changes.
        """
        if "passes" in self.pending_jobs:
            self._passes_refresh_again=True
            return
        try:
            station=self.saved_station()
        except Exception:
            self.pass_table.setRowCount(0)
            return
        ident=str(self.sat_combo.currentData() or "")
        if not ident or ident not in self.omm:
            self.pass_table.setRowCount(0)
            self.passes=[]
            self.next_candidate=None
            return
        self._pass_refresh_sat=ident
        self._pass_refresh_last=time.monotonic()
        self.pass_enabled={ident}
        self.pass_rows={ident:load_transmitters(self.config.dir,int(ident))}
        obj=dict(self.omm[ident])
        window=int(self.config.values.get("pass_window_hours",36) or 36)
        rows_tx=self.pass_rows[ident]
        alive=(True if any(r.get("alive") for r in rows_tx) else (False if rows_tx else None))
        mode=self.rx_mode.currentText()
        try:
            downlink=self.nominal_hz()[1]
        except Exception:
            downlink=None
        def task():
            try:
                from .quality import pass_quality
                sat=make_satellite(obj,self.ts)
                end=now_utc()+timedelta(hours=window)
                rows=predict_passes(sat,station,now=now_utc()-timedelta(hours=3),hours=window+3,ts=self.ts)
                out=[]
                for p in rows:
                    if p["los"]<=now_utc() or p["aos"]>end:
                        continue
                    item=dict(p,id=ident,name=obj.get("OBJECT_NAME",ident))
                    try:
                        item["quality"]=pass_quality(sat,station,p,self.ts,norad=ident,mode=mode,
                                                     downlink_hz=downlink,alive=alive)
                    except Exception:
                        item["quality"]=None
                    out.append(item)
                    if len(out)>=100:
                        break
                return out
            except Exception as exc:
                self.log("Agenda órbita "+ident+": "+str(exc))
                return []
        self.background("passes",task)

    def prefetch_upcoming_modes(self):
        """Download a small, bounded group of transmitter catalogs (not TLE) in background."""
        count=0
        for p in self.passes:
            sid=str(p["id"])
            if sid in self.tx_prefetch_started:
                continue
            # Respect local cache and avoid hammering SatNOGS (3 network queries per session).
            if age_hours(self.config.dir,f"tx_{sid}.json") is not None and age_hours(self.config.dir,f"tx_{sid}.json")<24:
                continue
            if count>=3 or len(self.tx_prefetch_started)>=6:
                break
            self.tx_prefetch_started.add(sid)
            count+=1
            self.background("tx:"+sid,lambda sid=sid:refresh_transmitters(self.config.dir,int(sid)))

    # ------------------------------------------------ popup de informações do satélite (v1.5.0)
    def request_satinfo(self,ident,name):
        ident=str(ident)
        if not hasattr(self,"satinfo"):
            self.satinfo={}
        if ident in self.satinfo or f"satinfo:{ident}" in self.pending_jobs:
            return
        from .satinfo import fetch_info, load_cached
        cached=load_cached(self.config.dir,ident)
        if cached:
            self.satinfo[ident]=cached
        lang=self.ui_language().split("-")[0]
        self.background(f"satinfo:{ident}",lambda:fetch_info(self.config.dir,ident,name,lang))

    def satinfo_html(self,ident,for_qt=True):
        from .satinfo import info_html
        ident=str(ident)
        info=getattr(self,"satinfo",{}).get(ident)
        obj=self.omm.get(ident,{})
        name=obj.get("OBJECT_NAME",ident)
        live=None;next_pass=None;transponders=None
        if self.sat is not None and ident==str(self.sat_combo.currentData() or ""):
            live=self.last_pos
            transponders=self.options
            upcoming=[p for p in self.passes if p["los"]>now_utc()]
            if upcoming:
                p=upcoming[0];q=p.get("quality")
                next_pass=(f"{p['aos'].astimezone():%d/%m %H:%M} · máx {p['max_el']:.0f}° · "
                           f"{format_duration(int((p['los']-p['aos']).total_seconds()))}"+(f" · {q.label}" if q else ""))
        else:
            try:
                transponders=transponder_options(load_transmitters(self.config.dir,int(ident)))
            except Exception:
                transponders=None
        return info_html(info,name=name,norad=ident,live=live,transponders=transponders,
                         next_pass=next_pass,for_qt=for_qt)

    def refresh_satinfo_tooltips(self,ident=None):
        current=str(self.sat_combo.currentData() or "")
        if current and (ident is None or ident==current):
            self.sat_combo.setToolTip(self.satinfo_html(current))
        if ident is not None:
            html=self.satinfo_html(ident)
            for row in range(self.catalog_table.rowCount()):
                item=self.catalog_table.item(row,0)
                if item is not None and str(item.data(Qt.UserRole))==ident:
                    for col in range(self.catalog_table.columnCount()):
                        cell=self.catalog_table.item(row,col)
                        if cell is not None:
                            cell.setToolTip(html)

    def catalog_item_hovered(self,item):
        ident=str(item.data(Qt.UserRole) or "")
        if ident and ident in self.omm:
            if ident in getattr(self,"satinfo",{}):
                self.refresh_satinfo_tooltips(ident)
            self.request_satinfo(ident,self.omm[ident].get("OBJECT_NAME",ident))

    def change_pass_window(self,*args):
        hours=int(self.pass_window.currentData() or 36)
        self.config.values["pass_window_hours"]=hours
        self.config.save()
        self.pass_group.setTitle(f"PASSAGENS DO SATÉLITE SELECIONADO · {hours} H" if hours<168 else
                                 "PASSAGENS DO SATÉLITE SELECIONADO · 7 DIAS")
        self.log(f"Janela de passagens: {hours} h")
        self.refresh_passes()

    def render_pass_table(self):
        """Preenche a tabela (cronológica ou por qualidade) sem recalcular as passagens."""
        from .passfmt import aos_label, time_label, full_tooltip
        from .alerts import find_alert
        rows=list(self.passes)
        if self.pass_sort.isChecked():
            rows.sort(key=lambda p:-(p.get("quality").score if p.get("quality") else -1))
        self._pass_rows_view=rows
        lang=self.ui_language()
        alerts=self.config.values.get("pass_alerts",[])
        self.pass_table.setRowCount(len(rows))
        for i,p in enumerate(rows):
            bell="🔔 " if find_alert(alerts,p['id'],p['aos']) else ""
            aos=bell+aos_label(p['aos'],lang=lang)
            peak=time_label(p.get('tca'),p['aos'])
            los=time_label(p['los'],p['aos'])
            modes=self.suggested_mode_text(p['id'])
            seconds=max(0,int((p['los']-p['aos']).total_seconds()))
            duration=format_duration(seconds)
            q=p.get("quality")
            stars=q.label if q else "—"
            tips=(full_tooltip(p['aos']),full_tooltip(p.get('tca')),full_tooltip(p['los']))
            for j,value in enumerate((aos,peak,los,duration,f"{p['max_el']:.0f}°",stars,modes)):
                cell=QTableWidgetItem(value)
                cell.setTextAlignment(Qt.AlignVCenter | (Qt.AlignLeft if j in (5,6) else Qt.AlignCenter))
                cell.setToolTip(q.tooltip if (j==5 and q) else tips[j] if j<3 else value)
                if j==5:
                    cell.setForeground(QBrush(QColor("#f2c94c")))
                if j==0:
                    cell.setData(Qt.UserRole,str(p['id']))
                self.pass_table.setItem(i,j,cell)
        self.pass_table.resizeRowsToContents()
        for i in range(self.pass_table.rowCount()):
            self.pass_table.setRowHeight(i,max(self.pass_table.rowHeight(i),
                self.pass_table.fontMetrics().height()+12))
        self.fit_pass_columns()

    def fit_pass_columns(self):
        """Cada coluna recebe a largura do conteúdo e a sobra é repartida entre todas (sem rolagem lateral)."""
        table=self.pass_table
        header=table.horizontalHeader()
        avail=table.viewport().width()
        if avail<=0 or table.columnCount()==0:
            return
        fm=header.fontMetrics()
        need=[]
        for col in range(table.columnCount()):
            title=table.horizontalHeaderItem(col).text() if table.horizontalHeaderItem(col) else ""
            content=table.sizeHintForColumn(col) if table.rowCount() else 0
            need.append(max(content,fm.horizontalAdvance(title)+18,header.minimumSectionSize()))
        total=sum(need)
        # v1.7.0: a tabela nunca rola na horizontal; a largura mínima do bloco é a soma das colunas e,
        # se faltar espaço, o mapa (à esquerda do divisor) é que cede largura.
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        minimum=total+table.verticalScrollBar().sizeHint().width()+2*table.frameWidth()+4
        if table.minimumWidth()!=minimum:
            table.setMinimumWidth(minimum)
        extra=max(0,avail-total)
        widths=[w+extra*w//max(1,total) for w in need]
        widths[-1]+=avail-sum(widths) if extra else 0
        if avail<total:   # transição antes do relayout: comprime proporcionalmente, sem rolagem
            widths=[max(header.minimumSectionSize(),w*avail//total) for w in need]
        for col,w in enumerate(widths):
            header.resizeSection(col,int(w))

    def eventFilter(self,obj,event):
        try:
            from PySide6.QtCore import QEvent
        except ImportError:
            from PySide2.QtCore import QEvent
        if obj is getattr(getattr(self,"pass_table",None),"viewport",lambda:None)() and event.type()==QEvent.Resize:
            QTimer.singleShot(0,self.fit_pass_columns)
        return super().eventFilter(obj,event)

    def pass_context_menu(self,pos):
        """Clique direito numa passagem: agendar avisos 30 min / 30 s antes do AOS."""
        from .alerts import add_alert, remove_alert, find_alert
        try:
            from PySide6.QtWidgets import QMenu
        except ImportError:
            from PySide2.QtWidgets import QMenu
        row=self.pass_table.rowAt(pos.y())
        view=getattr(self,"_pass_rows_view",self.passes)
        if not 0<=row<len(view):
            return
        p=view[row]
        alerts=self.config.values.setdefault("pass_alerts",[])
        menu=QMenu(self)
        title=menu.addAction(f"{p.get('name','')} · AOS {p['aos'].astimezone():%d/%m %H:%M}")
        title.setEnabled(False)
        a30m=menu.addAction("🔔 Avisar 30 minutos antes")
        a30s=menu.addAction("🔔 Avisar 30 segundos antes (contagem com som)")
        both=menu.addAction("🔔 Avisar nos dois")
        existing=find_alert(alerts,p['id'],p['aos'])
        remove=menu.addAction("Remover avisos desta passagem") if existing else None
        chosen=menu.exec(self.pass_table.viewport().mapToGlobal(pos)) if hasattr(menu,"exec") else menu.exec_(self.pass_table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is remove:
            remove_alert(alerts,p['id'],p['aos'])
            self.log(f"Avisos removidos: {p.get('name','')} {p['aos'].astimezone():%d/%m %H:%M}")
        elif chosen in (a30m,a30s,both):
            leads={a30m:(1800,),a30s:(30,),both:(1800,30)}[chosen]
            add_alert(alerts,p,leads)
            self.log(f"Aviso agendado: {p.get('name','')} AOS {p['aos'].astimezone():%d/%m %H:%M} · "
                     +", ".join("30 min" if x==1800 else f"{x} s" for x in leads))
        else:
            return
        self.config.save()
        self.render_pass_table()

    def check_pass_alerts(self,now):
        """Dispara os avisos agendados pelo clique direito (qualquer satélite, uma vez cada)."""
        from .alerts import due_alerts
        alerts=self.config.values.get("pass_alerts",[])
        if not alerts:
            return
        before=len(alerts)
        fired=due_alerts(alerts,now)
        if fired or len(alerts)!=before:
            self.config.save()
        for alert,lead in fired:
            aos=datetime.fromisoformat(alert["aos"])
            if lead<=120:
                if self.aos_alarm_dialog is None:
                    row={"name":alert["name"],"id":alert["norad"],"aos":aos,"max_el":alert.get("max_el",0)}
                    self._open_aos_countdown(row,(aos-now).total_seconds())
            else:
                minutes=max(0,round((aos-now).total_seconds()/60))
                text=(f"{alert['name']} passa em {minutes} min · AOS {aos.astimezone():%H:%M} · "
                      f"máx {alert.get('max_el',0):.0f}°")
                self.log("Aviso de passagem: "+text)
                self._notify_pass(alert,text)
            if fired:
                self.render_pass_table()

    def _notify_pass(self,alert,text):
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            if QSystemTrayIcon.isSystemTrayAvailable():
                if getattr(self,"_tray",None) is None:
                    self._tray=QSystemTrayIcon(self.windowIcon(),self);self._tray.show()
                self._tray.showMessage("PT2VHF Sat Tool · passagem",text)
        except Exception:
            pass
        box=QMessageBox(self)
        box.setWindowTitle("Aviso de passagem")
        box.setIcon(QMessageBox.Information)
        box.setText(text)
        box.setWindowModality(Qt.NonModal)
        box.setAttribute(Qt.WA_ShowWithoutActivating,True)
        go=box.addButton("Selecionar satélite",QMessageBox.AcceptRole)
        box.addButton("Fechar",QMessageBox.RejectRole)
        def chosen(button):
            if button is go:
                idx=self.sat_combo.findData(alert["norad"])
                if idx>=0:self.sat_combo.setCurrentIndex(idx)
                self.tabs.setCurrentIndex(0)
        box.buttonClicked.connect(chosen)
        box.show()

    def select_pass_satellite(self,row,col):
        view=getattr(self,"_pass_rows_view",self.passes)
        if 0<=row<len(view):
            ident=view[row]['id']
            self.search.clear()
            index=self.sat_combo.findData(ident)
            if index>=0:
                self.sat_combo.setCurrentIndex(index)
                self.arm_cat_tracking()

    @Slot(object,int)
    def web_renderer_terminated(self,status,exit_code):
        report_event(f"QtWebEngine renderer terminated: status={status}, code={exit_code}")
        self.log("Falha no processo do mapa (QtWebEngine); a página será recarregada")
        try:self.map.reload()
        except Exception as exc:report_exception("QtWebEngine reload",exc)

    def update_map(self):
        if self.sat is None:return
        try:
            station=self.saved_station()
            pos=position(self.sat,station,ts=self.ts)
            self.last_pos=pos
            self.refresh_track_async()
            circle=footprint(pos["sat_lat"],pos["sat_lon"],pos["footprint_radius_deg"])
            payload={"name":self.sat.name,
                     "satellite":{"lat":pos["sat_lat"],"lon":pos["sat_lon"],"height_km":pos["height_km"]},
                     "station":{"lat":station.lat,"lon":station.lon,"callsign":station.callsign},
                     "track_past":self.track_cache["past"] if self.track_cache_key and self.track_cache_key[0]==str(self.sat_combo.currentData()) else [],
                     "track_future":self.track_cache["future"] if self.track_cache_key and self.track_cache_key[0]==str(self.sat_combo.currentData()) else [],
                     "footprint":circle,
                     "label":f"{self.sat.name} · elevação {pos['elevation']:.1f}° · alcance {pos['range_km']:.0f} km · órbita TLE/OMM",
                     "info":self.satinfo_html(str(self.sat_combo.currentData() or ""),for_qt=False),
                     "antenna":self.rotor_map_payload(station)}
            self.sat_combo.setToolTip(self.satinfo_html(str(self.sat_combo.currentData() or "")))
            self.map.page().runJavaScript('window.updateOrbit && window.updateOrbit('+json.dumps(payload)+');')
            # A past error banner must not survive a successful map render.
            self.map_desc.setText("Trajetória passada reconstruída · futuro previsto por OMM/TLE · Natural Earth offline")
        except (ValueError,TypeError) as exc:
            self.map_desc.setText(f"Cadastre uma estação válida para calcular a órbita: {exc}")
        except Exception as exc:
            self.map_desc.setText(f"Erro ao atualizar a órbita: {exc}")
            self.log(f"Mapa/órbita: {exc}")

    def save_aos_lead(self,value):
        self.config.values['aos_alarm_lead_seconds']=int(value)
        self.config.save()

    def play_aos_sound(self,critical=False):
        '''Short synthetic WAV alarm; QtMultimedia on all platforms, Windows fallback.'''
        if not self.config.values.get('aos_alarm_sound',True):
            return
        try:
            path=self.config.dir/('aos_start.wav' if critical else 'aos_tick.wav')
            if not path.exists():
                rate=22050
                duration=0.32 if critical else 0.12
                freq=1100 if critical else 680
                samples=int(rate*duration)
                frames=bytearray()
                for i in range(samples):
                    envelope=min(1.0,i/250,(samples-i)/350)
                    value=int(14000*max(0,envelope)*math.sin(2*math.pi*freq*i/rate))
                    frames.extend(struct.pack('<h',value))
                with wave.open(str(path),'wb') as f:
                    f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(frames)
            try:
                if QT_BINDING=='PySide6':
                    from PySide6.QtMultimedia import QSoundEffect
                else:
                    from PySide2.QtMultimedia import QSoundEffect
                if self._alarm_sound_effect is None:
                    self._alarm_sound_effect=QSoundEffect(self)
                    self._alarm_sound_effect.setVolume(0.85)
                self._alarm_sound_effect.stop()
                self._alarm_sound_effect.setSource(QUrl.fromLocalFile(str(path)))
                self._alarm_sound_effect.play()
            except (ImportError,RuntimeError,OSError):
                if sys.platform=='win32':
                    import winsound
                    winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
                else:
                    QApplication.beep()
        except Exception as exc:
            self.log('AOS áudio indisponível: '+str(exc))
            QApplication.beep()

    def _clear_aos_dialog(self):
        self.aos_alarm_dialog=None
        self.aos_alarm_target=None
        self.aos_alarm_title=None
        self.aos_alarm_detail=None

    def _update_aos_countdown(self,now):
        if self.aos_alarm_dialog is None or self.aos_alarm_target is None:
            return
        _,row,_=self.aos_alarm_target
        remaining=math.ceil((row['aos']-now).total_seconds())
        if remaining < -4:
            self.aos_alarm_dialog.close()
            self._clear_aos_dialog()
            return
        if self.aos_alarm_title is not None:
            self.aos_alarm_title.setText(
                f"{row.get('name','Satélite')} · NORAD {row.get('id','')}\n"
                + (f'AOS em {remaining} s' if remaining>0 else 'AOS · PASSAGEM INICIADA'))
        if self.aos_alarm_detail is not None:
            self.aos_alarm_detail.setText(
                f"AOS {row['aos'].astimezone():%d/%m/%Y %H:%M:%S} local · "
                f"UTC {row['aos']:%H:%M:%S} · Máx {row.get('max_el',0):.0f}°")
        if remaining != self.aos_alarm_last_second:
            if not self.aos_alarm_silenced and remaining>=0:
                self.play_aos_sound(critical=(remaining==0))
            elif (not self.aos_alarm_silenced and remaining<0
                    and self.aos_alarm_last_second is not None
                    and self.aos_alarm_last_second>0):
                self.play_aos_sound(critical=True)
            self.aos_alarm_last_second=remaining

    def _open_aos_countdown(self,row,remaining,key=None):
        """Popup não modal com contagem regressiva e som (alarme do selecionado ou aviso agendado)."""
        found=(key or f"{row.get('id')}@{row['aos'].isoformat()}",row,remaining)
        self.aos_alarm_target=found
        self.aos_alarm_silenced=False
        self.aos_alarm_last_second=None
        dialog=QDialog(self)
        dialog.setWindowTitle('Alerta AOS · contagem regressiva')
        dialog.setWindowModality(Qt.NonModal)
        dialog.setAttribute(Qt.WA_ShowWithoutActivating,True)
        layout=QVBoxLayout(dialog)
        self.aos_alarm_title=QLabel()
        self.aos_alarm_title.setStyleSheet('font-size:21px;font-weight:800;color:#73eac9')
        self.aos_alarm_detail=QLabel()
        self.aos_alarm_detail.setWordWrap(True)
        layout.addWidget(self.aos_alarm_title)
        layout.addWidget(self.aos_alarm_detail)
        actions=QHBoxLayout()
        jump=QPushButton('Ir para Operação')
        mute=QPushButton('Silenciar')
        dismiss=QPushButton('Fechar')
        jump.clicked.connect(lambda:self.tabs.setCurrentIndex(0))
        mute.clicked.connect(lambda:setattr(self,'aos_alarm_silenced',True))
        dismiss.clicked.connect(dialog.close)
        for button in (jump,mute,dismiss):
            actions.addWidget(button)
        layout.addLayout(actions)
        dialog.finished.connect(lambda *_:self._clear_aos_dialog())
        self.aos_alarm_dialog=dialog
        self._update_aos_countdown(now_utc())
        dialog.show()

    def check_selected_aos_alarm(self,now):
        '''Read-only audible AOS countdown; never commands radio or CAT.'''
        if not self.config.values.get('aos_alarm_enabled',True):
            if self.aos_alarm_dialog is not None:
                self.aos_alarm_dialog.close()
                self._clear_aos_dialog()
            return
        if self.aos_alarm_dialog is not None:
            self._update_aos_countdown(now)
            return
        selected=self.sat_combo.currentData()
        seen=set(self.config.values.get('aos_alarm_fired',[]))
        lead=int(self.config.values.get('aos_alarm_lead_seconds',10))
        found=selected_aos_alarm(self.passes,selected,now,seen,lead)
        if found is None:
            return
        key,row,remaining=found
        self.config.values['aos_alarm_fired']=(list(seen)+[key])[-160:]
        self.config.save()
        self._open_aos_countdown(row,remaining,key)
        self.log(f'Alarme AOS: NORAD {selected} em {remaining:.0f} s')

    def tick(self):
        # No network calls in the GUI tick; asynchronous check respects the configured period.
        if int(now_utc().timestamp()) % 60 == 0:
            self.check_for_updates()
        if getattr(self,"_cat_scan_progress",""):
            self.cat_tune_status.setText(self._cat_scan_progress)
        now=now_utc();self.utc.setText(now.strftime('UTC · %d/%m %H:%M:%S'))
        self.utc.setToolTip(now.strftime('DATA/HORA UTC · %d/%m/%Y %H:%M:%S'))
        self.update_next_indicator()
        if (self.sat is not None and time.monotonic()-self._pass_refresh_last>=300
                and "passes" not in self.pending_jobs):
            self.refresh_passes()
        self.check_selected_aos_alarm(now)
        self.check_pass_alerts(now)
        try:
            self.rotor_tick(now)
        except Exception as exc:
            report_exception("rotor_tick",exc)
        self.poll_station_map()
        if self.sat:
            try:
                station=self.saved_station()
                pos=position(self.sat,station,ts=self.ts)
                self.last_pos=pos
                formats={'elevation':f"{pos['elevation']:.1f}°",'azimuth':f"{pos['azimuth']:.1f}°",
                         'range_km':f"{pos['range_km']:.0f} km",'radial_m_s':radial_kmh_text(pos['radial_m_s']),
                         'height_km':f"{pos['height_km']:.0f} km"}
                for k,v in formats.items():self.orbit_metrics[k].setText(v)
                self.orbit_metrics['radial_m_s'].setToolTip(
                    f"{pos['radial_m_s']:+.1f} m/s · positivo = afastando, negativo = aproximando")
                self.visibility.setText('EM PASSAGEM' if pos['visible'] else 'ABAIXO DO HORIZONTE')
                self.visibility.setStyleSheet('font-size:18px;font-weight:800;color:'+('#5ae1a6' if pos['visible'] else '#e1c27c'))
                self.preview_doppler(pos=pos,when=now)
                if (self.last_map_time is None or (now-self.last_map_time).total_seconds()>=12):
                    self.update_map();self.last_map_time=now
            except Exception as exc:
                self.visibility.setText('Cadastre a estação')
                self.log("Falha ao atualizar órbita/Doppler da interface: "+str(exc))
        # Fast Auto CAT worker owns the COM port; full meter/FC polls are
        # independent and must not interleave with the live tuning loop.
        if self.radio.connected:
            active=self.cat_tracking_armed and self.config.values.get("cat_auto_select",False)
            interval=2.0 if active else max(1,int(self.config.values.get("poll_interval_s",1)))
            if (time.monotonic()-self.last_cat_poll_started>=interval
                    and not any(k in self.pending_jobs for k in (
                        "cat-connect","cat-autotune","cat-track","cat-readback","cat-diagnostic","cat-poll"))):
                self.last_cat_poll_started=time.monotonic()
                self.background("cat-poll",self.radio.poll_telemetry if active else self.radio.poll)
        if self.radio.connected and self.last_cat_success:
            age=(now-self.last_cat_success).total_seconds()
            if age>10:
                self.map_radio_label.setText(f"CAT sem leitura há {age:.0f}s · valores desatualizados")
                self.map_radio_label.setStyleSheet("color:#e3ad61;font-weight:700")
                self.cat_indicator.setText("CAT")
                self.cat_indicator.setToolTip(f"CAT sem resposta há {age:.0f}s · confira a porta")
                self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ffead3;background:#755225;border:1px solid #e0aa55")
                self.cat_status.setText(f"● CAT desatualizado há {age:.0f}s")
                self.cat_status.setStyleSheet("color:#efc17b;font-size:12px")
                self.cat_details.setText("Leitura CAT vencida · conferir cabo e porta COM")
                self.cat_live_label.setText(f"RÁDIO REAL (CAT) · última leitura há {age:.0f}s, não confirmada")
                self.cat_sat_orientation.setText("SAT: resposta CAT desatualizada")
                self.cat_telemetry.setText("Potência/medidores: dados desatualizados")
                for widget in (self.smeter_main,self.smeter_sub):
                    widget.setValue(0);widget.setFormat("sem leitura")

        self.publish_web_snapshot()

    def background_result(self,key,data):
        self.pending_jobs.discard(key)
        if self.rotor_result(key,data):
            return
        if key=="web-firewall":
            self._web_firewall=data
            self.web_refresh_diagnostics()
            return
        if key=="web-firewall-add":
            ok,msg,present=data
            self._web_firewall=present
            self.web_status.setText(msg)
            self.log('Web: '+msg)
            self.web_refresh_diagnostics()
            return
        if key=="rig":
            self.sdr_panel.rig_result(data)
            return
        if key=="cat-scan":
            self.cat_scan_finished(data)
            return
        if key=="cat-swap":
            state,ident,target=data
            self.config.values.setdefault("main_sub_swapped",{})[ident]=target
            self.config.save()
            self.lcd.set_state(swapped=target)
            self.last_freqs=(None,None)
            self.cat_selection_generation+=1
            self.radio.main_downlink_expected=not target
            self.cat_tune_status.setText("A/B: "+("MAIN TX / SUB RX" if target else "MAIN RX / SUB TX")+" confirmado pelo TS-2000")
            self.log("TS-2000: "+("MAIN TX / SUB RX" if target else "MAIN RX / SUB TX")+" confirmado")
            if self.cat_tracking_armed:
                self.auto_tune_selected_satellite()
            return
        if key.startswith("satinfo:"):
            ident=key.split(":",1)[1]
            self.satinfo[ident]=data
            self.refresh_satinfo_tooltips(ident)
            if ident==str(self.sat_combo.currentData() or ""):
                self.update_map()
            return
        if key.startswith('photo:'):
            if key.split(':')[1]==str(self.sat_combo.currentData()):
                self.photo.setHtml(photo_html(data),QUrl("https://commons.wikimedia.org/"))
            return
        if key in ("geo-ip","geo-gps"):
            self.apply_location_fix(data)
            return
        if key=='trail':
            track_key,past,future,description=data
            self.track_cache_key=track_key
            self.track_cache={"past":past,"future":future}
            self.map_desc.setText(description+" · Natural Earth offline")
            self.update_map()
            return
        if key=="omm-stage":
            index,total,group,count,errors=data
            dlg=self.orbit_progress_dialog
            if dlg:
                elapsed=time.monotonic()-(self.orbit_started_at or time.monotonic())
                eta=format_duration(eta_seconds(index,total,elapsed))
                dlg.setLabelText(
                    f"Categoria {index}/{total} · {group.upper()} · {count} satélites\n"
                    f"{round(index*100/max(total,1))}% · Tempo restante estimado: {eta}\n"
                    f"Tempo decorrido: {format_duration(elapsed)} · falhas {errors}")
                dlg.setValue(index)
            return
        if key=="tx-batch-item":
            ident,rows,index,total=data
            if rows is not None:
                self.pass_rows[ident]=rows
                if str(self.sat_combo.currentData())==ident:
                    self.choose_cached_modes(int(ident))
            status="falha" if rows is None else "sem dados" if not rows else "recebido"
            self.catalog_progress.setText(f"SatNOGS: {index}/{total} · {status} NORAD {ident}")
            if self.frequency_progress_dialog:
                elapsed=time.monotonic()-(self.frequency_started_at or time.monotonic())
                eta=format_duration(eta_seconds(index,total,elapsed))
                self.frequency_progress_dialog.setLabelText(
                    f"SatNOGS: {index} de {total} satélites · {round(100*index/total)}%\n"
                    f"NORAD {ident} · {status}\n"
                    f"Restante estimado: {eta} · Decorrido: {format_duration(elapsed)}")
                self.frequency_progress_dialog.setValue(index)
            return
        if key=="cat-connect":
            self._cat_after_scan=False
            self.cat_connecting=False
            self.cat_indicator.setEnabled(True)
            self.connection.setEnabled(True)
            self.connection.setText("Desconectar")
            self.cat_diagnose.setEnabled(True)
            self.last_cat_telemetry=now_utc()
            self.render_radio_state(data)
            self.cat_tune_status.setText("CAT conectado · verificando Auto CAT online")
            self.config.values.update({"port":self.radio.port.port,
                "baud":int(self.baud_combo.currentText()),
                "stopbits":int(self.stops_combo.currentText())})
            self.config.save()
            self.log("CAT: conectado e conferido por ID/SA/FA/FB/FC/MD")
            self.cat_tracking_armed=bool(self.config.values.get("cat_auto_select",False))
            self.last_freqs=(None,None)
            self.cat_autotune_requested_generation=-1
            if self.cat_tracking_armed and self.radio.state.sat and self.sat is not None:
                self.auto_tune_selected_satellite()
            elif not self.cat_tracking_armed:
                self.cat_tune_status.setText("Auto CAT desativado em Configurações")
            else:
                self.cat_tune_status.setText("Auto CAT aguardando SAT ON e satélite válido")
            return
        if key=="cat-track":
            generation,state,ul,dl,elapsed=data
            if state is not None and generation==self.cat_selection_generation:
                self.last_freqs=(ul,dl)
                self.last_cat_frequency_readback=time.monotonic()
                self.cat_consecutive_failures=0
                self.cat_retry_after=0.0
                self.last_cat_track_completed=time.monotonic()
                self.cat_tracking_confirmed=getattr(self,"cat_tracking_confirmed",0)+1
                self.log(f"Auto CAT confirmado · ajustes {self.cat_tracking_confirmed} · "
                         f"RX {dl} Hz · TX {ul} Hz")
                self.cat_last_roundtrip_ms=round(elapsed*1000)
                self.render_radio_state(state)
                self.update_cat_sync_status(state)
                self.cat_tune_status.setText("Auto CAT ONLINE · FA/FB confirmados · "
                                             +str(self.cat_last_roundtrip_ms)+" ms")
            return
        if key=="cat-readback":
            if self.radio.connected:
                self.last_cat_frequency_readback=time.monotonic()
                self.render_radio_state(data)
                self.update_cat_sync_status(data)
                if self.cat_tracking_armed and self.config.values.get("cat_auto_select",False):
                    # Immediately correct drift detected at the dial, even if
                    # predicted Doppler changed by less than the normal limit.
                    self.track_cat_frequencies(now_utc())
            return
        if key=="logs-export":
            path,count=data
            self.export_logs.setEnabled(True)
            self.log("Log local exportado: "+str(path))
            QMessageBox.information(self,"Exportação concluída",
                f"Arquivo salvo em:\\n{path}\\n\\n{count} arquivo(s) de histórico incluídos. "
                "O pacote pode conter indicativo, posição e comandos CAT; revise antes de compartilhar.")
            return
        if key=="cat-autotune":
            self.cat_tune_manual_request=False
            generation,state=data
            if generation==self.cat_selection_generation and state is not None:
                self.last_freqs=(state.uplink,state.downlink)
                self.last_cat_frequency_readback=time.monotonic()
                self.cat_consecutive_failures=0
                self.cat_retry_after=0.0
                self.cat_last_requested=(state.uplink,state.downlink)
                self.last_cat_track_completed=time.monotonic()
                self.last_tracking_write=0.0
                self.render_radio_state(state)
                self.update_cat_sync_status(state)
                self.cat_tune_status.setText("Auto CAT ONLINE · nova seleção confirmada · MAIN "+state.mode)
            elif (self.config.values.get("cat_auto_select",False) and self.radio.connected
                  and generation!=self.cat_selection_generation):
                self.auto_tune_selected_satellite()
            return
        if key=="tx-batch":
            self.refresh_catalog_freq.setEnabled(True)
            self.stop_catalog_freq.setEnabled(False)
            if self.frequency_progress_dialog:
                self.frequency_progress_dialog.close()
                self.frequency_progress_dialog=None
            self.refresh_satellite_table()
            self.refresh_tracked_table()
            self.refresh_passes()
            self.update_next_indicator()
            self.catalog_progress.setText(
                f"SatNOGS: {data['ok']}/{data['total']} com canais · "
                f"{data['no_data']} sem dados · {len(data['failed'])} falhas"
                +(" · cancelado" if data["cancelled"] else ""))
            for error in data["failed"][:20]:self.log("SatNOGS: "+error)
            QMessageBox.information(self,"Atualização de frequências concluída",
                self.catalog_progress.text()+"\nDetalhes das falhas na aba LOGs / CAT.")
            return
        if key=='cat-diagnostic':
            self.cat_diagnose.setEnabled(self.radio.connected)
            if self.radio.connected:
                self.show_cat_diagnostic(data)
            return
        if key=='cat-poll':
            if self.radio.connected and not any(
                    k in self.pending_jobs for k in ("cat-autotune","cat-track")):
                self.last_cat_telemetry=now_utc()
                self.render_radio_state(data)
                self.update_cat_sync_status(data)
            return
        if key=='update-check':
            start_download=self.manual_update_requested
            self.manual_update_requested=False
            self.available_update=data
            if data:
                self.version_btn.setText(f'Nova versão {data.version} · instalar')
                self.version_btn.setStyleSheet('background:#ae6616;color:white;border:1px solid #eda847')
                if start_download:
                    self.request_update(manual=True)
                elif (self.config.values.get('auto_update',True) and self.update_distribution
                      and self.update_distribution[1]!='Manual'):
                    self.try_auto_update(data)
                else:
                    self.maybe_prompt_update(data)
            else:
                self.version_btn.setText('Última versão')
                self.version_btn.setStyleSheet('background:#145a3d;color:#e6ffee')
            return
        if key=='update-download':
            self.update_ready(data)
            return
        if key=='omm':
            if self.orbit_progress_dialog:
                self.orbit_progress_dialog.close()
                self.orbit_progress_dialog=None
            self.populate_catalog(data)
            self.refresh_passes()
            self.log(f'Catálogo atualizado: {len(data)} objetos OMM')
        elif key.startswith('tx:'):
            ident=key.split(':')[1]
            if ident==self.sat_combo.currentData():
                self.choose_cached_modes(int(ident))
            self.refresh_tracked_table()
            if self.config.values.get("satellite_selection") is None:self.refresh_passes()
            self.log(f'Transponders SatNOGS atualizados para NORAD {ident}: {len(data)}')
            self.pass_rows[ident]=data
            self.update_next_indicator()
        elif key=='passes':
            if self._pass_refresh_sat!=str(self.sat_combo.currentData() or ""):
                self._passes_refresh_again=False
                self.refresh_passes()
                return
            self.passes=data[:100]
            from .alerts import sync_with_passes
            sync_with_passes(self.config.values.get("pass_alerts",[]),self.passes)
            self.render_pass_table()
            window=int(self.config.values.get("pass_window_hours",36) or 36)
            self.log(f'Previsão: {len(data)} passagens nas próximas {window} h (lista limitada a 100)')
            self.update_next_indicator()
            self.prefetch_upcoming_modes()
            if self._passes_refresh_again:
                self._passes_refresh_again=False
                self.refresh_passes()

    def background_error(self,key,message):
        self.pending_jobs.discard(key)
        self.log(f'Falha {key}: {message}')
        if self.rotor_failed(key,message):
            return
        if key in ("geo-ip","geo-gps"):
            self.location_status.setText(f"Localização não obtida: {message}. Coordenadas preservadas.")
            return
        if key=="tx-batch":
            self.refresh_catalog_freq.setEnabled(True)
            self.stop_catalog_freq.setEnabled(False)
            if self.frequency_progress_dialog:
                self.frequency_progress_dialog.close()
                self.frequency_progress_dialog=None
            self.catalog_progress.setText("SatNOGS: falha, cache anterior preservado")
            return
        if key=="cat-swap":
            self.cat_tune_status.setText("A/B não aplicado: "+message[:200])
            QMessageBox.warning(self,"Inverter MAIN↔SUB",message)
            return
        if key=="cat-connect":
            self.cat_connecting=False
            self.cat_indicator.setEnabled(True)
            self.connection.setEnabled(True)
            self.connection.setText("Conectar")
            self.cat_diagnose.setEnabled(False)
            self.cat_indicator.setText("CAT")
            self.cat_indicator.setToolTip("CAT indisponível · "+message[:160])
            self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ffe7e7;background:#783437;border:1px solid #db565e")
            from .cat import port_error_text
            friendly,advice=port_error_text(message,str(self.config.values.get("port","") or ""))
            friendly+=". "+("Confira COM, cabo, driver e Configurações." if "indisponível" in friendly else "Veja LOGs / CAT.")
            self.cat_tune_status.setText(friendly)
            self.cat_tune_status.setToolTip(message)
            self.log("CAT: falha ao conectar: "+message)
            if not self.cat_connect_was_startup:
                if not getattr(self,"_cat_after_scan",False):
                    # v1.5.0: porta salva falhou → procura o rádio nas demais portas
                    self.cat_tune_status.setText("Porta salva não respondeu · procurando o rádio…")
                    QTimer.singleShot(0,self.start_cat_scan)
                else:
                    self.show_cat_port_error(message)
            self._cat_after_scan=False
            return
        if key=="cat-readback":
            self.cat_consecutive_failures+=1
            self.cat_retry_after=time.monotonic()+min(
                8.0,0.5*2**min(4,self.cat_consecutive_failures))
            self.last_freqs=(None,None)
            self.cat_tune_status.setText(
                "CAT: leitura FA/FB falhou · reconecte a porta se necessário · "
                "tentativa automática em instantes")
            self.pred_cat_status.setText("CAT · leitura FA/FB não confirmada: "+message[:105])
            return
        if key=="cat-track":
            # A CAT timeout/readback mismatch must not silently turn off
            # automatic tracking forever. Back off, read current SAT/FA/FB
            # and reinitialize with fresh satellite/mode if still authorized.
            self.cat_consecutive_failures+=1
            self.cat_retry_after=time.monotonic()+min(8.0,0.5*2**min(4,self.cat_consecutive_failures))
            self.last_freqs=(None,None)
            self.cat_autotune_requested_generation=-1
            self.cat_tune_status.setText(
                f"CAT: resposta não confirmada · nova tentativa automática em "
                f"{max(1,round(self.cat_retry_after-time.monotonic()))} s · "+message[:110])
            self.log("CAT contínuo: falha recuperável, reconsultando SAT/FA/FB: "+message)
            if self.radio.connected and "cat-poll" not in self.pending_jobs:
                self.background("cat-poll",self.radio.poll_tracking)
            return
        if key=="logs-export":
            self.export_logs.setEnabled(True)
            QMessageBox.warning(self,"Erro ao exportar log",message)
            return
        if key=="cat-autotune":
            was_manual=self.cat_tune_manual_request
            self.cat_tune_manual_request=False
            # A failed write/readback is not a failed *connection*.  The radio
            # can still answer ID/SA/FA/FC after rejecting a requested tune.
            # Keep the connection indicator independent of tune status.
            self.cat_tune_status.setText("SINTONIA NÃO APLICADA: "+message)
            self.cat_tune_status.setToolTip(
                "O erro de sintonia não significa que a porta CAT desconectou. "
                "Detalhes: "+message)
            if self.radio.connected:
                self.log("CAT: verificando comunicação após falha de sintonia (somente leitura)")
                # Verify an actual response before changing any connection LED.
                # background() safely coalesces requests if polling is in progress.
                self.background("cat-poll",self.radio.poll)
            else:
                self.last_cat_success=None
                self.cat_indicator.setText("CAT")
                self.cat_indicator.setToolTip("CAT desconectado · clique para conectar")
                self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ffe7e7;background:#783437;border:1px solid #db565e")
            if was_manual:
                QMessageBox.warning(self,"Falha ao sintonizar TS-2000",
                                    "O rádio não confirmou a sintonia solicitada. "
                                    "Isso não significa, necessariamente, perda da conexão CAT.\n\n"
                                    +message+"\n\nVeja também LOGs / CAT.")
            self.cat_consecutive_failures+=1
            self.cat_retry_after=time.monotonic()+min(
                8.0,0.5*2**min(4,self.cat_consecutive_failures))
            self.last_freqs=(None,None)
            self.cat_autotune_requested_generation=-1
            if self.cat_tracking_armed and self.radio.connected:
                self.cat_tune_status.setText(
                    "CAT: sintonia pendente · tentando novamente automaticamente · "+message[:110])
            return
        if key=="cat-diagnostic":
            self.cat_diagnose.setEnabled(self.radio.connected)
            self.cat_tune_status.setText("CAT: diagnóstico falhou · "+message)
            QMessageBox.warning(self,"Falha no diagnóstico CAT",message)
            return
        if key=="cat-poll":
            self.cat_live_label.setText("RÁDIO REAL (CAT) · erro de leitura")
            self.cat_sat_orientation.setText("SAT: sem resposta atual")
            self.cat_indicator.setText("CAT")
            self.cat_indicator.setToolTip("CAT sem resposta atual · ver LOGs / CAT")
            self.cat_indicator.setStyleSheet("font-size:12px;font-weight:800;color:#ffead3;background:#755225;border:1px solid #e0aa55")
            self.map_radio_label.setText("CAT erro de leitura · dados desatualizados")
            self.map_radio_label.setStyleSheet("color:#e98b81;font-weight:700")
            self.cat_status.setText("● Erro de leitura CAT")
            self.cat_status.setStyleSheet("color:#e98b81;font-size:12px")
            self.cat_rx.setText("RX / DOWNLINK (CAT)\n—")
            self.cat_tx.setText("TX / UPLINK (CAT)\n—")
            self.cat_details.setText("Leitura falhou · confira LOGs / CAT")
        if key.startswith('update-'):
            self.version_btn.setText('Verificação indisponível')
            if self.update_dialog:
                self.update_dialog.close()
                self.update_dialog=None
            if key=='update-download' and getattr(self,'_auto_update_running',False):
                # v1.7.0: falha no OTA automático não repete em laço (nova tentativa em 6 h) nem bloqueia o uso.
                self._auto_update_running=False
                self._auto_update_failed={'version':getattr(self.available_update,'version',''),'at':time.time()}
                self.version_btn.setText('Atualização automática falhou · clique para tentar')
                self.log('Atualização automática falhou: '+message)
            elif key=='update-download' or self.manual_update_requested:
                QMessageBox.warning(self,'Falha de atualização',message)
            self.manual_update_requested = False
        if key=='passes' and self._passes_refresh_again:
            self._passes_refresh_again=False
            self.refresh_passes()
        if key=='trail':
            self.map_desc.setText(f"Falha no cálculo da trajetória: {message}")
        if key=='omm':
            if self.orbit_progress_dialog:
                self.orbit_progress_dialog.close()
                self.orbit_progress_dialog=None
            self.summary.setText('Sem atualização: usando cache OMM, se existente')
        if key.startswith('photo:') and key.split(':')[1]==str(self.sat_combo.currentData()):
            self.photo.setHtml(photo_html(None))

    def enabled_satellite_ids(self):
        c=self.config.values
        manual=c.get("satellite_selection")
        if manual is not None:
            return [str(n) for n in manual if str(n) in self.omm]
        # Never scan tens of thousands of SatNOGS files for automatic suggestions.
        rows={ident:load_transmitters(self.config.dir,int(ident))
              for ident in self.omm if ident in CANDIDATES}
        suggested=choose_satellites(self.omm,rows,c.get("radio_modes",[]),
                                    c.get("radio_bands",[]),c.get("satellite_selection"))
        # Seleção automática sempre inclui os satélites padrão presentes no catálogo.
        return list(dict.fromkeys([n for n in DEFAULT_SATELLITES if n in self.omm]+suggested))

    def suggested_mode_text(self,ident):
        c=self.config.values
        info=capability(ident,load_transmitters(self.config.dir,int(ident)),
                        c.get("radio_modes",[]),c.get("radio_bands",[]))
        return render_service(info["modes"])

    def filter_tracked_satellites(self,*args):
        """Hide only nonmatching rows; never modify stored checked NORAD IDs."""
        if not hasattr(self,"tracked_table"):return
        text=self.tracked_search.text() if hasattr(self,"tracked_search") else ""
        normalize=lambda value: "".join(c for c in unicodedata.normalize("NFKD",str(value).casefold())
                                         if not unicodedata.combining(c))
        query=normalize(text).strip()
        count=0
        for index in range(self.tracked_table.rowCount()):
            name=self.tracked_table.item(index,1)
            row_text=name.text() if name is not None else ""
            show=query in normalize(row_text)
            self.tracked_table.setRowHidden(index,not show)
            count+=int(show)
        enabled=len(self.enabled_satellite_ids()) if self.omm else 0
        if hasattr(self,"tracked_search_summary"):
            self.tracked_search_summary.setText(
                f"{count} resultados de {self.tracked_table.rowCount()} satélites · {enabled} habilitados")

    def refresh_tracked_table(self):
        if not hasattr(self,"tracked_table"):return
        self._loading_satellites=True
        try:
            selected=set(self.enabled_satellite_ids())
            query=normalized_satellite_search(self.tracked_search.text())
            rows=[(sid,obj) for sid,obj in self.omm.items()
                  if not query or query in satellite_search_text(sid,obj)]
            rows.sort(key=lambda p:p[1].get("OBJECT_NAME",""))
            self._tracked_result_count=len(rows)
            rows=rows[:350]
            self.tracked_table.setRowCount(len(rows))
            for i,(ident,obj) in enumerate(rows):
                checkbox=QTableWidgetItem("")
                checkbox.setFlags(checkbox.flags()|Qt.ItemIsUserCheckable)
                checkbox.setData(Qt.UserRole,ident)
                checkbox.setCheckState(Qt.Checked if ident in selected else Qt.Unchecked)
                self.tracked_table.setItem(i,0,checkbox)
                self.tracked_table.setItem(i,1,QTableWidgetItem(f'{obj.get("OBJECT_NAME",ident)} ({ident})'))
                info=capability(ident,load_transmitters(self.config.dir,int(ident)),
                                self.config.values.get("radio_modes",[]),
                                self.config.values.get("radio_bands",[]))
                self.tracked_table.setItem(i,2,QTableWidgetItem(f'{render_service(info["modes"])} · {info["notice"]}'))
        finally:
            self._loading_satellites=False
        self.filter_tracked_satellites()

    def satellite_checked(self,row,col):
        if self._loading_satellites or col!=0:return
        # Only the edited checkbox changes. Hidden/paged satellite selections
        # must never be erased by rebuilding the table from visible rows.
        item=self.tracked_table.item(row,0)
        if item is None:return
        ident=str(item.data(Qt.UserRole))
        ids=set(self.enabled_satellite_ids())
        if item.checkState()==Qt.Checked:ids.add(ident)
        else:ids.discard(ident)
        self.config.values["satellite_selection"]=sorted(ids)
        self.config.save()
        self.filter_sats(self.search.text())
        self.refresh_passes()
        self.filter_tracked_satellites()

    def bulk_select_satellites(self,select):
        self.config.values["satellite_selection"]=list(self.omm) if select else []
        self.config.save();self.refresh_tracked_table();self.filter_sats(self.search.text());self.refresh_passes()

    def restore_auto_selection(self):
        self.config.values["satellite_selection"]=None
        self.config.save();self.refresh_tracked_table();self.filter_sats(self.search.text());self.refresh_passes()

    def save_profile(self):
        modes=[name for name,w in self.station_modes.items() if w.isChecked()]
        bands=[name for name,w in self.station_bands.items() if w.isChecked()]
        if not modes or not bands:
            QMessageBox.warning(self,"Perfil inválido","Escolha ao menos um modo e uma banda.");return
        self.config.values.update({"radio_modes":modes,"radio_bands":bands})
        self.config.save();self.refresh_tracked_table();self.filter_sats(self.search.text());self.refresh_passes()

    def connect_from_settings(self):
        port=self.ports.currentText().strip()
        if not port:
            QMessageBox.warning(self,"Porta CAT","Selecione ou digite a porta COM.");return
        if self.radio.connected:
            QMessageBox.information(self,"CAT","Rádio já conectado; desconecte antes de alterar a porta.");return
        self.config.values.update({"radio_brand":"Kenwood","radio_model":"TS-2000","port":port})
        self.config.save()
        if self.ports.findText(port)<0:self.ports.addItem(port)
        self.ports.setCurrentText(port)
        self.toggle_connection()

    def set_alarm_option(self,name,enabled):
        self.config.values[name]=bool(enabled)
        self.config.save()

    def save_orbit_groups(self):
        chosen=[g for g,w in self.orbit_group_checks.items() if w.isChecked()]
        if not chosen:
            QMessageBox.warning(self,"Categorias","Selecione pelo menos uma categoria.")
            return
        self.config.values["orbit_groups"]=chosen
        self.config.save()
        self.refresh_catalog(force=True)

    def change_auto_cat(self,enabled):
        if enabled and QMessageBox.question(
            self,"Autorizar CAT automático",
            "O aplicativo acompanhará continuamente as frequências FA/FB conforme o Doppler, aproximadamente a cada segundo, enquanto conectado e com SAT ativo. Não transmite nem aciona PTT. Habilitar?",
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
            self.auto_cat.blockSignals(True)
            self.auto_cat.setChecked(False)
            self.auto_cat.blockSignals(False)
            enabled=False
        self.config.values["cat_auto_select"]=bool(enabled)
        self.config.save()
        if enabled:
            self.cat_tracking_armed=True
            self.last_freqs=(None,None)
            self.cat_autotune_requested_generation=-1
            self.auto_tune_selected_satellite()
        else:
            self.cat_tracking_armed=False
            self.cat_selection_generation+=1
            self.cat_tune_status.setText("Auto CAT desligado · frequências não serão alteradas automaticamente")

    def save_tle_settings(self):
        self.config.values["tle_update_hours"]=int(self.tle_hours.value())
        self.config.save();self.log("Intervalo de atualização orbital salvo.")

    def change_web_settings(self,*args):
        self.config.values['web_enabled']=self.web_enabled.isChecked()
        self.config.values['web_allow_lan']=self.web_lan.isChecked()
        self.config.values['web_port']=int(self.web_port.value())
        self.config.values['web_session_hours']=int(self.web_session_hours.value())
        controls=self.web_controls.isChecked()
        if controls and not self.config.values.get('web_pin_hash'):
            self.web_controls.blockSignals(True);self.web_controls.setChecked(False);self.web_controls.blockSignals(False)
            controls=False
            self.web_status.setText('Defina o PIN da estação antes de permitir controle pela rede.')
        self.config.values['web_controls']=controls
        self.config.save()
        self.stop_web_server()
        if self.web_enabled.isChecked():
            self.start_web_server()
        else:
            self.web_status.setText('Interface Web desativada')
            self.web_refresh_diagnostics()

    def web_save_pin(self):
        from .web_ui import pin_hash, valid_pin
        import secrets as _secrets
        pin=self.web_pin.text().strip()
        if not valid_pin(pin):
            self.web_status.setText('PIN inválido: use de 4 a 12 dígitos.')
            return
        salt=_secrets.token_hex(16)
        self.config.values['web_pin_salt']=salt
        self.config.values['web_pin_hash']=pin_hash(pin,salt)
        self.config.save()
        self.web_pin.clear()
        self.web_pin.setPlaceholderText('definido')
        if self.web_server is not None:
            self.web_server.pin_salt=salt
            self.web_server.pin_hash_value=self.config.values['web_pin_hash']
        self.web_status.setText('PIN da estação salvo.')
        self.log('Web: PIN da estação alterado')

    def stop_web_server(self):
        if self.web_server is not None:
            self.web_server.stop()
            self.web_server=None
        timer=getattr(self,'web_timer',None)
        if timer is not None:
            timer.stop()

    def start_web_server(self):
        if self.web_server is not None:
            return True
        c=self.config.values
        try:
            server=LocalStatusServer(
                lan=bool(c.get('web_allow_lan',False)),
                port=int(c.get('web_port',8094)),
                map_path=Path(__file__).with_name('map.html'),
                controls=bool(c.get('web_controls',False)) and bool(c.get('web_pin_hash')),
                pin_hash_value=c.get('web_pin_hash',''),pin_salt=c.get('web_pin_salt',''),
                session_hours=int(c.get('web_session_hours',8)))
            server.start()
            self.web_server=server
            self._web_events_seen=0
            if getattr(self,'web_timer',None) is None:
                self.web_timer=QTimer(self)
                self.web_timer.timeout.connect(self.web_tick)
            self.web_timer.start(500)
            self._web_firewall=None
            if server.lan and sys.platform=='win32':
                from .web_ui import firewall_rule_present
                self.background('web-firewall',lambda port=server.port:firewall_rule_present(port))
            self.publish_web_snapshot(force=True)
            access=server.url
            if not access:
                access=f'http://IP-DA-REDE:{server.port}/?key={server.key}'
            self.web_status.setText('Interface Web ativa · '+access)
            self.web_status.setToolTip('Link de acesso LAN com chave; não compartilhe fora da rede.')
            self.log('Painel Web iniciado · LAN habilitada' if server.lan else 'Painel Web local iniciado')
            if server.controls:
                self.log('Painel Web: controle pela rede habilitado (com PIN; PTT/TX nunca)')
            self.web_refresh_diagnostics()
            return True
        except (OSError,ValueError) as exc:
            self.web_server=None
            self.web_status.setText('Falha ao iniciar Web: '+str(exc))
            self.log('Falha ao iniciar painel Web: '+str(exc))
            return False

    def web_tick(self):
        """Thread da janela: aplica pedidos do navegador, copia eventos para o log e atualiza o diagnóstico."""
        server=self.web_server
        if server is None:
            return
        events=list(server.events)
        seen=min(getattr(self,'_web_events_seen',0),len(events))
        if len(events)==server.events.maxlen and seen==len(events):
            seen=len(events)
        for line in events[seen:]:
            self.log('Web: '+line)
        self._web_events_seen=len(events)
        for cmd in server.drain_commands():
            self.apply_web_command(cmd)
        self._web_diag_tick=getattr(self,'_web_diag_tick',0)+1
        if self._web_diag_tick%4==0:
            self.web_refresh_diagnostics()

    def apply_web_command(self,cmd):
        """Executa um pedido validado do navegador. Nunca há PTT/TX aqui."""
        server=self.web_server
        if server is None or not server.controls:
            return False
        action,value,ip=cmd.get('action'),cmd.get('value'),cmd.get('ip','?')
        who=f'Web ({ip})'
        if action=='select_satellite':
            idx=self.sat_combo.findData(value)
            if idx<0:
                idx=self.sat_combo.findText(str(value))
            if idx<0:
                self.log(who+': satélite não encontrado na lista: '+str(value));return False
            self.sat_combo.setCurrentIndex(idx)
            self.log(who+': satélite '+self.sat_combo.currentText())
        elif action=='auto_cat':
            self.auto_cat.setChecked(bool(value))
            self.log(who+': Auto CAT '+('ligado' if value else 'desligado'))
        elif action=='ab':
            self.log(who+': A/B')
            self.toggle_main_sub()
        elif action=='rx_only':
            if bool(value)!=bool(self.config.values.get('rx_only',False)):
                self.toggle_rx_only()
            self.log(who+': RX ONLY '+('ligado' if value else 'desligado'))
        elif action in ('rotor_track','rotor_park','rotor_stop'):
            if not self.rotor_cfg('rotor_enabled'):
                self.log(who+': rotor desativado nas Configurações');return False
            if action=='rotor_track':
                self.rotor_track_btn.setChecked(bool(value))
                self.log(who+': rastreamento do rotor '+('pedido' if value else 'desligado'))
            elif action=='rotor_park':
                self.log(who+': estacionar rotor');self.rotor_park()
            else:
                self.rotor_stop('PARAR pela rede, '+str(ip))
        else:
            return False
        self.publish_web_snapshot(force=True)
        return True

    def web_refresh_diagnostics(self):
        label=getattr(self,'web_diag',None)
        combo=getattr(self,'web_addresses',None)
        server=self.web_server
        if label is None:
            return
        if server is None:
            label.setText('Servidor: parado')
            if combo is not None:combo.clear()
            return
        d=server.diagnostics()
        if combo is not None:
            current=[combo.itemText(i) for i in range(combo.count())]
            if current!=d['addresses']:
                combo.clear();combo.addItems(d['addresses'])
                fm=combo.fontMetrics()
                widest=max([fm.horizontalAdvance(a) for a in d['addresses']]+[fm.horizontalAdvance('http://192.168.100.100:8094/')])
                combo.setFixedWidth(widest+48)
        parts=[f"Servidor: escutando na porta {d['port']}" if d['listening'] else 'Servidor: parado']
        if d['lan']:
            fw=getattr(self,'_web_firewall',None)
            if sys.platform=='win32':
                parts.append('Firewall: '+('regra presente' if fw else 'regra ausente' if fw is False else 'verificando…'))
            if not d['addresses']:
                parts.append('Nenhum IPv4 de rede local encontrado')
        parts.append('Último acesso remoto: '+(d['last_remote'] or 'nenhum'))
        active=d['remote_active']
        parts.append('Navegador remoto ativo agora: '+(', '.join(active) if active else 'não'))
        if d['controls']:
            parts.append('Controle pela rede: LIGADO')
        label.setText(' · '.join(parts))

    def web_request_firewall(self):
        from .web_ui import request_windows_firewall_rule, firewall_rule_present
        port=int(self.web_port.value())
        self.web_status.setText('Pedindo ao Windows para liberar a porta TCP '+str(port)+'…')
        def task():
            ok,msg=request_windows_firewall_rule(port)
            return ok,msg,firewall_rule_present(port)
        self.background('web-firewall-add',task)

    def web_rotate_key(self):
        if self.web_server is None:
            self.web_status.setText('Interface Web desativada');return
        self.web_server.rotate_key()
        self.log('Web: chave de acesso renovada; links antigos e sessões abertas perderam o acesso')
        self.web_status.setText('Nova chave · '+(self.web_server.url or 'IP da LAN não detectado'))
        self.web_refresh_diagnostics()

    def open_web_dashboard(self):
        if not self.start_web_server():
            QMessageBox.warning(self,'Interface Web','Não foi possível iniciar o servidor. Confira a porta TCP nas Configurações.')
            return
        import webbrowser
        url=self.web_server.url
        if not url:
            self.web_status.setText('IP da LAN não detectado · use o IP local do computador e o link com chave')
            return
        webbrowser.open(url)

    def copy_web_url(self):
        if not self.start_web_server():
            return
        combo=getattr(self,'web_addresses',None)
        url=combo.currentText() if combo is not None and combo.currentText() else self.web_server.url
        if not url:
            url=f'http://IP-DA-REDE:{self.web_server.port}/?key={self.web_server.key}'
        QApplication.clipboard().setText(url)
        self.web_status.setText('Endereço copiado: '+url)

    def web_display_png(self):
        """Imagem do display (mesmo modelo/tema da janela) em PNG, feita no thread da janela."""
        from .qt_compat import QBuffer, QByteArray, QIODevice
        lcd=getattr(self,'lcd',None)
        if lcd is None:
            return b''
        w,h=max(lcd.width(),600),max(lcd.height(),90)
        img,_=lcd.render_image(w,h,1.0)
        data=QByteArray()
        buf=QBuffer(data)
        mode=getattr(QIODevice,'WriteOnly',None) or QIODevice.OpenModeFlag.WriteOnly
        buf.open(mode)
        img.save(buf,'PNG')
        buf.close()
        return bytes(data.data())

    def publish_web_snapshot(self,force=False):
        server=self.web_server
        if server is None:
            return
        stamp=time.monotonic()
        if not force and stamp-self._web_last_push<2.5:
            return
        self._web_last_push=stamp
        def txt(name):
            item=getattr(self,name,None)
            return item.text() if item is not None else '—'
        state='desconectado'
        if self.radio.connected:
            if self.last_cat_success is None:
                state='degradado'
            else:
                age=(now_utc()-self.last_cat_success).total_seconds()
                state='conectado' if age<=10 else 'degradado'
        passes=[]
        for i in range(min(self.pass_table.rowCount(),75)):
            cells=[self.pass_table.item(i,j) for j in range(7)]
            items=[x.text() if x is not None else '—' for x in cells]
            passes.append(dict(zip(('aos','tca','los','duration','max_el','quality','modes'),items)))
        names={'elevation':'Elevação','azimuth':'Azimute','range_km':'Distância',
               'radial_m_s':'Velocidade radial','height_km':'Altitude orbital'}
        metrics={names[k]:w.text() for k,w in self.orbit_metrics.items()}
        orbit=None
        try:
            pos=self.last_pos
            station=self.saved_station()
            if pos and station:
                orbit={
                    'name':self.sat_combo.currentText(),
                    'satellite':{'lat':pos['sat_lat'],'lon':pos['sat_lon'],
                                 'height_km':pos.get('height_km',0)},
                    'station':{'lat':station.lat,'lon':station.lon,'callsign':station.callsign},
                    'track_past':self.track_cache.get('past',[]),
                    'track_future':self.track_cache.get('future',[]),
                    'footprint':footprint(pos['sat_lat'],pos['sat_lon'],pos['footprint_radius_deg']),
                    'label':self.sat_combo.currentText()+' · elevação '+str(round(pos['elevation'],1))+'°'}
        except (KeyError,ValueError,TypeError,AttributeError):
            pass
        server.publish({
            'version':__version__,
            'utc':now_utc().strftime('UTC · %d/%m/%Y %H:%M:%S'),
            'satellite':self.sat_combo.currentText(),
            'catalog_count':len(self.omm),
            'cat_state':state,
            'cat_detail':txt('cat_tune_status'),
            'rx':txt('pred_rx').replace('\n',' · '),
            'tx':txt('pred_tx').replace('\n',' · '),
            'nextpass':txt('next_countdown'),
            'metrics':metrics,
            'visibility':txt('visibility'),
            'passes':passes,
            'orbit':orbit,
            **self.web_extra_snapshot(server),
        })

    def web_extra_snapshot(self,server):
        """Rotor, APRS, lista de satélites, Auto CAT/RX ONLY e a imagem do display para o painel Web."""
        def txt(name):
            item=getattr(self,name,None)
            return item.text() if item is not None else ''
        rotor={'enabled':bool(self.rotor_cfg('rotor_enabled'))}
        if rotor['enabled']:
            connected=bool(getattr(getattr(self,'rotor',None),'connected',False))
            rotor.update(connected=connected,tracking=bool(getattr(self,'rotor_tracking',False)),
                         state='rastreando' if getattr(self,'rotor_tracking',False) else ('conectado' if connected else 'desconectado'),
                         position=txt('rotor_pos_label'),target=txt('rotor_target_label'),status=txt('rotor_label'))
        aprs=[]
        for rec in list(getattr(getattr(self,'sdr_panel',None),'records',[]) or [])[:15]:
            aprs.append({'utc':str(rec.get('utc',''))[11:19],'source':str(rec.get('source','')),
                         'text':str(rec.get('aprs') or rec.get('ax25') or rec.get('hex') or '')[:160]})
        extra={'rotor':rotor,'aprs':aprs,'auto_cat':bool(self.auto_cat.isChecked()),
               'rx_only':bool(self.config.values.get('rx_only',False)),'display':''}
        if server.controls:
            sats=[]
            for i in range(min(self.sat_combo.count(),500)):
                data=self.sat_combo.itemData(i)
                sats.append({'id':str(data if data is not None else self.sat_combo.itemText(i)),'name':self.sat_combo.itemText(i)})
            current=self.sat_combo.currentData()
            extra.update(satellites=sats,satellite_id=str(current if current is not None else self.sat_combo.currentText()))
        if server.browser_recent():
            try:
                png=self.web_display_png()
                if png:
                    server.publish_display(png)
                    extra['display']=str(int(time.time()*1000))
            except Exception as exc:
                report_exception('Web display',exc)
        return extra
    def closeEvent(self,event):
        self.rotor_shutdown()
        self._closing_app=True
        if getattr(self,"display_window",None) is not None:
            self.display_window.close()   # lembra posição/monitor; display_detached continua True
        try:
            if self.sdr_dock.isVisible() and not self.sdr_dock.isFloating():
                self.config.values["sdr_dock_height"]=int(self.sdr_dock.height())
        except Exception:
            pass
        if getattr(self,"sdr_panel",None) is not None:
            self.sdr_panel.shutdown()
        # v1.6.0: desmonta o mapa para os processos QtWebEngine encerrarem junto com o app.
        try:
            for timer in (self.tick_timer,self.cat_live_timer,self.diagnostic_timer):
                timer.stop()
            self.map.stop()
            self.map.setHtml("")
            self.map.close()
            self.map.deleteLater()
        except Exception:
            pass
        self.config.save()
        if self.web_server is not None:
            self.web_server.stop()
            self.web_server=None
        self.doppler_checkbox.setChecked(False)
        self.radio.disconnect()
        event.accept()


def _single_instance_mutex():
    """Mutex nomeado: o instalador (AppMutex) detecta o app aberto e pede/força o fechamento."""
    if sys.platform!="win32":
        return None
    try:
        import ctypes
        return ctypes.windll.kernel32.CreateMutexW(None,False,"PT2VHF_Sat_Tool_Running")
    except Exception:
        return None


def main():
    app=QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(True)
    mutex=_single_instance_mutex()
    try:  # v1.7.2: EXE portátil com a versão no nome, também depois de um OTA
        from .updater import rename_portable_to_version
        from . import __version__ as _ver
        rename_portable_to_version(_ver)
    except Exception:
        pass
    window=MainWindow()
    window.show()
    QTimer.singleShot(2500,window.show_last_update_result)
    code=qt_exec(app)
    del mutex
    # Threads de serial/SDR/rede são daemon; sai imediatamente para não deixar processos órfãos.
    try:
        from .crash_diagnostics import clean_shutdown
        clean_shutdown()
    except Exception:
        pass
    try:
        sys.stdout.flush();sys.stderr.flush()
    except Exception:
        pass
    os._exit(int(code or 0))
