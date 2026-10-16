"""PT2VHF Sat Tool desktop Windows MVP.

UI is intentionally non-transmitting: no CAT TX/PTT commands exist.
"""
from __future__ import annotations
import json
import math
import time
import unicodedata
import sys
import threading
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .qt_compat import Qt, QTimer, QObject, Signal, Slot, QUrl
from .crash_diagnostics import heartbeat,report_event,report_exception,diagnostic_dir
from .log_journal import EventJournal
from .qt_compat import QDoubleValidator, QFont, QIcon, QPixmap
from .qt_compat import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QGroupBox, QTabWidget, QPlainTextEdit,
    QSplitter, QMessageBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QAbstractItemView, QProgressDialog, QScrollArea, QProgressBar, QFileDialog,
)
from .qt_compat import QWebEngineView, QGeoPositionInfoSource, qt_exec, QT_BINDING
from skyfield.api import load
from . import __version__
from .cat import TS2000, available_ports, decode_satellite_status
from .catalog import refresh_orbits, load_orbits, refresh_transmitters, load_transmitters, age_hours, satellite_search_text, normalized_satellite_search, DEFAULT_GROUPS
from .config import Config
from .geolocation import GeoFix, lookup_approximate_ip, read_gps_serial
from .location_map import parse_coordinate_fields, sanitize_map_pick, valid_coordinates
from .frequency import format_frequency,parse_mhz_input,frequency_label
from .transponder import prioritized_transponders,cat_pair_diagnostic
from .i18n import LANGUAGES,translated
from .satellite_info import orbital_characteristics, operational_characteristics, characteristics_text
from .updater import check_for_update, download_update, install_flavor, launch_staged_update
from .profile import choose_satellites, capability, render_service, CANDIDATES
from .selection import change_selection, transmitter_batch_ids, cat_doppler_allowed
from .alerts import eta_seconds, format_duration, selected_aos_alarm
from .media import find_photo, photo_html
from .operations import select_next_pass, frequency_prediction, status_at, orbital_age_days
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


