"""PT2VHF Sat Tool desktop Windows MVP.

UI is intentionally non-transmitting: no CAT TX/PTT commands exist.
"""
from __future__ import annotations
import json
import math
import sys
import threading
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .qt_compat import Qt, QTimer, QObject, Signal, QUrl
from .qt_compat import QDoubleValidator, QFont
from .qt_compat import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QGroupBox, QTabWidget, QPlainTextEdit,
    QSplitter, QMessageBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QAbstractItemView, QProgressDialog, QScrollArea,
)
from .qt_compat import QWebEngineView, QGeoPositionInfoSource, qt_exec, QT_BINDING
from skyfield.api import load
from . import __version__
from .cat import TS2000, available_ports
from .catalog import refresh_orbits, load_orbits, refresh_transmitters, load_transmitters, age_hours
from .config import Config
from .satellite_info import orbital_characteristics, operational_characteristics, characteristics_text
from .updater import check_for_update, download_update, install_flavor, launch_staged_update
from .profile import choose_satellites, capability, render_service
from .media import find_photo, photo_html
from .core import (Station, now_utc, make_satellite, position, ground_track, footprint,
                   predict_passes, transponder_options, doppler_frequencies, paired_linear_uplink)

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
"""

class Events(QObject):
    result = Signal(str, object)
    failure = Signal(str, str)
    progress = Signal(int, int)


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
        self.setWindowTitle(f"PT2VHF Sat Tool • {__version__}")
        self.resize(1550, 890)
        self.setMinimumSize(1100, 700)
        self.config = Config()
        self.ts = load.timescale(builtin=True)
        self.radio = TS2000(self.log)
        self.events = Events()
        self.events.result.connect(self.background_result)
        self.events.failure.connect(self.background_error)
        self.events.progress.connect(self.download_progress)
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
        self.last_freqs = (None, None)
        self.last_radio_poll = 0
        self.last_cat_success = None
        self._loading_satellites = False
        self.pos_source = None
        self.init_ui()
        self.load_fields()
        self.populate_catalog(load_orbits(self.config.dir))
        self.update_ports()
        if age_hours(self.config.dir,"amateur_omm.json") is None or age_hours(self.config.dir,"amateur_omm.json")>self.config.values.get("tle_update_hours",4):
            self.refresh_catalog()
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(1000)
        self.tick()
        # Delay startup network I/O until the UI is visible.
        QTimer.singleShot(12000, self.check_for_updates)

    def log(self, message):
        if hasattr(self, 'log_view'):
            self.log_view.appendPlainText(f"{datetime.now().astimezone():%H:%M:%S}  {message}")

    def background(self, key, fn):
        if key in self.pending_jobs:
            return
        self.pending_jobs.add(key)
        def run():
            try:
                value = fn()
                self.events.result.emit(key, value)
            except Exception as exc:
                self.events.failure.emit(key, str(exc))
        threading.Thread(target=run, name='sat-'+key, daemon=True).start()

    def init_ui(self):
        root = QTabWidget()
        self.setCentralWidget(root)
        operation = QWidget(); op = QVBoxLayout(operation); op.setContentsMargins(12,12,12,10)
        op.setSpacing(9)
        header = QHBoxLayout()
        headline = QLabel("PT2VHF  /  SAT TOOL")
        headline.setStyleSheet("font-size:21px;font-weight:800;color:#e9fbff")
        header.addWidget(headline)
        self.version_btn = QPushButton(f"v{__version__} · verificar atualização")
        self.version_btn.setToolTip("Verificar versões no GitHub; iniciar atualização com autorização")
        self.version_btn.clicked.connect(lambda: self.request_update(manual=True))
        header.addWidget(self.version_btn)
        self.summary = label("Dados orbitais não carregados")
        self.summary.setStyleSheet('color:#85aaba')
        header.addWidget(self.summary, 1)
        self.utc = QLabel("UTC")
        header.addWidget(self.utc)
        op.addLayout(header)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        left = QWidget(); lv=QVBoxLayout(left);lv.setContentsMargins(3,0,3,0)
        pick,pv=group("SATÉLITE E TRANSPONDER")
        self.search = QLineEdit();self.search.setPlaceholderText("Filtrar satélites por nome / NORAD...")
        self.search.textChanged.connect(self.filter_sats)
        pv.addWidget(self.search)
        self.sat_combo = QComboBox()
        self.sat_combo.currentIndexChanged.connect(self.choose_satellite)
        pv.addWidget(self.sat_combo)
        self.sat_detail = label("Atualize o catálogo OMM")
        self.sat_detail.setStyleSheet("color:#a9c5d9")
        pv.addWidget(self.sat_detail)
        self.photo=QWebEngineView()
        self.photo.setMaximumHeight(165)
        self.photo.setHtml(photo_html(None))
        pv.addWidget(self.photo)
        self.refresh_omm_btn = QPushButton("Atualizar órbitas (OMM + TLE)")
        self.refresh_omm_btn.clicked.connect(self.refresh_catalog)
        pv.addWidget(self.refresh_omm_btn)
        self.mode_combo=QComboBox()
        self.mode_combo.currentIndexChanged.connect(self.choose_mode)
        pv.addWidget(label("Transponder / canal / modo operacional"));pv.addWidget(self.mode_combo)
        self.refresh_tx_btn=QPushButton("Atualizar frequências / modos")
        self.refresh_tx_btn.clicked.connect(lambda:self.refresh_modes(force=True))
        pv.addWidget(self.refresh_tx_btn)
        lv.addWidget(pick)
        freqs,fv=group("FREQUÊNCIAS NOMINAIS")
        form=QGridLayout()
        self.down_edit=QLineEdit();self.up_edit=QLineEdit()
        for inp in (self.down_edit,self.up_edit):
            inp.setPlaceholderText("MHz (ex. 145.825000)")
            inp.setValidator(QDoubleValidator(0.0,1300.0,6,inp))
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
        self.doppler_checkbox=QCheckBox("Doppler automático (somente em passagem)")
        self.doppler_checkbox.stateChanged.connect(self.doppler_state_changed)
        fv.addWidget(self.doppler_checkbox)
        self.frequency_apply=QPushButton("Aplicar RX/TX no TS-2000")
        self.frequency_apply.setObjectName('primary')
        self.frequency_apply.clicked.connect(self.apply_freqs)
        fv.addWidget(self.frequency_apply)
        self.apply_main_mode=QPushButton("Aplicar modo RX (MAIN)")
        self.apply_main_mode.clicked.connect(self.apply_rx_mode)
        fv.addWidget(self.apply_main_mode)
        lv.addWidget(freqs)
        lv.addStretch(1)
        splitter.addWidget(left)
        mid=QWidget();mv=QVBoxLayout(mid);mv.setContentsMargins(0,0,0,0)
        self.map=QWebEngineView()
        self.map.setHtml(Path(__file__).with_name("map.html").read_text(encoding="utf-8"),
                         QUrl("https://www.openstreetmap.org/"))
        mv.addWidget(self.map,1)
        self.map_radio_label=label("CAT desconectado · RX — MHz · TX — MHz · Modo —")
        self.map_radio_label.setStyleSheet("font-size:13px;color:#f0c186;font-weight:700")
        mv.addWidget(self.map_radio_label)
        self.map_desc=label("Trajetória orbital · footprint · sua estação · OSM")
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
        rv.addWidget(nextpass,1)
        splitter.addWidget(right)
        splitter.setSizes([285,830,375])
        op.addWidget(splitter,1)
        radio_box,rb=group("KENWOOD TS-2000  •  CAT SERIAL")
        row=QHBoxLayout()
        self.ports=QComboBox();self.refresh_ports=QPushButton("↻ Portas")
        self.refresh_ports.clicked.connect(self.update_ports)
        self.baud_combo=QComboBox();self.baud_combo.addItems(["4800","9600","19200","38400","57600"])
        self.stops_combo=QComboBox();self.stops_combo.addItems(["1","2"])
        self.connection=QPushButton("Conectar")
        self.connection.clicked.connect(self.toggle_connection)
        self.enable_sat=QPushButton("Ativar SAT / desativar TRACE")
        self.enable_sat.clicked.connect(self.enable_satellite)
        row.addWidget(label("Porta:"));row.addWidget(self.ports,2)
        row.addWidget(self.refresh_ports);row.addWidget(label("Baud:"));row.addWidget(self.baud_combo)
        row.addWidget(label("Stop:"));row.addWidget(self.stops_combo);row.addWidget(self.connection)
        row.addWidget(self.enable_sat)
        rb.addLayout(row)
        row2=QHBoxLayout()
        self.radio_label=label("Desconectado · CAT inativo · transmissão nunca acionada pelo aplicativo")
        self.radio_label.setStyleSheet('color:#ecc48f')
        self.corrected_label=label("Doppler RX: —  |  TX: —")
        row2.addWidget(self.radio_label,2);row2.addWidget(self.corrected_label,1)
        rb.addLayout(row2)
        op.addWidget(radio_box)
        root.addTab(operation,"Operação")
        catalog_page=QWidget(); catalog_layout=QVBoxLayout(catalog_page)
        catalog_layout.addWidget(label("Satélites atuais no catálogo orbital CelesTrak. 'Canal publicado' não comprova serviço ativo nem autoriza TX. Clique duas vezes para selecionar."))
        self.catalog_search=QLineEdit()
        self.catalog_search.setPlaceholderText("Filtrar nome, NORAD, modo ou frequência…")
        self.catalog_search.textChanged.connect(self.refresh_satellite_table)
        catalog_layout.addWidget(self.catalog_search)
        self.catalog_table=QTableWidget(0, 7)
        self.catalog_table.setHorizontalHeaderLabels(["Satélite", "NORAD", "Inclinação", "Período", "Modos", "Downlink MHz", "Situação"])
        self.catalog_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.catalog_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.catalog_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.catalog_table.cellDoubleClicked.connect(self.select_catalog_satellite)
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
        place=QHBoxLayout()
        self.get_position=QPushButton("Obter coordenadas do computador")
        self.get_position.clicked.connect(self.geolocate)
        self.save_station_btn=QPushButton("Salvar estação")
        self.save_station_btn.setObjectName('primary')
        self.save_station_btn.clicked.connect(self.save_station)
        place.addWidget(self.get_position);place.addWidget(self.save_station_btn)
        sg.addLayout(place)
        sg.addWidget(label("A captura utiliza o serviço de localização do sistema (quando disponível). Não substitui coordenadas GPS precisas para previsão de passagens."))
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
        self.config_port=QComboBox();self.config_port.setEditable(True)
        rr.addWidget(label("Fabricante"));rr.addWidget(self.radio_brand)
        rr.addWidget(label("Modelo"));rr.addWidget(self.radio_model)
        rr.addWidget(label("Porta COM"));rr.addWidget(self.config_port)
        rs.addLayout(rr)
        rs.addWidget(label("Ajustes de baud rate e stop bits ficam na faixa CAT da aba Operação. Somente o TS-2000 tem driver nesta versão."))
        connect_btn=QPushButton("Conectar pela porta selecionada")
        connect_btn.clicked.connect(self.connect_from_settings)
        rs.addWidget(connect_btn);cfg.addWidget(radio_settings)

        sel_group,ss=group("SATÉLITES VISÍVEIS NA PÁGINA PRINCIPAL")
        ss.addWidget(label("Auto sugere satélites por FM/SSB/CW e banda. A confirmação de funcionamento depende das fontes atuais."))
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
        button=QPushButton("Salvar intervalo TLE")
        button.clicked.connect(self.save_tle_settings);tg.addWidget(button)
        cfg.addWidget(tle_group)
        advanced,adv=group("DOPPLER E SEGURANÇA")
        self.interval=QDoubleSpinBox();self.interval.setRange(1,15);self.interval.setSuffix(' segundos')
        self.threshold=QDoubleSpinBox();self.threshold.setRange(5,1000);self.threshold.setSuffix(' Hz')
        ag=QGridLayout();ag.addWidget(label("Intervalo de ajuste automático"),0,0);ag.addWidget(self.interval,0,1)
        ag.addWidget(label("Mínima variação para reprogramar CAT"),1,0);ag.addWidget(self.threshold,1,1)
        adv.addLayout(ag)
        adv.addWidget(label("Proteções: Doppler automático desabilitado por padrão; somente com SAT confirmado, efeméride recente, passagens acima do horizonte configurado e frequências definidas. O programa não envia PTT."))
        cfg.addWidget(advanced)
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
        cfg.addStretch(1)
        root.addTab(config_page,"Configurações")
        logs=QWidget();ll=QVBoxLayout(logs)
        self.log_view=QPlainTextEdit();self.log_view.setReadOnly(True)
        ll.addWidget(self.log_view)
        clear=QPushButton("Limpar logs da tela");clear.clicked.connect(self.log_view.clear)
        ll.addWidget(clear)
        root.addTab(logs,"LOGs / CAT")
        about=QWidget();about_layout=QVBoxLayout(about)
        about_layout.addWidget(label(f"PT2VHF Sat Tool v{__version__} — Controle CAT do TS-2000"))
        about_layout.addWidget(label("Distribuição: Windows 7 / Windows 11; instalador Setup EXE e portátil EXE único."))
        about_layout.addWidget(label("Elementos orbitais: CelesTrak OMM/TLE. Transponders e modos: SatNOGS (créditos e licenças nos provedores)."))
        about_layout.addWidget(label("Repositório: https://github.com/alexpmr/PT2VHF-Sat-Tool · Licença MIT"))
        btn=QPushButton("Verificar versão");btn.clicked.connect(lambda:self.request_update(manual=True))
        about_layout.addWidget(btn);about_layout.addStretch()
        root.addTab(about,"Sobre")
        self.statusBar().showMessage("PT2VHF Sat Tool • Monitoramento passivo | TX/PTT não controlado")

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
        self.stops_combo.setCurrentText(str(c['stopbits']))
        self.interval.setValue(float(c['update_interval_s']))
        self.threshold.setValue(float(c['tune_threshold_hz']))
        self.update_minutes.setValue(float(c.get('version_check_minutes',15)))
        self.include_prerelease.setChecked(bool(c.get('include_prereleases', True)))
        # Always require an explicit enable on each launch to avoid surprise CAT writes.
        self.doppler_checkbox.setChecked(False)

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
            self.version_btn.setText(f'v{__version__} · desenvolvimento')
            return
        self.update_last_checked=now
        variant,kind=self.update_distribution
        self.version_btn.setText(f'v{__version__} · verificando…')
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
        self.refresh_passes()
        self.update_map()

    def geolocate(self):
        try:
            source=QGeoPositionInfoSource.createDefaultSource(self)
            if source is None:
                raise RuntimeError("O sistema não forneceu um provedor de localização")
            self.pos_source=source
            source.positionUpdated.connect(self.position_found)
            source.updateTimeout.connect(lambda:QMessageBox.warning(self,"Localização","Sem coordenadas: habilite a permissão de localização do Windows ou digite manualmente."))
            source.requestUpdate(12000)
            self.log("Solicitada a localização do computador ao sistema operacional")
        except Exception as exc:
            QMessageBox.warning(self,"Localização indisponível",f"{exc}\nInforme as coordenadas manualmente ou habilite a localização no Windows.")

    def position_found(self, info):
        coord=info.coordinate()
        if not coord.isValid(): return
        self.lat.setText(f"{coord.latitude():.7f}")
        self.lon.setText(f"{coord.longitude():.7f}")
        if coord.altitude() and math.isfinite(coord.altitude()):
            self.altitude.setValue(coord.altitude())
        self.log("Coordenadas obtidas do serviço de localização do computador; confirme antes de salvar")
        QMessageBox.information(self,"Localização recebida","Latitude e longitude preenchidas. Confira a precisão e clique em Salvar estação.")

    def update_ports(self):
        previous=self.ports.currentText() or self.config.values['port']
        ports=available_ports()
        self.ports.clear()
        self.ports.addItems(ports)
        if previous in ports:self.ports.setCurrentText(previous)
        if hasattr(self,"config_port"):
            selected=self.config_port.currentText() or previous
            self.config_port.clear();self.config_port.addItems(ports)
            if selected:self.config_port.setCurrentText(selected)

    def toggle_connection(self):
        if self.radio.connected:
            self.doppler_checkbox.setChecked(False)
            self.radio.disconnect()
            self.connection.setText("Conectar")
            self.radio_label.setText("Desconectado")
            self.map_radio_label.setText("CAT desconectado · RX — MHz · TX — MHz · Modo —")
            self.log("CAT desconectado")
            return
        try:
            st=self.radio.connect(self.ports.currentText(), int(self.baud_combo.currentText()), int(self.stops_combo.currentText()))
            self.config.values.update({"port":self.ports.currentText(),"baud":int(self.baud_combo.currentText()),
                                       "stopbits":int(self.stops_combo.currentText())})
            self.config.save()
            self.connection.setText("Desconectar")
            self.render_radio_state(st)
        except Exception as exc:
            QMessageBox.critical(self,"Erro de conexão CAT",str(exc))
            self.log(f"ERRO CAT: {exc}")

    def enable_satellite(self):
        try:
            if not self.radio.connected: raise ConnectionError("Conecte ao TS-2000 primeiro")
            msg="O TS-2000 será colocado em modo SAT, com MAIN=RX, SUB=TX e TRACE desativado. Continuar?"
            if QMessageBox.question(self,"Configurar SAT",msg) != QMessageBox.Yes:return
            self.render_radio_state(self.radio.enable_satellite_mode())
        except Exception as exc:
            QMessageBox.critical(self,"CAT",str(exc))

    def render_radio_state(self, st):
        self.radio_label.setText(f"{st.model}  •  SAT {'ON' if st.sat else 'OFF'}  •  FA RX: {st.downlink/1e6:.6f} MHz  |  FB TX: {st.uplink/1e6:.6f} MHz  •  MD: {st.mode}")
        self.radio_label.setStyleSheet("color:#69e3bc" if st.sat else "color:#f0c186")
        self.last_cat_success=now_utc()
        self.map_radio_label.setText(f"CAT · {st.model} · SAT {'ON' if st.sat else 'OFF'} · RX {st.downlink/1e6:.6f} MHz · TX {st.uplink/1e6:.6f} MHz · Modo {st.mode} · {self.last_cat_success.astimezone():%H:%M:%S}")
        self.map_radio_label.setStyleSheet("font-size:13px;color:#69e3bc;font-weight:700")

    def refresh_catalog(self):
        age=age_hours(self.config.dir,"amateur_omm.json")
        if age is not None and age<2:
            self.summary.setText(f"OMM em cache há {age:.1f} h; nova consulta permitida após 2 h")
            return
        self.summary.setText("Atualizando elementos orbitais…")
        self.background('omm',lambda:refresh_orbits(self.config.dir))

    def populate_catalog(self, objects):
        old=self.sat_combo.currentData() or self.config.values.get('selected_norad')
        self.omm={str(o['NORAD_CAT_ID']):o for o in objects if o.get('NORAD_CAT_ID')}
        self.filter_sats(self.search.text())
        if old:
            idx=self.sat_combo.findData(str(old))
            if idx>=0:self.sat_combo.setCurrentIndex(idx)
        self.summary.setText(f"{len(self.omm)} satélites no catálogo amador  •  CelesTrak OMM/TLE")
        self.refresh_satellite_table()
        self.refresh_tracked_table()
        self.refresh_passes()

    def refresh_satellite_table(self, text=None):
        text=(text if isinstance(text,str) else self.catalog_search.text()).casefold().strip()
        rows=[]
        for ident,item in self.omm.items():
            orb=orbital_characteristics(item)
            info=operational_characteristics(load_transmitters(self.config.dir,int(ident)))
            mode=', '.join(info['modes']) or '—'
            freq=', '.join(f'{n:.3f}' for n in info['downlinks_mhz'][:3]) or '—'
            fields=[orb['name'],ident,
                    f"{orb['inclination_deg']:.1f}°" if orb['inclination_deg'] is not None else '—',
                    f"{orb['period_min']:.1f} min" if orb['period_min'] is not None else '—',
                    mode,freq,info['status']]
            if text in ' '.join(fields).casefold():
                rows.append((orb['name'].casefold(),ident,fields))
        rows.sort()
        self.catalog_table.setSortingEnabled(False)
        self.catalog_table.setRowCount(len(rows))
        for r,(_,ident,fields) in enumerate(rows):
            for c,value in enumerate(fields):
                cell=QTableWidgetItem(value)
                cell.setData(Qt.UserRole,ident)
                self.catalog_table.setItem(r,c,cell)
        self.catalog_table.setSortingEnabled(True)
        self.catalog_note.setText(f'{len(rows)} satélites (CelesTrak) · modo/frequência apenas quando recuperados do SatNOGS')

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
            if search in f"{name} {ident}".casefold():self.sat_combo.addItem(f"{name}  ·  {ident}",ident)
        if selected:
            idx=self.sat_combo.findData(str(selected))
            if idx>=0:self.sat_combo.setCurrentIndex(idx)
        self.sat_combo.blockSignals(False)
        self.choose_satellite()

    def choose_satellite(self):
        if hasattr(self, "doppler_checkbox") and self.doppler_checkbox.isChecked():
            self.doppler_checkbox.setChecked(False)
        ident=self.sat_combo.currentData()
        if not ident or ident not in self.omm:
            self.sat=None;self.sat_detail.setText("Nenhum satélite selecionado");return
        item=self.omm[ident]
        try:
            self.sat=make_satellite(item,self.ts)
        except Exception as exc:
            self.log(f"Erro OMM {ident}: {exc}")
            self.sat=None;return
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

    def refresh_modes(self,force=False):
        ident=self.sat_combo.currentData()
        if not ident:return
        hours=age_hours(self.config.dir,f"tx_{ident}.json")
        if force or hours is None or hours>24:
            self.background('tx:'+str(ident),lambda:refresh_transmitters(self.config.dir,int(ident)))

    def choose_cached_modes(self,ident):
        self.options=transponder_options(load_transmitters(self.config.dir,ident))
        self.mode_combo.blockSignals(True);self.mode_combo.clear()
        self.mode_combo.addItem("Manual (frequências customizadas)",-1)
        for i, opt in enumerate(self.options):
            info='RX apenas' if opt['receive_only'] else 'RX/TX'
            self.mode_combo.addItem(f"{opt['name'][:43]} · {opt['mode']} · {info}",i)
        self.mode_combo.blockSignals(False)
        self.mode_combo.setCurrentIndex(1 if self.options else 0)
        self.choose_mode()
        self.refresh_satellite_table()

    def choose_mode(self):
        if hasattr(self, "doppler_checkbox") and self.doppler_checkbox.isChecked():
            self.doppler_checkbox.setChecked(False)
        i=self.mode_combo.currentData()
        if not isinstance(i,int) or i<0 or i>=len(self.options):
            self.mode_note.setText("Modo manual: confira cada frequência e modo antes de usar.")
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

    def pair_linear(self):
        i=self.mode_combo.currentData()
        if not isinstance(i,int) or i<0 or i>=len(self.options):return
        opt=self.options[i]
        if opt['uplink'] is None or opt['downlink_high']<=opt['downlink'] or opt['uplink_high']<=opt['uplink']:return
        try:
            dl=round(float(self.down_edit.text().replace(',','.'))*1e6)
            ul=paired_linear_uplink(dl,opt['downlink'],opt['downlink_high'],opt['uplink'],opt['uplink_high'],opt['inverted'])
            self.up_edit.setText(f"{ul/1e6:.6f}")
        except ValueError:pass

    def nominal_hz(self):
        try: dl=round(float(self.down_edit.text().replace(',','.'))*1e6)
        except ValueError:raise ValueError('Informe a frequência nominal de RX')
        try:ul=round(float(self.up_edit.text().replace(',','.'))*1e6) if self.up_edit.text().strip() else None
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

    def doppler_state_changed(self):
        if self.doppler_checkbox.isChecked():
            try:
                self.station();self.corrected()
                if not self.radio.connected or not self.radio.state.sat:
                    raise ValueError("Conecte ao TS-2000 e ative SAT antes de habilitar o Doppler")
                if not self.last_pos['visible']:
                    raise ValueError('O satélite está abaixo da elevação mínima configurada')
                if not self.omm_fresh():
                    raise ValueError('OMM antigo: atualize antes de controlar o rádio automaticamente')
                if QMessageBox.question(self,'Ativar Doppler','Permitir que o aplicativo altere periodicamente FA/FB durante esta passagem?') != QMessageBox.Yes:
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

    def refresh_passes(self):
        try:station=self.station()
        except Exception:
            self.pass_table.setRowCount(0)
            return
        selected=set(self.enabled_satellite_ids())
        entries=[(ident,obj) for ident,obj in self.omm.items() if ident in selected]
        # Capture immutable snapshot; skyfield object construction in background.
        def task():
            out=[]
            for ident,obj in entries:
                try:
                    sat=make_satellite(obj,self.ts)
                    passes=predict_passes(sat,station,hours=36,ts=self.ts)
                    for p in passes:
                        out.append({**p,'id':ident,'name':obj.get('OBJECT_NAME',ident)})
                except Exception:
                    continue
            out.sort(key=lambda p:p['aos'])
            return out[:100]
        self.background('passes',task)

    def select_pass_satellite(self,row,col):
        if 0<=row<len(self.passes):
            ident=self.passes[row]['id']
            self.search.clear()
            index=self.sat_combo.findData(ident)
            if index>=0:self.sat_combo.setCurrentIndex(index)

    def update_map(self):
        if self.sat is None:return
        try:
            station=self.station()
            pos=position(self.sat,station,ts=self.ts)
            self.last_pos=pos
            track=ground_track(self.sat,ts=self.ts)
            circle=footprint(pos['sat_lat'],pos['sat_lon'],pos['footprint_radius_deg'])
            payload={"name":self.sat.name,"satellite":{"lat":pos['sat_lat'],"lon":pos['sat_lon'],"height_km":pos['height_km']},
                     "station":{"lat":station.lat,"lon":station.lon,"callsign":station.callsign},
                     "track":track,"footprint":circle,
                     "label":f"{self.sat.name} · elevação {pos['elevation']:.1f}° · alcance {pos['range_km']:.0f} km"}
            self.map.page().runJavaScript('window.updateOrbit && window.updateOrbit('+json.dumps(payload)+');')
        except Exception as exc:
            self.map_desc.setText(f"Para ver órbitas/passagens, cadastre sua estação. {exc}")

    def tick(self):
        # No network calls in the GUI tick; asynchronous check respects the configured period.
        if int(now_utc().timestamp()) % 60 == 0:
            self.check_for_updates()
        now=now_utc();self.utc.setText(now.strftime('%d/%m/%Y  %H:%M:%S UTC'))
        if self.sat:
            try:
                station=self.station()
                pos=position(self.sat,station,ts=self.ts)
                self.last_pos=pos
                formats={'elevation':f"{pos['elevation']:.1f}°",'azimuth':f"{pos['azimuth']:.1f}°",
                         'range_km':f"{pos['range_km']:.0f} km",'radial_m_s':f"{pos['radial_m_s']:+.1f} m/s",
                         'height_km':f"{pos['height_km']:.0f} km"}
                for k,v in formats.items():self.orbit_metrics[k].setText(v)
                self.visibility.setText('EM PASSAGEM' if pos['visible'] else 'ABAIXO DO HORIZONTE')
                self.visibility.setStyleSheet('font-size:18px;font-weight:800;color:'+('#5ae1a6' if pos['visible'] else '#e1c27c'))
                try:
                    ul,dl=self.corrected()
                    self.corrected_label.setText(f"Doppler RX {dl/1e6:.6f}  |  TX {ul/1e6:.6f} MHz")
                except ValueError:self.corrected_label.setText('Doppler RX/TX: —')
                if (self.last_map_time is None or (now-self.last_map_time).total_seconds()>=12):
                    self.update_map();self.last_map_time=now
                if self.doppler_checkbox.isChecked():
                    if not pos['visible'] or not self.omm_fresh() or not self.radio.connected:
                        self.doppler_checkbox.setChecked(False)
                        self.log('Doppler parado: horizonte, dados antigos ou CAT desconectado')
                    else:
                        interval=int(self.interval.value())
                        if int(now.timestamp())%interval == 0:
                            ul,dl=self.corrected()
                            threshold=int(self.threshold.value())
                            if self.last_freqs[0] is None or max(abs(ul-self.last_freqs[0]),abs(dl-self.last_freqs[1]))>=threshold:
                                self.apply_freqs(silent=True)
            except Exception:
                self.visibility.setText('Cadastre a estação')
        if self.radio.connected and not self.doppler_checkbox.isChecked():
            interval=max(1,int(self.config.values.get("poll_interval_s",1)))
            if now.timestamp()-self.last_radio_poll>=interval:
                self.last_radio_poll=now.timestamp()
                self.background("cat-poll",self.radio.poll)
        if self.radio.connected and self.last_cat_success:
            age=(now-self.last_cat_success).total_seconds()
            if age>10:
                self.map_radio_label.setText(f"CAT sem leitura há {age:.0f}s · valores desatualizados")
                self.map_radio_label.setStyleSheet("color:#e3ad61;font-weight:700")

    def background_result(self,key,data):
        self.pending_jobs.discard(key)
        if key.startswith('photo:'):
            if key.split(':')[1]==str(self.sat_combo.currentData()):
                self.photo.setHtml(photo_html(data),QUrl("https://commons.wikimedia.org/"))
            return
        if key=='cat-poll':
            if self.radio.connected:self.render_radio_state(data)
            return
        if key=='update-check':
            self.manual_update_requested = False
            self.available_update=data
            if data:
                self.version_btn.setText(f'Nova v{data.version} · Atualizar')
                self.version_btn.setStyleSheet('background:#ae6616;color:white;border:1px solid #eda847')
                if self.config.values.get('last_update_notice')!=data.version:
                    self.config.values['last_update_notice']=data.version
                    self.config.save()
                    QMessageBox.information(self,'Atualização disponível',
                        f'Nova versão v{data.version}. Clique no botão laranja da barra superior para atualizar.\n\n{data.body[:3200]}')
            else:
                self.version_btn.setText(f'v{__version__} · última versão')
                self.version_btn.setStyleSheet('background:#145a3d;color:#e6ffee')
            return
        if key=='update-download':
            self.update_ready(data)
            return
        if key=='omm':
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

    def background_error(self,key,message):
        self.pending_jobs.discard(key)
        self.log(f'Falha {key}: {message}')
        if key=="cat-poll":
            self.map_radio_label.setText("CAT erro de leitura · dados desatualizados")
            self.map_radio_label.setStyleSheet("color:#e98b81;font-weight:700")
        if key.startswith('update-'):
            self.version_btn.setText(f'v{__version__} · atualização indisponível')
            if self.update_dialog:
                self.update_dialog.close()
                self.update_dialog=None
            if key=='update-download' or self.manual_update_requested:
                QMessageBox.warning(self,'Falha de atualização',message)
            self.manual_update_requested = False
        if key=='omm':self.summary.setText('Sem atualização: usando cache OMM, se existente')
        if key.startswith('photo:') and key.split(':')[1]==str(self.sat_combo.currentData()):
            self.photo.setHtml(photo_html(None))

    def enabled_satellite_ids(self):
        c=self.config.values
        rows={ident:load_transmitters(self.config.dir,int(ident)) for ident in self.omm}
        return choose_satellites(self.omm,rows,c.get("radio_modes",[]),
                                 c.get("radio_bands",[]),c.get("satellite_selection"))

    def suggested_mode_text(self,ident):
        c=self.config.values
        info=capability(ident,load_transmitters(self.config.dir,int(ident)),
                        c.get("radio_modes",[]),c.get("radio_bands",[]))
        return render_service(info["modes"])

    def refresh_tracked_table(self):
        if not hasattr(self,"tracked_table"):return
        self._loading_satellites=True
        try:
            selected=set(self.enabled_satellite_ids())
            rows=sorted(self.omm.items(),key=lambda p:p[1].get("OBJECT_NAME",""))
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

    def satellite_checked(self,row,col):
        if self._loading_satellites or col!=0:return
        ids=[]
        for row_index in range(self.tracked_table.rowCount()):
            entry=self.tracked_table.item(row_index,0)
            if entry and entry.checkState()==Qt.Checked:ids.append(str(entry.data(Qt.UserRole)))
        self.config.values["satellite_selection"]=ids
        self.config.save()
        self.filter_sats(self.search.text())
        self.refresh_passes()

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
        port=self.config_port.currentText().strip()
        if not port:
            QMessageBox.warning(self,"Porta CAT","Selecione ou digite a porta COM.");return
        if self.radio.connected:
            QMessageBox.information(self,"CAT","Rádio já conectado; desconecte antes de alterar a porta.");return
        self.config.values.update({"radio_brand":"Kenwood","radio_model":"TS-2000","port":port})
        self.config.save()
        if self.ports.findText(port)<0:self.ports.addItem(port)
        self.ports.setCurrentText(port)
        self.toggle_connection()

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