class MainWindow(QMainWindow):
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
        self.selected_cat_target = None
        self.freq_update_cancel = False
        self.freq_update_stats = None
        self.frequency_progress_dialog = None
        self.frequency_started_at = None
        self.orbit_started_at = None
        self.orbit_progress_dialog = None
        self.aos_alarm_dialog = None
        self.aos_alarm_target = None
        self.cat_selection_generation = 0
        self.cat_autotune_requested_generation = -1
        self.cat_tune_manual_request = False
        self.cat_tracking_armed = False
        self.cat_connecting = False
        self.cat_connect_was_startup = False
        self.last_tracking_write = 0.0
        self.last_cat_poll_started = 0.0
        self.last_cat_track_completed = 0.0
        self.cat_live_queued = False
        self.cat_last_requested = (None,None)
        self.cat_last_roundtrip_ms = None
        self._mode_catalog_sat_id = None
        self._loading_satellites = False
        self._loading_catalog = False
        self._active_satellite_id = None
        self._passes_refresh_again = False
        self.pos_source = None
        self.map_pick_active = False
        self.map_pick_position = None
        self.init_ui()
        self.capture_static_language()
        self.load_fields()
        self.apply_language()
        self.populate_catalog(load_orbits(self.config.dir))
        self.update_ports()
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
        QTimer.singleShot(12000, self.check_for_updates)
        if self.config.values.get("cat_auto_connect_startup",True) and self.config.values.get("port","").strip():
            QTimer.singleShot(1200, self.startup_cat_connect)

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
        operation = QWidget(); op = QVBoxLayout(operation); op.setContentsMargins(12,12,12,10)
        op.setSpacing(9)
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
        self.version_btn.setToolTip("Verificar versões no GitHub; iniciar atualização com autorização")
        self.version_btn.clicked.connect(lambda: self.request_update(manual=True))
        self.version_btn.setStyleSheet('background:#155a3e;border:1px solid #30a579;color:#e6fff4')
        header.addWidget(self.version_btn)
        self.summary = label("Dados orbitais não carregados")
        self.summary.setStyleSheet('color:#85aaba')
        header.addWidget(self.summary, 1)
        self.cat_indicator=QPushButton("● RÁDIO DESCONECTADO")
        self.cat_indicator.setToolTip("Clique para conectar ou desconectar o TS-2000 pela porta CAT configurada")
        self.cat_indicator.clicked.connect(self.toggle_connection)
        self.cat_indicator.setStyleSheet("font-size:14px;font-weight:800;color:#ef9a9a;padding:6px;background:#243143;border-radius:5px")
        header.addWidget(self.cat_indicator)
        self.utc = QLabel("DATA/HORA UTC —")
        self.utc.setStyleSheet("font-size:17px;font-weight:800;color:#dff9ff;padding:6px;background:#153751;border:1px solid #34758c;border-radius:5px")
        self.utc.setMinimumWidth(235)
        header.addWidget(self.utc)
        op.addLayout(header)
        upcoming,upcoming_layout=group("PRÓXIMA PASSAGEM COMPATÍVEL · CONTAGEM REGRESSIVA")
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
        self.next_times=label("AOS — · TCA — · LOS — · Elevação máxima —")
        self.next_times.setStyleSheet("color:#b5cfde;font-size:11px")
        upcoming_layout.addWidget(self.next_times)
        self.next_frequencies=label("RX/TX: aguardando transponder publicado e TLE válido")
        self.next_frequencies.setStyleSheet("color:#7ee5d4;font-size:12px;font-weight:700")
        upcoming_layout.addWidget(self.next_frequencies)
        self.pass_progress=QProgressBar()
        self.pass_progress.setRange(0,1000)
        self.pass_progress.setValue(0)
        self.pass_progress.setMaximumHeight(7)
        self.pass_progress.setTextVisible(False)
        self.pass_progress.setStyleSheet("QProgressBar{background:#10243c;border:0;border-radius:3px}QProgressBar::chunk{background:#35d9b6;border-radius:3px}")
        upcoming_layout.addWidget(self.pass_progress)
        op.addWidget(upcoming)
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
        self.rx_mode=QComboBox();self.tx_mode=QComboBox()
        for cb in (self.rx_mode,self.tx_mode):cb.addItems(["FM","USB","LSB","CW","AM","FSK"])
        form.addWidget(label("Modo RX"),4,0);form.addWidget(self.rx_mode,5,0)
        form.addWidget(label("Modo TX (referência)"),6,0);form.addWidget(self.tx_mode,7,0)
        fv.addLayout(form)
        self.mode_note=label("Selecione uma frequência do SatNOGS ou informe manualmente.")
        self.mode_note.setStyleSheet("color:#e3c477")
        fv.addWidget(self.mode_note)
        # Retire the competing legacy Doppler control; use Auto CAT as the single control.
        self.doppler_checkbox=QCheckBox()
        self.doppler_checkbox.setChecked(False)
        self.frequency_apply=QPushButton("Aplicar RX/TX no TS-2000")
        self.frequency_apply.setObjectName('primary')
        self.frequency_apply.clicked.connect(self.apply_freqs)
        fv.addWidget(self.frequency_apply)
        self.apply_main_mode=QPushButton("Aplicar modo RX (MAIN)")
        self.apply_main_mode.clicked.connect(self.apply_rx_mode)
        fv.addWidget(self.apply_main_mode)
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
        self.pred_rx=label("RX / DOWNLINK\nAguardando satélite")
        self.pred_tx=label("TX / UPLINK\nAguardando satélite")
        for card,color in ((self.pred_rx,"#68ebcd"),(self.pred_tx,"#8fd8ff")):
            card.setAlignment(Qt.AlignCenter)
            card.setMinimumHeight(108)
            card.setMinimumWidth(210)
            card.setStyleSheet("font-size:15px;font-weight:800;color:"+color+
                               ";background:transparent;border:0;padding:4px")
            frequency_cards.addWidget(card,1)
        ov.addLayout(frequency_cards)
        self.corrected_label=label("Previsão orbital sem CAT e sem transmissão")
        self.corrected_label.setStyleSheet("color:#a4d5df;font-size:11px")
        self.corrected_label.setVisible(False)
        ov.addWidget(self.corrected_label)
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
        self.map.setHtml(Path(__file__).with_name("map.html").read_text(encoding="utf-8"),
                         QUrl("about:blank"))
        mv.addWidget(self.map,1)
        self.map_radio_label=label("CAT desconectado · RX — MHz · TX — MHz · Modo —")
        self.map_radio_label.setStyleSheet("font-size:13px;color:#f0c186;font-weight:700")
        mv.addWidget(self.map_radio_label)
        self.map_desc=label("Trajetória · cobertura · estação · mapa vetorial offline (Natural Earth)")
        self.map_desc.setStyleSheet('color:#8caec3')
        mv.addWidget(self.map_desc)
        splitter.addWidget(mid)
        right=QWidget();rv=QVBoxLayout(right);rv.setContentsMargins(2,0,2,0)
        stat,sv=group("TELEMETRIA ORBITAL")
        self.orbit_metrics={}
        for key,title in (("elevation","Elevação"),("azimuth","Azimute"),("range_km","Distância"),
                          ("radial_m_s","Velocidade radial"),("height_km","Altitude orbital")):
            r=QHBoxLayout();r.addWidget(label(title));v=label("—");v.setAlignment(Qt.AlignRight)
            v.setStyleSheet("font-size:15px;font-weight:600;color:#90e7df")
            self.orbit_metrics[key]=v;r.addWidget(v);sv.addLayout(r)
        self.visibility=label("Aguardando localização")
        self.visibility.setObjectName('metric')
        sv.addWidget(self.visibility)
        rv.addWidget(stat)
        nextpass,np=group("PRÓXIMAS PASSAGENS · 36 H")
        self.pass_table=QTableWidget(0,6)
        self.pass_table.setHorizontalHeaderLabels(["Satélite","AOS local","TCA local","LOS local","Max °","Modos"])
        self.pass_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pass_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pass_table.cellDoubleClicked.connect(self.select_pass_satellite)
        self.pass_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        np.addWidget(self.pass_table)
        self.refresh_passes_btn=QPushButton("Recalcular passagens")
        self.refresh_passes_btn.clicked.connect(self.refresh_passes)
        np.addWidget(self.refresh_passes_btn)
        rv.insertWidget(0,nextpass,2)
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
        splitter.setSizes([1100,420])
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
        quick_cat.addWidget(self.radio_label,1)
        quick_cat.addWidget(self.connection)
        op.addLayout(quick_cat)
        self.cat_live_label=label("RÁDIO REAL (CAT) · aguardando FA (RX SAT) / FB (TX SAT) / FC (SUB) / MD")
        self.cat_live_label.setStyleSheet("font-size:14px;font-weight:800;color:#d8f5c0")
        op.addWidget(self.cat_live_label)
        self.cat_sat_orientation=label("SAT: aguardando resposta SA do TS-2000")
        self.cat_sat_orientation.setStyleSheet("font-size:12px;font-weight:700;color:#d8c399")
        op.addWidget(self.cat_sat_orientation)
        self.cat_diagnose=QPushButton("Diagnosticar comunicação CAT · somente leitura")
        self.cat_diagnose.setToolTip("Consulta ID, SA, FA, FB, FC e MD; sem alterar SAT, VFO ou PTT")
        self.cat_diagnose.setEnabled(False)
        self.cat_diagnose.clicked.connect(self.diagnose_cat)
        op.addWidget(self.cat_diagnose)
        self.cat_tune_status=label("Auto CAT desligado · ative em Configurações para acompanhar a seleção")
        self.cat_tune_status.setStyleSheet("font-size:12px;font-weight:700;color:#b4d7e7")
        op.addWidget(self.cat_tune_status)
        self.cat_sync_status=label("CAT SYNC · previsto — · confirmado — · atraso —")
        self.cat_sync_status.setStyleSheet("font-size:11px;color:#a8d7e5")
        op.addWidget(self.cat_sync_status)
        root.addTab(operation,"Operação")
        catalog_page=QWidget(); catalog_layout=QVBoxLayout(catalog_page)
        catalog_layout.addWidget(label("Satélites atuais no catálogo orbital CelesTrak. 'Canal publicado' não comprova serviço ativo nem autoriza TX. Clique duas vezes para selecionar."))
        self.catalog_search=QLineEdit()
        self.catalog_search.setPlaceholderText("Filtrar nome, NORAD, modo ou frequência…")
        self.catalog_search.textChanged.connect(self.refresh_satellite_table)
        catalog_layout.addWidget(self.catalog_search)
        self.catalog_category=QComboBox()
        self.catalog_category.addItem("Todas as categorias","all")
        for name in DEFAULT_GROUPS:self.catalog_category.addItem(name.upper(),name)
        self.catalog_category.currentIndexChanged.connect(self.refresh_satellite_table)
        catalog_layout.addWidget(self.catalog_category)
        catalog_actions=QHBoxLayout()
        self.scope_filtered=QCheckBox("Somente resultados filtrados")
        self.scope_filtered.setToolTip("Marcar/desmarcar somente os satélites exibidos; desmarcado: catálogo inteiro")
        self.mark_catalog_all=QPushButton("Marcar todos")
        self.mark_catalog_none=QPushButton("Desmarcar todos")
        self.mark_catalog_all.clicked.connect(lambda:self.bulk_catalog_selection(True))
        self.mark_catalog_none.clicked.connect(lambda:self.bulk_catalog_selection(False))
        self.catalog_refresh_scope=QComboBox()
        self.catalog_refresh_scope.addItems(["Selecionado","Habilitados","Resultados filtrados"])
        self.catalog_refresh_scope.setCurrentIndex(1)  # Batch follows marked satellites by default
        self.refresh_catalog_freq=QPushButton("Baixar/atualizar frequências")
        self.refresh_catalog_freq.clicked.connect(self.refresh_catalog_transmitters)
        self.stop_catalog_freq=QPushButton("Cancelar download")
        self.stop_catalog_freq.clicked.connect(self.cancel_catalog_transmitters)
        self.stop_catalog_freq.setEnabled(False)
        for widget in (self.scope_filtered,self.mark_catalog_all,self.mark_catalog_none,
                       self.catalog_refresh_scope,self.refresh_catalog_freq,self.stop_catalog_freq):
            catalog_actions.addWidget(widget)
        catalog_layout.addLayout(catalog_actions)
        self.catalog_progress=label("SatNOGS: frequências em cache; atualização sob demanda.")
        catalog_layout.addWidget(self.catalog_progress)
        self.catalog_table=QTableWidget(0, 8)
        self.catalog_table.setHorizontalHeaderLabels(["Selecionado", "Satélite", "NORAD", "Inclinação", "Período", "Modos", "Downlink MHz", "Situação"])
        self.catalog_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.catalog_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Fixed)
        self.catalog_table.setColumnWidth(0,92)
        self.catalog_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.catalog_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.catalog_table.cellDoubleClicked.connect(self.select_catalog_satellite)
        self.catalog_table.itemChanged.connect(self.catalog_satellite_checked)
        catalog_layout.addWidget(self.catalog_table)
        self.catalog_note=label("Dados orbitais: CelesTrak OMM/TLE · Frequências e modos: SatNOGS · Não confundir catálogo com atividade confirmada.")
        catalog_layout.addWidget(self.catalog_note)
        root.addTab(catalog_page,"Satélites")
        config_page=QWidget();config_root=QVBoxLayout(config_page)
        settings_scroll=QScrollArea(config_page);settings_scroll.setWidgetResizable(True)
        settings_frame=QWidget();cfg=QVBoxLayout(settings_frame)
        cfg.setContentsMargins(20,16,20,16)
        settings_scroll.setWidget(settings_frame);config_root.addWidget(settings_scroll)
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
        source_row=QHBoxLayout()
        source_row.addWidget(label("Fonte de localização:"))
        self.location_source=QComboBox()
        self.location_source.addItems([
            "Windows (se houver provedor de posição)",
            "IP aproximado (cidade/região, com consentimento)",
            "GPS USB / serial (NMEA)",
            "Manual (sem consulta externa)",
        ])
        self.location_source.currentIndexChanged.connect(self.change_location_source)
        source_row.addWidget(self.location_source,2)
        self.gps_port=QComboBox();self.gps_port.setEditable(True)
        self.gps_port.setToolTip("Porta COM do receptor GPS, diferente da porta CAT do TS-2000")
        self.gps_port.setMinimumWidth(95)
        self.gps_baud=QComboBox();self.gps_baud.addItems(["4800","9600","38400","115200"])
        self.gps_baud.setCurrentText("9600")
        source_row.addWidget(label("GPS COM:"));source_row.addWidget(self.gps_port)
        source_row.addWidget(label("Baud:"));source_row.addWidget(self.gps_baud)
        sg.addLayout(source_row)
        place=QHBoxLayout()
        self.get_position=QPushButton("Obter localização da fonte selecionada")
        self.get_position.clicked.connect(self.geolocate)
        self.save_station_btn=QPushButton("Salvar estação")
        self.save_station_btn.setObjectName('primary')
        self.save_station_btn.clicked.connect(self.save_station)
        self.station_map_button=QPushButton("Marcar estação no mapa")
        self.station_map_button.clicked.connect(self.begin_station_map)
        place.addWidget(self.get_position)
        place.addWidget(self.station_map_button)
        place.addWidget(self.save_station_btn)
        sg.addLayout(place)
        self.location_status=label("Sem consulta: escolha a fonte. IP é aproximado, GPS requer receptor, manual não usa rede.")
        self.location_status.setStyleSheet("color:#a6cede;font-size:11px")
        sg.addWidget(self.location_status)
        sg.addWidget(label("A latitude/longitude obtidas precisam ser conferidas e depois salvas manualmente. Consultar IP envia seu IP público ao provedor; nenhuma consulta é automática."))
        cfg.addWidget(station_group)
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
        pg.addWidget(profile_save);cfg.addWidget(profile_group)

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
        self.auto_cat.setToolTip("Acompanha o satélite selecionado a cada segundo. Reprograma FA/FB somente quando a frequência Doppler muda. Sem PTT; exige SAT ON e crossband.")
        self.auto_cat.toggled.connect(self.change_auto_cat)
        rs.addWidget(self.auto_cat)
        self.auto_cat_startup=QCheckBox("Conectar ao abrir e seguir satélite se Auto CAT estiver habilitado")
        self.auto_cat_startup.toggled.connect(self.change_startup_connect)
        rs.addWidget(self.auto_cat_startup)
        rs.addWidget(label("O programa pode conectar ao abrir, mas só rastreia após escolha explícita do satélite. Não habilita SAT nem transmite."))
        rs.addWidget(catview)
        connect_btn=QPushButton("Conectar pela porta selecionada")
        connect_btn.clicked.connect(self.connect_from_settings)
        rs.addWidget(connect_btn);cfg.addWidget(radio_settings)
        track_settings,tsv=group("MAPA E TRAJETÓRIA")
        tsv.addLayout(trail_bar)
        tsv.addWidget(label("O mapa respeita as preferências salvas. Para marcar a estação, use Estação Terrena."))
        cfg.addWidget(track_settings)

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
        self.aos_enabled=QCheckBox("Avisar 30 segundos antes da entrada do satélite selecionado")
        self.aos_enabled.toggled.connect(lambda v:self.set_alarm_option("aos_alarm_enabled",v))
        self.aos_sound=QCheckBox("Alarme sonoro")
        self.aos_sound.toggled.connect(lambda v:self.set_alarm_option("aos_alarm_sound",v))
        alert_layout.addWidget(self.aos_enabled)
        alert_layout.addWidget(self.aos_sound)
        alarm_test=QPushButton("Testar som")
        alarm_test.clicked.connect(QApplication.beep)
        alert_layout.addWidget(alarm_test)
        cfg.addWidget(alert_group)
        advanced,adv=group("DOPPLER E SEGURANÇA")
        self.interval=QDoubleSpinBox();self.interval.setRange(0.25,15);self.interval.setSingleStep(0.25);self.interval.setDecimals(2);self.interval.setSuffix(' segundos')
        self.threshold=QDoubleSpinBox();self.threshold.setRange(1,1000);self.threshold.setDecimals(0);self.threshold.setSuffix(' Hz')
        ag=QGridLayout();ag.addWidget(label("Intervalo de ajuste automático"),0,0);ag.addWidget(self.interval,0,1)
        ag.addWidget(label("Mínima variação para reprogramar CAT"),1,0);ag.addWidget(self.threshold,1,1)
        adv.addLayout(ag)
        self.cat_outside=QCheckBox("Permitir CAT Doppler fora da visada (opcional)")
        self.cat_outside.toggled.connect(self.change_cat_outside)
        adv.addWidget(self.cat_outside)
        adv.addWidget(label("Doppler calculado a cada segundo, inclusive fora da visada. CAT exige SAT, efeméride recente e autorização. Fora da visada, CAT bloqueado por padrão. Sem comandos PTT."))
        cfg.addWidget(advanced)
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
        cfg.addWidget(local_group)
        update_group, ug=group("ATUALIZAÇÕES DO APLICATIVO")
        self.update_minutes=QDoubleSpinBox();self.update_minutes.setRange(5,1440);self.update_minutes.setDecimals(0)
        self.update_minutes.setSuffix(' min')
        ug.addWidget(label("Verificar novas versões automaticamente a cada"))
        ug.addWidget(self.update_minutes)
        self.include_prerelease=QCheckBox("Incluir versões de testes / pré-lançamentos")
        ug.addWidget(self.include_prerelease)
        ug.addWidget(label("Nova versão: aviso na barra superior, changelog e download autenticado com SHA-256. A substituição só ocorre após sua confirmação e o fechamento seguro do aplicativo. Configurações preservadas."))
        self.save_update_btn=QPushButton("Salvar preferências de atualização")
        self.save_update_btn.clicked.connect(self.save_update_preferences)
        ug.addWidget(self.save_update_btn)
        cfg.addWidget(update_group)
        extra_controls,extras=group("EDITOR AVANÇADO DE SATÉLITE E TRANSPONDER")
        extras.addWidget(left)
        cfg.addWidget(extra_controls)
        cfg.addStretch(1)
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
        about_layout.addWidget(label("Distribuição: Windows 7 / Windows 11; instalador Setup EXE e portátil EXE único."))
        about_layout.addWidget(label("Elementos orbitais: CelesTrak OMM/TLE. Transponders e modos: SatNOGS (créditos e licenças nos provedores)."))
        about_layout.addWidget(label("Repositório: https://github.com/alexpmr/PT2VHF-Sat-Tool · Licença MIT"))
        btn=QPushButton("Verificar versão");btn.clicked.connect(lambda:self.request_update(manual=True))
        about_layout.addWidget(btn);about_layout.addStretch()
        root.addTab(about,"Sobre")
        self.statusBar().showMessage("PT2VHF Sat Tool | Mapa offline Natural Earth | CAT passivo · PTT não controlado | CelesTrak OMM / SatNOGS")

    def load_fields(self):
        c=self.config.values
        self.callsign.setText(str(c['callsign']))
        self.lat.setText(str(c['lat']))
        self.lon.setText(str(c['lon']))
        self.altitude.setValue(float(c['altitude_m']))
        self.min_el.setValue(float(c['min_elevation']))
        self.baud_combo.setCurrentText(str(c['baud']))
        self.gps_baud.setCurrentText(str(c.get('gps_baud',9600)))
        if c.get('gps_port'):self.gps_port.setCurrentText(str(c['gps_port']))
        self.change_location_source()
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
        self.cat_outside.blockSignals(True)
        self.cat_outside.setChecked(bool(c.get('cat_doppler_out_of_view',False)))
        self.cat_outside.blockSignals(False)
        self.update_minutes.setValue(float(c.get('version_check_minutes',15)))
        self.include_prerelease.setChecked(bool(c.get('include_prereleases', True)))
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(max(0,self.language_combo.findData(c.get("language","pt-BR"))))
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

    def capture_static_language(self):
        """Snapshot only creation-time UI strings; do not translate live CAT telemetry."""
        self._language_texts=[]
        for widget in self.findChildren(QWidget):
            if isinstance(widget,QGroupBox):
                original=widget.title()
                if original:self._language_texts.append((widget,"group",original))
            elif isinstance(widget,(QPushButton,QCheckBox,QLabel)):
                original=widget.text()
                if original:self._language_texts.append((widget,"text",original))
        self._language_tabs=[self.tabs.tabText(i) for i in range(self.tabs.count())]
        self._language_tables=[]
        for widget in self.findChildren(QTableWidget):
            labels=[]
            for i in range(widget.columnCount()):
                item=widget.horizontalHeaderItem(i)
                labels.append(item.text() if item is not None else "")
            self._language_tables.append((widget,labels))

    def apply_language(self):
        locale=self.config.values.get("language","pt-BR")
        old=getattr(self,"_language_active","pt-BR")
        for widget,kind,original in self._language_texts:
            old_value=translated(original,old)
            new_value=translated(original,locale)
            current=widget.title() if kind=="group" else widget.text()
            if current in (old_value,original):
                if kind=="group":widget.setTitle(new_value)
                else:widget.setText(new_value)
        for i,original in enumerate(self._language_tabs):
            self.tabs.setTabText(i,translated(original,locale))
        for widget,originals in self._language_tables:
            for i,original in enumerate(originals):
                item=widget.horizontalHeaderItem(i)
                if item:item.setText(translated(original,locale))
        for i,original in enumerate(("Selecionado","Habilitados","Resultados filtrados")):
            self.catalog_refresh_scope.setItemText(i,translated(original,locale))
        if hasattr(self,"tracked_search"):
            self.tracked_search.setPlaceholderText(translated("Pesquisar por nome ou NORAD…",locale))
        self._language_active=locale

    def change_language(self,*args):
        locale=self.language_combo.currentData()
        if locale not in LANGUAGES:return
        self.config.values["language"]=locale
        self.config.save()
        self.apply_language()
        self.log(f"Idioma da interface: {LANGUAGES[locale]}")

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
        self.config.save()
        self.log('Preferências de atualizações salvas')
        self.manual_update_requested = True
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

    def request_update(self,manual=False):
        if not self.update_distribution:
            QMessageBox.information(self,'Atualizações','O atualizador funciona apenas nos executáveis Windows instalável ou portátil. Compile ou instale uma versão para testar.')
            return
        if self.available_update is None:
            self.manual_update_requested = bool(manual)
            self.check_for_updates(force=True)
            return
        if 'update-download' in self.pending_jobs:
            return
        u=self.available_update
        msg=(f'Nova versão {u.version} disponível para {self.update_distribution[0]} / {self.update_distribution[1]}.\n\n'
             f'Novidades:\n{u.body[:3500] or "Sem descrição."}\n\n'
             'Baixar e instalar após verificação SHA-256? O aplicativo será fechado; Doppler/CAT serão desconectados.')
        if QMessageBox.question(self,'Atualização PT2VHF Sat Tool',msg)!=QMessageBox.Yes:
            return
        self.update_dialog=QProgressDialog('Baixando e verificando atualização…','',0,100,self)
        self.update_dialog.setCancelButton(None)
        self.update_dialog.setAutoClose(False)
        self.update_dialog.setMinimumDuration(0)
        self.update_dialog.setValue(0)
        self.version_btn.setText('Atualização em andamento…')
        self.background('update-download', lambda: download_update(u, lambda n,total:self.events.progress.emit(n,total)))

    def download_progress(self, current, total):
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
        self.doppler_checkbox.setChecked(False)
        self.radio.disconnect()
        try:
            base=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
            script=base/'scripts'/'apply-update.ps1'
            launch_staged_update(Path(package), portable=self.update_distribution[1]=='Portable', script_path=script)
            self.log('Atualização verificada; fechando para atualização externa')
            self.close()
        except Exception as exc:
            QMessageBox.critical(self,'Atualização não aplicada',str(exc))

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
        self.tabs.setCurrentIndex(2)
        self.lat.setFocus()

    def save_station(self):
        try: st=self.station()
        except Exception as exc:
            QMessageBox.warning(self,"Localização inválida",str(exc));return
        c=self.config.values
        c.update({"callsign":st.callsign,"lat":st.lat,"lon":st.lon,
                  "altitude_m":st.altitude_m,"min_elevation":st.min_elevation,
                  "update_interval_s":int(self.interval.value()),"tune_threshold_hz":int(self.threshold.value())})
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

    def change_location_source(self,*args):
        source=self.location_source.currentIndex()
        gps=(source==2)
        self.gps_port.setVisible(gps)
        self.gps_baud.setVisible(gps)
        # The serial settings are independent of the TS-2000 CAT port.
        self.get_position.setText(
            ("Solicitar coordenadas ao Windows",
             "Consultar IP aproximado (pedir autorização)",
             "Ler posição GPS por COM",
             "Inserir coordenadas manualmente")[source])
        if source==0:
            self.location_status.setText("Windows: exige serviço/provedor de localização e permissões habilitadas.")
        elif source==1:
            self.location_status.setText("IP aproximado: será enviada uma consulta HTTPS a ipwho.is SOMENTE após sua autorização.")
        elif source==2:
            self.location_status.setText("GPS NMEA: receptor conectado e porta COM exclusiva; nenhuma solicitação à Internet.")
        else:
            self.location_status.setText("Manual: digite latitude e longitude, confira altitude e clique em Salvar estação.")

    def geolocate(self):
        choice=self.location_source.currentIndex()
        if choice==3:
            self.lat.setFocus()
            self.location_status.setText("Digite as coordenadas da antena manualmente e clique em Salvar estação.")
            return
        if choice==1:
            consent=QMessageBox.question(self,"Localização aproximada por IP",
                "Quer consultar sua região aproximada em https://ipwho.is/?\n\n"
                "O serviço externo receberá seu IP público e metadados normais da requisição HTTPS. "
                "O resultado pode indicar apenas a cidade ou região, NÃO a posição exata da estação.\n\n"
                "Nada será salvo nem enviado ao rádio automaticamente. Continuar?",
                QMessageBox.Yes | QMessageBox.No,QMessageBox.No)
            if consent!=QMessageBox.Yes:
                self.location_status.setText("Consulta IP cancelada. Coordenadas anteriores preservadas.")
                return
            self.location_status.setText("Consultando localização aproximada por IP com autorização…")
            self.background("geo-ip",lookup_approximate_ip)
            return
        if choice==2:
            port=self.gps_port.currentText().strip()
            if not port:
                QMessageBox.warning(self,"GPS","Selecione ou digite a porta COM do receptor GPS.")
                return
            cat=(self.ports.currentText() or self.config.values.get("port","")).strip()
            if port.casefold()==cat.casefold():
                QMessageBox.warning(self,"Porta em uso",
                    "A porta do GPS deve ser diferente da porta CAT do TS-2000. "
                    "Não usaremos o rádio como fonte de GPS.")
                return
            baud=int(self.gps_baud.currentText())
            self.config.values.update({"gps_port":port,"gps_baud":baud})
            self.config.save()
            self.location_status.setText("Aguardando posição válida do GPS NMEA (até 12 s)…")
            self.background("geo-gps",lambda:read_gps_serial(port,baud=baud,timeout_s=12))
            return
        try:
            source=QGeoPositionInfoSource.createDefaultSource(self)
            if source is None:
                self.location_status.setText(
                    "Windows sem provedor de localização. Use coordenadas manuais, IP aproximado "
                    "com consentimento ou GPS serial.")
                self.log("QtPositioning: provedor de localização indisponível no sistema")
                return
            self.pos_source=source
            source.positionUpdated.connect(self.position_found)
            self.location_waiting=True
            if getattr(self,"location_timer",None) is None:
                self.location_timer=QTimer(self)
                self.location_timer.setSingleShot(True)
                self.location_timer.timeout.connect(self.location_timed_out)
            self.location_timer.start(13000)
            source.requestUpdate(12000)
            self.location_status.setText("Aguardando serviço de localização do Windows (até 13 s)…")
        except Exception as exc:
            self.location_waiting=False
            self.location_status.setText(
                "Windows não forneceu localização. Tente manual, IP opcional ou GPS serial.")
            self.log(f"Falha ao consultar localização do Windows: {exc}")

    def location_timed_out(self):
        if getattr(self,"location_waiting",False):
            self.location_waiting=False
            self.log("Localização Windows: sem resposta dentro de 13 s")
            self.location_status.setText(
                "Tempo excedido no Windows; use GPS serial, IP aproximado (opcional) ou digite as coordenadas.")

    def position_found(self,info):
        if not getattr(self,"location_waiting",False):
            return
        coord=info.coordinate()
        if not coord.isValid():
            self.location_status.setText("O Windows retornou uma posição inválida; nenhuma coordenada alterada.")
            return
        self.location_waiting=False
        timer=getattr(self,"location_timer",None)
        if timer is not None:timer.stop()
        try:
            lat=float(coord.latitude())
            lon=float(coord.longitude())
            altitude=float(coord.altitude())
            fix=GeoFix(lat,lon,"Localização do Windows",
                       altitude_m=altitude if math.isfinite(altitude) else None,
                       description="Provedor Qt/Windows").validate()
            self.apply_location_fix(fix)
        except (ValueError,TypeError) as exc:
            self.location_status.setText(f"Posição Windows rejeitada: {exc}. Dados anteriores preservados.")

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
                QMessageBox.warning(self,"CAT não configurado",
                    "Configure uma porta COM em Configurações → Conexão CAT antes de conectar.")
                self.tabs.setCurrentIndex(2)
            return
        baud=int(self.baud_combo.currentText())
        stopbits=int(self.stops_combo.currentText())
        self.cat_connecting=True
        self.cat_connect_was_startup=bool(startup)
        self.cat_indicator.setText("◌ CONECTANDO AO RÁDIO…")
        self.cat_indicator.setStyleSheet("font-size:14px;font-weight:800;color:#f2c16b")
        self.cat_indicator.setEnabled(False)
        self.connection.setEnabled(False)
        self.cat_tune_status.setText("CAT: conectando "+port+" (somente leitura inicial)…")
        self.log("CAT: iniciando conexão "+port+"; auto="+str(startup))
        self.background("cat-connect",lambda:self.radio.connect(port,baud,stopbits))

    def toggle_connection(self):
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
        self.cat_indicator.setText("● RÁDIO DESCONECTADO")
        self.cat_indicator.setStyleSheet("font-size:14px;font-weight:800;color:#ff9595")
        self.connection.setText("Conectar")
        self.radio_label.setText("Desconectado")
        self.map_radio_label.setText("CAT desconectado · RX — MHz · TX — MHz · Modo —")
        self.cat_status.setText("● Desconectado · CAT inativo")
        self.cat_status.setStyleSheet("color:#efc17b;font-size:12px")
        self.cat_rx.setText("RX / DOWNLINK (CAT)\\n— MHz")
        self.cat_tx.setText("TX / UPLINK (CAT)\\n— MHz")
        self.cat_details.setText("SAT — · MAIN — · sem leitura atual")
        self.cat_telemetry.setText("Potência: — · Medidor: — · RX/TX: sem leitura CAT")
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
        self.radio_label.setText(f"{st.model} · SAT {'ON' if st.sat else 'OFF'} · RX {self.radio_freq(st.downlink)} | TX {self.radio_freq(st.uplink)} · Modo {st.mode}")
        self.radio_label.setStyleSheet("color:#69e3bc" if st.sat else "color:#f0c186")
        self.last_cat_success=now_utc()
        self.cat_indicator.setText("● TS-2000 CONECTADO · "+self.ports.currentText())
        self.cat_indicator.setStyleSheet("font-size:14px;font-weight:800;color:#67efb2")
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
        self.cat_telemetry.setText(f"Potência: {watts} · Medidor {meter} · RX/TX real: não confirmado (CAT)")

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
        self.summary.setText(f"{len(self.omm)} satélites no catálogo de múltiplas categorias  •  CelesTrak OMM/TLE")
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
        row=self.catalog_table.currentRow()
        item=self.catalog_table.item(row,0) if row>=0 else None
        chosen=str(item.data(Qt.UserRole)) if item is not None else self.sat_combo.currentData()
        ids=transmitter_batch_ids(self.catalog_refresh_scope.currentIndex(),chosen,
            self.enabled_satellite_ids(),self.catalog_filtered_ids(),self.omm)
        if not ids:
            self.catalog_progress.setText("Selecione pelo menos um satélite ou clique em Marcar todos")
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

    def refresh_satellite_table(self, text=None):
        """Virtualized search: thousands of cached satellites must not freeze Qt."""
        query=normalized_satellite_search(
            text if isinstance(text,str) else self.catalog_search.text())
        old_row=self.catalog_table.currentRow()
        previous=self.catalog_table.item(old_row,0) if old_row>=0 else None
        previous_id=str(previous.data(Qt.UserRole)) if previous is not None else None
        checked=set(self.enabled_satellite_ids())
        selected_category=self.catalog_category.currentData() if hasattr(self,"catalog_category") else "all"
        ids=[]
        for ident,obj in self.omm.items():
            if selected_category!="all" and selected_category not in obj.get("CATEGORIES",["amateur"]):
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
                box=QTableWidgetItem("")
                box.setFlags((box.flags()|Qt.ItemIsUserCheckable)&~Qt.ItemIsEditable)
                box.setData(Qt.UserRole,ident)
                box.setCheckState(Qt.Checked if ident in checked else Qt.Unchecked)
                self.catalog_table.setItem(row,0,box)
                for column,value in enumerate(cols,1):
                    cell=QTableWidgetItem(str(value))
                    cell.setData(Qt.UserRole,ident)
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

    def catalog_satellite_checked(self,item):
        """Individual checkbox persists the same explicit selection as bulk actions."""
        if self._loading_catalog or item.column()!=0:return
        ident=str(item.data(Qt.UserRole))
        if ident not in self.omm:return
        updated,_=change_selection(self.omm,[ident],self.enabled_satellite_ids(),
                                   item.checkState()==Qt.Checked,True)
        self.config.values["satellite_selection"]=updated
        self.config.save()
        self.refresh_tracked_table()
        self.filter_sats(self.search.text())
        self.refresh_passes()
        self.catalog_progress.setText(f"Seleção salva: {len(updated)} de {len(self.omm)} satélites")

    def select_catalog_satellite(self,row,col):
        cell=self.catalog_table.item(row,0)
        if cell is None:return
        ident=str(cell.data(Qt.UserRole))
        if ident not in self.enabled_satellite_ids():
            self.config.values["satellite_selection"]=list(dict.fromkeys(self.enabled_satellite_ids()+[ident]))
            self.config.save()
            self.refresh_tracked_table()
        self.search.clear()
        self.filter_sats("")
        idx=self.sat_combo.findData(ident)
        if idx>=0:self.sat_combo.setCurrentIndex(idx)
        self.centralWidget().setCurrentIndex(0)

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

    def choose_satellite(self):
        ident=self.sat_combo.currentData()
        if ident==self._active_satellite_id and self.sat is not None:
            return  # The same satellite must not interrupt CAT.
        self.suspend_cat_doppler("satélite selecionado mudou")
        self.last_freqs=(None,None)
        self.cat_autotune_requested_generation=-1
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
        self.suspend_cat_doppler("transponder/modo mudou")
        self.last_freqs=(None,None)
        self.cat_autotune_requested_generation=-1
        i=self.mode_combo.currentData()
        if not isinstance(i,int) or i<0 or i>=len(self.options):
            self.mode_note.setText("Modo manual: confira cada frequência e modo antes de usar.")
            self.preview_doppler()
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
        self.mode_note.setText(f"SatNOGS · {'Inversor' if opt['inverted'] else 'Não inversor'} · {'somente recepção (sem TX CAT)' if opt['receive_only'] else 'uplink/downlink'} · confira a situação operacional do satélite")
        self.preview_doppler()
        self.cat_selection_generation+=1
        if self.cat_tracking_armed:
            self.auto_tune_selected_satellite()

    def arm_cat_tracking(self,*args):
        """Called only for an explicit user selection, not session restoration."""
        if not self.config.values.get("cat_auto_select",True):
            self.cat_tune_status.setText("Auto CAT desativado pelo operador")
            return
        self.cat_tracking_armed=True
        self.last_freqs=(None,None)
        self.cat_autotune_requested_generation=-1
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

    def track_cat_frequencies(self,now):
        """A confirmed, operator-armed Auto CAT profile tracks Doppler via worker."""
        if not self.cat_tracking_armed or not self.config.values.get("cat_auto_select",True):
            return
        if not self.radio.connected or not self.radio.state.sat:
            self.cat_tune_status.setText("CAT: rastreamento pausado · desconectado ou SAT OFF")
            return
        if not self.sat or not self.last_pos or not self.omm_fresh():
            return
        if (self.last_freqs==(None,None)
                and self.cat_autotune_requested_generation!=self.cat_selection_generation
                and self.down_edit.text().strip()):
            # When a saved/updated catalog becomes ready, initiate once.
            self.auto_tune_selected_satellite()
            return
        if self.last_freqs==(None,None):
            return
        if any(k in self.pending_jobs for k in ("cat-autotune","cat-track","cat-connect","cat-diagnostic")):
            return
        # A manual MAIN/SAT-Uplink dial change must not trigger a VFO tug-of-war.
        # Pausing explicitly is safer than overwriting the operator\'s adjustment.
        current=self.radio.state
        if (self.last_freqs[0] is not None and self.last_freqs[1] is not None
            and current.uplink is not None and current.downlink is not None
            and max(abs(current.uplink-self.last_freqs[0]),
                    abs(current.downlink-self.last_freqs[1])) > max(100,2*int(self.threshold.value()))):
            self.cat_tracking_armed=False
            self.cat_tune_status.setText("CAT: PAUSADO · ajuste manual detectado no TS-2000; selecione o satélite para retomar")
            self.log("CAT: alteração manual de FA/FB detectada; Auto CAT pausado para preservar a sintonia do operador")
            return
        if not cat_doppler_allowed(self.last_pos["visible"],
                self.config.values.get("cat_doppler_out_of_view",True)):
            return
        if time.monotonic()-self.last_tracking_write < max(0.25,float(
                self.interval.value())):
            return
        try:
            ul,dl=self.corrected()
            safe,reason=self.selected_cat_pair_info(ul,dl)
            if not safe:
                self.cat_tracking_armed=False
                self.cat_tune_status.setText("CAT: acompanhamento bloqueado · "+reason)
                return
            threshold=max(1,int(self.threshold.value()))
            if (self.last_freqs[0] is not None and self.last_freqs[1] is not None
                and max(abs(ul-self.last_freqs[0]),abs(dl-self.last_freqs[1]))<threshold):
                return
            generation=self.cat_selection_generation
            self.last_tracking_write=time.monotonic()
            self.cat_last_requested=(ul,dl)
            started=self.last_tracking_write
            self.cat_tune_status.setText("Auto CAT · corrigindo Doppler no TS-2000…")
            def task():
                if generation!=self.cat_selection_generation or not self.radio.connected:
                    return generation,None,None,None,0.0
                state=self.radio.set_frequencies(ul,dl)
                return generation,state,ul,dl,time.monotonic()-started
            self.background("cat-track",task)
        except (ValueError,TypeError,KeyError) as exc:
            self.cat_tune_status.setText("CAT rastreio aguardando: "+str(exc))

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
            self.last_pos=position(self.sat,self.saved_station(),ts=self.ts)
            self.track_cat_frequencies(now_utc())
        except Exception as exc:
            self.cat_sync_status.setText("CAT SYNC · previsão indisponível: "+str(exc)[:105])

    def update_cat_sync_status(self,state):
        """Compare the latest predicted Hz with the radio's readback, not UI labels."""
        predicted=self.cat_last_requested
        if predicted[0] is None or predicted[1] is None:
            self.cat_sync_status.setText("CAT SYNC · FA/FB lidos · previsão ainda não enviada")
            return
        if state.uplink is None or state.downlink is None:
            self.cat_sync_status.setText("CAT SYNC · aguardando FA/FB do rádio")
            return
        rx_delta=predicted[1]-state.downlink
        tx_delta=predicted[0]-state.uplink
        lag="—" if self.cat_last_roundtrip_ms is None else str(self.cat_last_roundtrip_ms)+" ms"
        result=("SINCRONIZADO" if max(abs(rx_delta),abs(tx_delta))<=max(1,int(self.threshold.value()))
                else "DIVERGENTE")
        self.cat_sync_status.setText(
            f"CAT {result} · RX Δ{rx_delta:+d} Hz · TX Δ{tx_delta:+d} Hz · "
            f"último comando {lag} · FA {state.downlink/1e6:.6f} / FB {state.uplink/1e6:.6f} MHz")

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
        if not self.radio.state.sat:
            return blocked("SAT está OFF no TS-2000; ative em Configurações → Conexão CAT")
        if not self.omm_fresh():
            return blocked("OMM/TLE vencido; atualize elementos orbitais antes de sintonizar")
        if "cat-autotune" in self.pending_jobs:
            self.cat_tune_status.setText("CAT: nova seleção aguardando sintonia anterior…")
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
                f"RX / DOWNLINK · {rx_mode}\n{self.radio_freq(calc['rx_hz'])}\nDoppler {calc['rx_offset_hz']:+d} Hz")
            self.pred_tx.setText(
                f"TX / UPLINK · {tx_mode}\n{self.radio_freq(calc['tx_hz'])}\nDoppler {calc['tx_offset_hz']:+d} Hz"
                if ul is not None else "TX / UPLINK\nSOMENTE RECEPÇÃO\nSem frequência TX")
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

    def change_cat_outside(self,enabled):
        self.config.values["cat_doppler_out_of_view"]=bool(enabled)
        self.config.save()
        if not enabled and self.doppler_checkbox.isChecked() and self.last_pos and not self.last_pos["visible"]:
            self.suspend_cat_doppler("permissão fora da visada desativada")

    def doppler_state_changed(self):
        if self.doppler_checkbox.isChecked():
            try:
                self.saved_station();self.corrected()
                if not self.radio.connected or not self.radio.state.sat:
                    raise ValueError("Conecte ao TS-2000 e ative SAT antes de habilitar o Doppler")
                if not cat_doppler_allowed(self.last_pos['visible'],self.config.values.get('cat_doppler_out_of_view',False)):
                    raise ValueError('Satélite fora da visada; habilite CAT fora da visada em Configurações')
                if not self.omm_fresh():
                    raise ValueError('OMM antigo: atualize antes de controlar o rádio automaticamente')
                scope='inclusive fora da visada' if self.config.values.get('cat_doppler_out_of_view',False) else 'durante a passagem visível'
                if QMessageBox.question(self,'Ativar Doppler',f'Permitir alterar periodicamente FA/FC {scope}?') != QMessageBox.Yes:
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
        c=self.config.values
        event=select_next_pass(self.passes,self.pass_rows,c.get("radio_modes",[]),c.get("radio_bands",[]),
                               now,self.pass_enabled)
        self.next_candidate=event
        self.next_select.setEnabled(event is not None)
        if event is None:
            self.next_event_label.setText("Nenhuma passagem com canal publicado compatível")
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
        if "passes" in self.pending_jobs:
            self._passes_refresh_again=True
            return
        try:station=self.saved_station()
        except Exception:
            self.pass_table.setRowCount(0)
            return
        selected=set(self.enabled_satellite_ids())
        self.pass_enabled=selected
        self.pass_rows={sid:load_transmitters(self.config.dir,int(sid)) for sid in selected}
        entries=[(ident,obj) for ident,obj in self.omm.items() if ident in selected]
        if len(entries)>150:
            self.log("Agenda: limite de 150 satélites simultâneos; refine a seleção para preservar a responsividade.")
            entries=entries[:150]
        # Capture immutable snapshot; skyfield object construction in background.
        def task():
            out=[]
            for ident,obj in entries:
                try:
                    sat=make_satellite(obj,self.ts)
                    # Include genuine AOS for passes already in progress at startup.
                    passes=predict_passes(sat,station,now=now_utc()-timedelta(hours=3),hours=39,ts=self.ts)
                    for p in passes:
                        out.append({**p,'id':ident,'name':obj.get('OBJECT_NAME',ident)})
                except Exception:
                    continue
            out=[p for p in out if p['los']>now_utc()]
            out.sort(key=lambda p:p['aos'])
            return out[:100]
        self.background('passes',task)

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

    def select_pass_satellite(self,row,col):
        if 0<=row<len(self.passes):
            ident=self.passes[row]['id']
            self.search.clear()
            index=self.sat_combo.findData(ident)
            if index>=0:self.sat_combo.setCurrentIndex(index)

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
                     "label":f"{self.sat.name} · elevação {pos['elevation']:.1f}° · alcance {pos['range_km']:.0f} km · órbita TLE/OMM"}
            self.map.page().runJavaScript('window.updateOrbit && window.updateOrbit('+json.dumps(payload)+');')
            # A past error banner must not survive a successful map render.
            self.map_desc.setText("Trajetória passada reconstruída · futuro previsto por OMM/TLE · Natural Earth offline")
        except (ValueError,TypeError) as exc:
            self.map_desc.setText(f"Cadastre uma estação válida para calcular a órbita: {exc}")
        except Exception as exc:
            self.map_desc.setText(f"Erro ao atualizar a órbita: {exc}")
            self.log(f"Mapa/órbita: {exc}")

    def check_selected_aos_alarm(self,now):
        """Alert for selected NORAD only; never write to the radio."""
        if not self.config.values.get("aos_alarm_enabled",True):
            return
        selected=self.sat_combo.currentData()
        seen=set(self.config.values.get("aos_alarm_fired",[]))
        found=selected_aos_alarm(self.passes,selected,now,seen,30)
        if not found:
            if self.aos_alarm_dialog is not None and self.aos_alarm_target is not None:
                _,row,_=self.aos_alarm_target
                remaining=max(0,int((row["aos"]-now).total_seconds()))
                self.aos_alarm_dialog.setInformativeText(
                    f"AOS em {format_duration(remaining)} · "
                    f"horário local {row['aos'].astimezone():%H:%M:%S} · "
                    f"UTC {row['aos']:%H:%M:%S} · "
                    f"elevação máxima {row.get('max_el',0):.0f}°")
            return
        key,row,remaining=found
        self.config.values["aos_alarm_fired"]=(list(seen)+[key])[-160:]
        self.config.save()
        self.aos_alarm_target=found
        dialog=QMessageBox(self)
        dialog.setWindowTitle("Alerta de aproximação — AOS")
        dialog.setIcon(QMessageBox.Information)
        dialog.setText(f"Satélite {row.get('name',selected)} · NORAD {selected}\n"
                       f"Entrará no horizonte em {format_duration(remaining)}!")
        dialog.setInformativeText(f"AOS {row['aos'].astimezone():%d/%m %H:%M:%S} local · "
                                  f"{row['aos']:%H:%M:%S} UTC · "
                                  f"elevação máxima {row.get('max_el',0):.0f}°")
        go=dialog.addButton("Ir para Operação",QMessageBox.ActionRole)
        dialog.addButton("Silenciar / Fechar",QMessageBox.RejectRole)
        go.clicked.connect(lambda:self.tabs.setCurrentIndex(0))
        dialog.finished.connect(lambda *_:setattr(self,"aos_alarm_dialog",None))
        dialog.setWindowFlag(Qt.WindowStaysOnTopHint,True)
        self.aos_alarm_dialog=dialog
        dialog.show()
        if self.config.values.get("aos_alarm_sound",True):
            QApplication.beep()
        self.log(f"Alarme AOS: NORAD {selected} em {remaining:.0f} s")

    def tick(self):
        # No network calls in the GUI tick; asynchronous check respects the configured period.
        if int(now_utc().timestamp()) % 60 == 0:
            self.check_for_updates()
        now=now_utc();self.utc.setText(now.strftime('DATA/HORA UTC · %d/%m/%Y %H:%M:%S'))
        self.update_next_indicator()
        self.check_selected_aos_alarm(now)
        self.poll_station_map()
        if self.sat:
            try:
                station=self.saved_station()
                pos=position(self.sat,station,ts=self.ts)
                self.last_pos=pos
                formats={'elevation':f"{pos['elevation']:.1f}°",'azimuth':f"{pos['azimuth']:.1f}°",
                         'range_km':f"{pos['range_km']:.0f} km",'radial_m_s':f"{pos['radial_m_s']:+.1f} m/s",
                         'height_km':f"{pos['height_km']:.0f} km"}
                for k,v in formats.items():self.orbit_metrics[k].setText(v)
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
            interval=8.0 if active else max(1,int(self.config.values.get("poll_interval_s",1)))
            if (time.monotonic()-self.last_cat_poll_started>=interval
                    and not any(k in self.pending_jobs for k in (
                        "cat-connect","cat-autotune","cat-track","cat-diagnostic","cat-poll"))):
                self.last_cat_poll_started=time.monotonic()
                self.background("cat-poll",self.radio.poll_tracking if active else self.radio.poll)
        if self.radio.connected and self.last_cat_success:
            age=(now-self.last_cat_success).total_seconds()
            if age>10:
                self.map_radio_label.setText(f"CAT sem leitura há {age:.0f}s · valores desatualizados")
                self.map_radio_label.setStyleSheet("color:#e3ad61;font-weight:700")
                self.cat_indicator.setText(f"! CAT SEM RESPOSTA HÁ {age:.0f}s")
                self.cat_indicator.setStyleSheet("font-size:14px;font-weight:800;color:#ffbf6f")
                self.cat_status.setText(f"● CAT desatualizado há {age:.0f}s")
                self.cat_status.setStyleSheet("color:#efc17b;font-size:12px")
                self.cat_details.setText("Leitura CAT vencida · conferir cabo e porta COM")
                self.cat_live_label.setText(f"RÁDIO REAL (CAT) · última leitura há {age:.0f}s, não confirmada")
                self.cat_sat_orientation.setText("SAT: resposta CAT desatualizada")
                self.cat_telemetry.setText("Potência/medidores: dados desatualizados")
                for widget in (self.smeter_main,self.smeter_sub):
                    widget.setValue(0);widget.setFormat("sem leitura")

    def background_result(self,key,data):
        self.pending_jobs.discard(key)
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
            self.cat_connecting=False
            self.cat_indicator.setEnabled(True)
            self.connection.setEnabled(True)
            self.connection.setText("Desconectar")
            self.cat_diagnose.setEnabled(True)
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
                self.last_cat_track_completed=time.monotonic()
                self.cat_last_roundtrip_ms=round(elapsed*1000)
                self.render_radio_state(state)
                self.update_cat_sync_status(state)
                self.cat_tune_status.setText("Auto CAT ONLINE · FA/FB confirmados · "
                                             +str(self.cat_last_roundtrip_ms)+" ms")
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
                self.render_radio_state(data)
                self.update_cat_sync_status(data)
            return
        if key=='update-check':
            self.manual_update_requested = False
            self.available_update=data
            if data:
                self.version_btn.setText(f'Versão {data.version} disponível')
                self.version_btn.setStyleSheet('background:#ae6616;color:white;border:1px solid #eda847')
                if self.config.values.get('last_update_notice')!=data.version:
                    self.config.values['last_update_notice']=data.version
                    self.config.save()
                    QMessageBox.information(self,'Atualização disponível',
                        f'Nova versão v{data.version}. Clique no botão laranja da barra superior para atualizar.\n\n{data.body[:3200]}')
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
            self.passes=data[:75]
            self.pass_table.setRowCount(len(self.passes))
            for i,p in enumerate(self.passes):
                aos=p['aos'].astimezone().strftime('%d/%m %H:%M')
                peak=p['tca'].astimezone().strftime('%d/%m %H:%M') if p.get('tca') else '—'
                los=p['los'].astimezone().strftime('%d/%m %H:%M')
                modes=self.suggested_mode_text(p['id'])
                for j,value in enumerate((p['name'],aos,peak,los,f"{p['max_el']:.0f}",modes)):
                    self.pass_table.setItem(i,j,QTableWidgetItem(value))
            self.log(f'Previsão: {len(data)} passagens nas próximas 36 h (lista limitada a 100)')
            self.update_next_indicator()
            self.prefetch_upcoming_modes()
            if self._passes_refresh_again:
                self._passes_refresh_again=False
                self.refresh_passes()

    def background_error(self,key,message):
        self.pending_jobs.discard(key)
        self.log(f'Falha {key}: {message}')
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
        if key=="cat-connect":
            self.cat_connecting=False
            self.cat_indicator.setEnabled(True)
            self.connection.setEnabled(True)
            self.connection.setText("Conectar")
            self.cat_diagnose.setEnabled(False)
            self.cat_indicator.setText("! CAT DESCONECTADO / ERRO")
            self.cat_indicator.setStyleSheet("font-size:14px;font-weight:800;color:#ff9595")
            self.cat_tune_status.setText("CAT: conexão falhou · "+message)
            self.log("CAT: falha ao conectar: "+message)
            if not self.cat_connect_was_startup:
                QMessageBox.warning(self,"Falha de conexão CAT",message)
            return
        if key=="cat-track":
            self.cat_tracking_armed=False
            self.cat_tune_status.setText("CAT: rastreamento pausado · "+message)
            self.log("CAT contínuo pausado após falha: "+message)
            if self.radio.connected:
                self.background("cat-poll",self.radio.poll)
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
                self.cat_indicator.setText("● RÁDIO DESCONECTADO")
                self.cat_indicator.setStyleSheet("font-size:14px;font-weight:800;color:#ff9595")
            if was_manual:
                QMessageBox.warning(self,"Falha ao sintonizar TS-2000",
                                    "O rádio não confirmou a sintonia solicitada. "
                                    "Isso não significa, necessariamente, perda da conexão CAT.\n\n"
                                    +message+"\n\nVeja também LOGs / CAT.")
            # Retry only when a NEW explicit, valid satellite selection exists.
            # A stale/unconfigured selection must not erase the real CAT error.
            if (self.config.values.get("cat_auto_select",False) and self.radio.connected
                    and self.sat is not None and self.sat_combo.currentData()
                    and self.cat_autotune_requested_generation!=self.cat_selection_generation):
                self.auto_tune_selected_satellite()
            return
        if key=="cat-diagnostic":
            self.cat_diagnose.setEnabled(self.radio.connected)
            self.cat_tune_status.setText("CAT: diagnóstico falhou · "+message)
            QMessageBox.warning(self,"Falha no diagnóstico CAT",message)
            return
        if key=="cat-poll":
            self.cat_live_label.setText("RÁDIO REAL (CAT) · erro de leitura")
            self.cat_sat_orientation.setText("SAT: sem resposta atual")
            self.cat_indicator.setText("! ERRO DE LEITURA CAT")
            self.cat_indicator.setStyleSheet("font-size:14px;font-weight:800;color:#ffbf6f")
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
            if key=='update-download' or self.manual_update_requested:
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
        return choose_satellites(self.omm,rows,c.get("radio_modes",[]),
                                 c.get("radio_bands",[]),c.get("satellite_selection"))

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

    def closeEvent(self,event):
        self.doppler_checkbox.setChecked(False)
        self.radio.disconnect()
        event.accept()


def main():
    app=QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window=MainWindow()
    window.show()
    sys.exit(qt_exec(app))
