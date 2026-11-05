"""Painel SDR / Equipamentos / Telemetria (v1.4.0), acoplável à janela principal.

- RTL-SDR embutido: detecção automática, Doppler em tempo real (4 Hz), áudio, waterfall,
  gravação automática das passagens e decodificação conforme o pipeline do transmissor.
- Equipamentos RX/TX separados: FT-817/818/857/897 e Hamlib rigctld (o TS-2000 segue com o
  Auto CAT existente). Rádios só recebem frequências com autorização explícita; nunca PTT.
- Telemetria: AFSK 1200 interno, SoundModem UZ7HO por KISS TCP, satnogs-decoders, CSV e SatNOGS.
"""
from __future__ import annotations

import collections
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .qt_compat import (Qt, QTimer, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QScrollArea,
                        QPushButton, QLineEdit, QComboBox, QGroupBox, QTabWidget, QCheckBox,
                        QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
                        QAbstractItemView, QMessageBox, QProgressBar)
from . import ax25, dsp, rigs, sdr, telemetry

try:  # PySide6
    from PySide6.QtGui import QImage, QPainter, QColor, QPen
    from PySide6.QtWidgets import QDockWidget, QSlider
except ImportError:  # PySide2
    from PySide2.QtGui import QImage, QPainter, QColor, QPen
    from PySide2.QtWidgets import QDockWidget, QSlider


def colormap() -> np.ndarray:
    """Paleta 256 cores (preto → azul → ciano → amarelo → vermelho), ARGB32."""
    stops = [(0, (5, 8, 25)), (70, (15, 40, 140)), (130, (0, 180, 210)),
             (190, (250, 230, 60)), (255, (250, 60, 30))]
    out = np.zeros((256, 3))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        t = np.linspace(0, 1, b - a + 1)[:, None]
        out[a:b + 1] = np.array(ca) * (1 - t) + np.array(cb) * t
    rgb = out.astype(np.uint32)
    return (0xFF000000 | (rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2]).astype(np.uint32)


ZOOMS = [("±12 kHz", 12_000), ("±25 kHz", 25_000), ("±50 kHz", 50_000), ("±100 kHz", 100_000),
         ("±250 kHz", 250_000), ("±480 kHz", 480_000)]


class WaterfallWidget(QWidget):
    """Waterfall com marcas do canal/filtro e do transponder; clique sintoniza (sinal tuned)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.lut = colormap()
        self.rows = 180
        self.width_px = 600
        self.image = np.zeros((self.rows, self.width_px), dtype=np.uint32) | 0xFF050819
        self.span_hz = 50_000
        self.floor_db = -110.0
        self.range_db = 50.0
        self.auto_floor = True
        self.channel_hz = 0      # frequência do canal (absoluta)
        self.filter_hz = 12_000
        self.band = None         # (baixa, alta) do transponder já com Doppler
        self.last_spectrum = None
        self.on_click = lambda delta_hz: None
        self.setCursor(Qt.CrossCursor)
        self.setToolTip("Clique para sintonizar o sinal; o Doppler continua corrigindo")

    def push(self, spectrum_db: np.ndarray, center_hz: int):
        if not self.channel_hz:
            return
        n = len(spectrum_db)
        bin_hz = dsp.SDR_RATE / n
        mid = n // 2 + (self.channel_hz - center_hz) / bin_hz
        half = self.span_hz / bin_hz
        lo, hi = int(max(0, mid - half)), int(min(n, mid + half))
        if hi - lo < 4:
            return
        seg = spectrum_db[lo:hi]
        self.last_spectrum = seg
        if self.auto_floor:
            self.floor_db = float(np.percentile(seg, 20)) - 3
        row = np.interp(np.linspace(0, len(seg) - 1, self.width_px), np.arange(len(seg)), seg)
        idx = np.clip((row - self.floor_db) / max(self.range_db, 1) * 255, 0, 255).astype(np.uint8)
        self.image = np.roll(self.image, 1, axis=0)
        self.image[0] = self.lut[idx]
        self.update()

    def resizeEvent(self, event):
        w = max(200, self.width())
        if w != self.width_px:
            self.width_px = w
            self.image = np.zeros((self.rows, w), dtype=np.uint32) | 0xFF050819
        super().resizeEvent(event)

    def _x(self, hz: float) -> float:
        return (hz - (self.channel_hz - self.span_hz)) / (2 * self.span_hz) * self.width()

    def paintEvent(self, event):
        p = QPainter(self)
        img = QImage(self.image.data, self.width_px, self.rows, self.width_px * 4, QImage.Format_ARGB32)
        p.drawImage(self.rect(), img)
        if self.channel_hz:
            if self.band:
                p.fillRect(int(self._x(self.band[0])), 0, max(1, int(self._x(self.band[1]) - self._x(self.band[0]))),
                           6, QColor(120, 220, 160, 200))
            x0, x1 = self._x(self.channel_hz - self.filter_hz / 2), self._x(self.channel_hz + self.filter_hz / 2)
            p.fillRect(int(x0), 0, max(1, int(x1 - x0)), self.height(), QColor(255, 255, 255, 28))
            p.setPen(QPen(QColor(255, 80, 80), 1))
            xc = int(self._x(self.channel_hz))
            p.drawLine(xc, 0, xc, self.height())
            p.setPen(QColor(220, 235, 245))
            p.drawText(6, self.height() - 6, f"{self.channel_hz / 1e6:.4f} MHz · ±{self.span_hz / 1e3:.0f} kHz")
        p.end()

    def mousePressEvent(self, event):
        if not self.channel_hz:
            return
        pos = event.position().x() if hasattr(event, "position") else event.x()
        delta = (pos / max(1, self.width()) - 0.5) * 2 * self.span_hz
        self.on_click(int(round(delta / 10) * 10))


class SdrPanel(QWidget):
    """Conteúdo do dock "SDR · Equipamentos · Telemetria"."""

    def __init__(self, window):
        super().__init__(window)
        self.w = window
        self.cfg = window.config.values
        self.receiver: sdr.SdrReceiver | None = None
        self.devices: list[sdr.SdrDevice] = []
        self._asked_devices: set[str] = set()
        self._audio_q: collections.deque = collections.deque(maxlen=50)
        self._spec_q: queue.Queue = queue.Queue(maxsize=4)
        self._frame_q: queue.Queue = queue.Queue()
        self._decoded_q: queue.Queue = queue.Queue()
        self.sink = None
        self.sink_io = None
        self.rx_rig = None
        self.tx_rig = None
        self.dispatch = rigs.DopplerDispatcher(threshold_hz=int(self.cfg.get("tune_threshold_hz", 10) or 10))
        self.kiss: telemetry.KissTcpClient | None = None
        self.decoder = telemetry.TelemetryDecoder(window.config.dir)
        self.tlm_log = telemetry.TelemetryLog(window.config.dir / "telemetria")
        self.last_snapshot: dict | None = None
        self._was_visible = False
        self._build()
        self.fast = QTimer(self)
        self.fast.timeout.connect(self.fast_tick)
        self.fast.start(250)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.drain)
        self.ui_timer.start(40)
        self.detect_timer = QTimer(self)
        self.detect_timer.timeout.connect(self.detect)
        self.detect_timer.start(5000)
        QTimer.singleShot(2500, self.detect)
        if self.cfg.get("kiss_enabled"):
            QTimer.singleShot(1500, self.start_kiss)

    # ----------------------------------------------------------------- UI
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        tabs = QTabWidget()
        root.addWidget(tabs)

        # --- Receptor
        rx_page = QWidget(); rl = QVBoxLayout(rx_page); rl.setContentsMargins(2, 2, 2, 2)
        bar = QHBoxLayout()
        self.sdr_led = QPushButton("SDR")
        self.sdr_led.setFixedWidth(52)
        self.sdr_led.setToolTip("Clique para iniciar/parar o RTL-SDR")
        self.sdr_led.clicked.connect(self.toggle_sdr)
        bar.addWidget(self.sdr_led)
        self.device_combo = QComboBox(); self.device_combo.setMinimumWidth(170)
        bar.addWidget(self.device_combo)
        self.rx_info = QLabel("RX —"); self.rx_info.setStyleSheet("color:#7ee5d4;font-weight:700")
        bar.addWidget(self.rx_info, 1)
        self.level = QProgressBar(); self.level.setRange(0, 60); self.level.setTextVisible(False)
        self.level.setFixedWidth(90); self.level.setMaximumHeight(10)
        bar.addWidget(QLabel("Nível")); bar.addWidget(self.level)
        bar.addWidget(QLabel("Zoom"))
        self.zoom = QComboBox()
        for label, hz in ZOOMS:
            self.zoom.addItem(label, hz)
        self.zoom.setCurrentIndex(2)
        self.zoom.currentIndexChanged.connect(lambda *_: setattr(self.waterfall, "span_hz", int(self.zoom.currentData())))
        bar.addWidget(self.zoom)
        bar.addWidget(QLabel("Vol"))
        self.volume = QSlider(Qt.Horizontal); self.volume.setRange(0, 100); self.volume.setFixedWidth(80)
        self.volume.setValue(int(float(self.cfg.get("sdr_volume", 0.8)) * 100))
        self.volume.valueChanged.connect(self.change_volume)
        bar.addWidget(self.volume)
        bar.addWidget(QLabel("Squelch"))
        self.squelch = QSlider(Qt.Horizontal); self.squelch.setRange(-120, 0); self.squelch.setFixedWidth(80)
        self.squelch.setValue(int(self.cfg.get("sdr_squelch_db", -120)))
        self.squelch.valueChanged.connect(self.change_squelch)
        bar.addWidget(self.squelch)
        bar.addWidget(QLabel("Faixa dB"))
        self.contrast = QSlider(Qt.Horizontal); self.contrast.setRange(15, 90); self.contrast.setValue(50)
        self.contrast.setFixedWidth(70)
        self.contrast.valueChanged.connect(lambda v: setattr(self.waterfall, "range_db", float(v)))
        bar.addWidget(self.contrast)
        rl.addLayout(bar)
        self.waterfall = WaterfallWidget()
        self.waterfall.span_hz = int(self.zoom.currentData())
        self.waterfall.on_click = self.click_tune
        rl.addWidget(self.waterfall, 1)
        self.sdr_status = QLabel("RTL-SDR: aguardando detecção")
        self.sdr_status.setWordWrap(True)
        self.sdr_status.setStyleSheet("color:#a8cee0;font-size:11px")
        rl.addWidget(self.sdr_status)
        tabs.addTab(rx_page, "Receptor SDR")

        # --- Equipamentos RX/TX
        eq = QWidget(); g = QGridLayout(eq)
        self.rx_dev = QComboBox(); self.tx_dev = QComboBox()
        for key, label in rigs.RIG_MODELS.items():
            self.rx_dev.addItem(label, key)
            if key != "SDR":
                self.tx_dev.addItem(label, key)
        self._select(self.rx_dev, self.cfg.get("rx_device", "TS-2000"))
        self._select(self.tx_dev, self.cfg.get("tx_device", "TS-2000"))
        g.addWidget(QLabel("RX (downlink)"), 0, 0); g.addWidget(self.rx_dev, 0, 1, 1, 3)
        g.addWidget(QLabel("TX (uplink)"), 1, 0); g.addWidget(self.tx_dev, 1, 1, 1, 3)
        self.ft_port = QComboBox(); self.ft_port.setEditable(True)
        self.ft_baud = QComboBox(); [self.ft_baud.addItem(b) for b in ("4800", "9600", "38400")]
        self.ft_baud.setCurrentText(str(self.cfg.get("ft817_baud", "9600")))
        g.addWidget(QLabel("FT-817 porta / baud"), 2, 0); g.addWidget(self.ft_port, 2, 1); g.addWidget(self.ft_baud, 2, 2)
        self.rig_host = QLineEdit(str(self.cfg.get("rigctld_host", "127.0.0.1:4532")))
        g.addWidget(QLabel("rigctld host:porta"), 3, 0); g.addWidget(self.rig_host, 3, 1, 1, 2)
        self.rig_connect = QPushButton("Conectar equipamentos")
        self.rig_connect.clicked.connect(self.connect_rigs)
        g.addWidget(self.rig_connect, 4, 0)
        self.rig_doppler = QCheckBox("Doppler automático nos equipamentos (FT-817/rigctld) — sem PTT")
        self.rig_doppler.toggled.connect(self.arm_rig_doppler)
        g.addWidget(self.rig_doppler, 4, 1, 1, 3)
        self.rig_status = QLabel("TS-2000 continua com o Auto CAT da aba Operação. FT-817 sem modo SAT: "
                                 "com RX e TX no mesmo FT-817 usa split (RX no VFO A, TX no VFO B).")
        self.rig_status.setWordWrap(True); self.rig_status.setStyleSheet("color:#a8cee0;font-size:11px")
        g.addWidget(self.rig_status, 5, 0, 1, 4)
        self.rtl_tcp = QLineEdit(str(self.cfg.get("rtl_tcp", "")))
        self.rtl_tcp.setPlaceholderText("opcional: rtl_tcp host:porta (dongle remoto)")
        g.addWidget(QLabel("RTL-SDR remoto"), 6, 0); g.addWidget(self.rtl_tcp, 6, 1, 1, 3)
        self.gain = QComboBox(); self.gain.addItem("Automático", None)
        for db in (0, 9.7, 19.7, 28.0, 33.8, 38.6, 42.1, 44.5, 49.6):
            self.gain.addItem(f"{db} dB", db)
        g.addWidget(QLabel("Ganho"), 7, 0); g.addWidget(self.gain, 7, 1)
        self.ppm = QDoubleSpinBox(); self.ppm.setRange(-200, 200); self.ppm.setDecimals(0)
        self.ppm.setValue(float(self.cfg.get("sdr_ppm", 0))); self.ppm.setSuffix(" ppm")
        g.addWidget(QLabel("Correção"), 7, 2); g.addWidget(self.ppm, 7, 3)
        self.bias = QCheckBox("Bias-tee (alimenta LNA)"); self.bias.setChecked(bool(self.cfg.get("sdr_bias_tee", False)))
        g.addWidget(self.bias, 8, 0, 1, 2)
        self.audio_dev = QComboBox()
        g.addWidget(QLabel("Saída de áudio"), 9, 0); g.addWidget(self.audio_dev, 9, 1, 1, 3)
        self.record = QCheckBox("Gravar passagens automaticamente (AOS→LOS, WAV)")
        self.record.setChecked(bool(self.cfg.get("sdr_record", False)))
        self.record_iq = QCheckBox("incluir IQ do canal (48 kHz)")
        self.record_iq.setChecked(bool(self.cfg.get("sdr_record_iq", False)))
        g.addWidget(self.record, 10, 0, 1, 2); g.addWidget(self.record_iq, 10, 2, 1, 2)
        save = QPushButton("Salvar configurações")
        save.clicked.connect(self.save_settings)
        g.addWidget(save, 11, 0)
        tabs.addTab(self._scroll(eq), "Equipamentos RX/TX")
        self._fill_audio_devices()
        self._fill_ports()

        # --- Telemetria
        tl = QWidget(); tv = QVBoxLayout(tl)
        top = QHBoxLayout()
        self.pipeline_label = QLabel("Pipeline: —"); self.pipeline_label.setStyleSheet("color:#7ee5d4")
        top.addWidget(self.pipeline_label, 1)
        self.kiss_enabled = QCheckBox("SoundModem/KISS")
        self.kiss_enabled.setChecked(bool(self.cfg.get("kiss_enabled", False)))
        self.kiss_enabled.toggled.connect(self.toggle_kiss)
        top.addWidget(self.kiss_enabled)
        self.kiss_host = QLineEdit(str(self.cfg.get("kiss_host", "127.0.0.1:8100"))); self.kiss_host.setFixedWidth(130)
        top.addWidget(self.kiss_host)
        self.satnogs_upload = QCheckBox("Enviar ao SatNOGS")
        self.satnogs_upload.setChecked(bool(self.cfg.get("satnogs_upload", False)))
        self.satnogs_upload.setToolTip("Envia cada quadro ao SatNOGS DB com seu indicativo e coordenadas da estação")
        top.addWidget(self.satnogs_upload)
        tv.addLayout(top)
        self.frames = QTableWidget(0, 5)
        self.frames.setHorizontalHeaderLabels(["UTC", "Origem", "Quadro (AX.25 / hex)", "Decodificador", "Campos"])
        self.frames.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.frames.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.frames.verticalHeader().hide()
        self.frames.setMinimumHeight(60)
        self.frames.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tv.addWidget(self.frames)
        self.tlm_status = QLabel(f"Log CSV: {self.tlm_log.folder}")
        self.tlm_status.setStyleSheet("color:#a8cee0;font-size:11px")
        tv.addWidget(self.tlm_status)
        tabs.addTab(self._scroll(tl), "Telemetria")
        self._led(False)

    @staticmethod
    def _scroll(page):
        """Formulários longos não impõem altura mínima ao painel acoplado."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(page)
        area.setMinimumHeight(60)
        return area

    @staticmethod
    def _select(combo, key):
        i = combo.findData(key)
        combo.setCurrentIndex(max(0, i))

    def _fill_ports(self):
        try:
            from .cat import available_ports
            ports = available_ports()
        except Exception:
            ports = []
        self.ft_port.clear()
        self.ft_port.addItems(ports)
        if self.cfg.get("ft817_port"):
            self.ft_port.setCurrentText(str(self.cfg["ft817_port"]))

    def _fill_audio_devices(self):
        self.audio_dev.clear()
        try:
            try:
                from PySide6.QtMultimedia import QMediaDevices
            except ImportError:
                QMediaDevices = None
            if QMediaDevices is not None:
                for dev in QMediaDevices.audioOutputs():
                    self.audio_dev.addItem(dev.description(), dev.description())
        except Exception:
            pass
        if not self.audio_dev.count():
            self.audio_dev.addItem("Padrão do sistema", "")
        want = self.cfg.get("sdr_audio_device", "")
        if want:
            self._select(self.audio_dev, want)

    def _led(self, ok, warn=False):
        color = ("#125743", "#a4f7c9", "#3fd18e") if ok else (("#755225", "#ffead3", "#e0aa55") if warn
                                                               else ("#5a2a2a", "#ffd0c4", "#c96a5a"))
        self.sdr_led.setStyleSheet(f"font-weight:800;background:{color[0]};color:{color[1]};border:1px solid {color[2]}")

    def save_settings(self):
        c = self.cfg
        c.update({"rx_device": self.rx_dev.currentData(), "tx_device": self.tx_dev.currentData(),
                  "ft817_port": self.ft_port.currentText().strip(), "ft817_baud": int(self.ft_baud.currentText()),
                  "rigctld_host": self.rig_host.text().strip(), "rtl_tcp": self.rtl_tcp.text().strip(),
                  "sdr_ppm": int(self.ppm.value()), "sdr_bias_tee": self.bias.isChecked(),
                  "sdr_gain_db": self.gain.currentData(), "sdr_audio_device": self.audio_dev.currentData() or "",
                  "sdr_record": self.record.isChecked(), "sdr_record_iq": self.record_iq.isChecked(),
                  "kiss_enabled": self.kiss_enabled.isChecked(), "kiss_host": self.kiss_host.text().strip(),
                  "satnogs_upload": self.satnogs_upload.isChecked(),
                  "sdr_volume": self.volume.value() / 100, "sdr_squelch_db": self.squelch.value()})
        self.w.config.save()
        self.w.log("Configurações de SDR/equipamentos salvas")

    # ------------------------------------------------------------ detecção
    def detect(self):
        if self.receiver and self.receiver.status.running:
            return
        devices, message = sdr.detect_devices()
        remote = self.rtl_tcp.text().strip()
        if remote:
            devices.append(sdr.SdrDevice(-1, "rtl_tcp", remote=remote))
        labels = [d.label for d in devices]
        if labels != [self.device_combo.itemText(i) for i in range(self.device_combo.count())]:
            self.device_combo.clear()
            self.device_combo.addItems(labels)
        self.devices = devices
        if not devices:
            self.sdr_status.setText("RTL-SDR: " + message)
            self._led(False)
            return
        self.sdr_status.setText(f"RTL-SDR detectado: {', '.join(labels)}")
        dock = self.parentWidget()
        if dock is not None and not self._asked_devices and not dock.isVisible():
            dock.setVisible(True)  # primeira detecção: mostra o painel
        self._led(False, warn=True)
        key = devices[0].serial or devices[0].label
        if self.cfg.get("rx_device") == "SDR":
            if self.cfg.get("sdr_autostart", True):
                self.start_sdr()
        elif key not in self._asked_devices and not any(d.remote for d in devices[:1]):
            self._asked_devices.add(key)
            answer = QMessageBox.question(
                self.w, "RTL-SDR detectado",
                f"{devices[0].label} conectado.\n\nUsar o RTL-SDR para a recepção (RX) dos satélites, "
                "com Doppler, áudio, waterfall e decodificação? O rádio continua disponível para TX.")
            if answer == QMessageBox.Yes:
                self._select(self.rx_dev, "SDR")
                self.save_settings()
                self.start_sdr()

    # ------------------------------------------------------------ receptor
    def toggle_sdr(self):
        if self.receiver and self.receiver.status.running:
            self.stop_sdr()
        else:
            self.start_sdr()

    def start_sdr(self):
        if self.receiver and self.receiver.status.running:
            return
        if not self.devices:
            self.detect()
            if not self.devices:
                QMessageBox.information(self.w, "RTL-SDR", "Nenhum RTL-SDR detectado. " + sdr.ZADIG_HELP
                                        if sdr.sys.platform == "win32" else "Nenhum RTL-SDR detectado.")
                return
        dev = self.devices[max(0, self.device_combo.currentIndex())]
        settings = sdr.SdrSettings(gain_db=self.gain.currentData(), ppm=int(self.ppm.value()),
                                   bias_tee=self.bias.isChecked())
        self.receiver = sdr.SdrReceiver(lambda: sdr.RtlSource(dev, settings),
                                        on_audio=self._audio_q.append,
                                        on_spectrum=self._on_spectrum,
                                        on_frame=lambda f, s: self._frame_q.put((f, s)))
        self.receiver.set_volume(self.volume.value() / 100)
        self.receiver.set_squelch(self.squelch.value())
        self._open_audio()
        self.dispatch.reset()
        self.fast_tick()
        self.receiver.start()
        if self.parentWidget() is not None:
            self.parentWidget().setVisible(True)
        self.w.log(f"SDR iniciado: {dev.label}")

    def stop_sdr(self):
        if self.receiver:
            self.receiver.stop()
            self.w.log("SDR parado")
        self._close_audio()
        self._led(False, warn=bool(self.devices))

    def _on_spectrum(self, spec, center):
        try:
            self._spec_q.put_nowait((spec, center))
        except queue.Full:
            pass

    def _open_audio(self):
        self._close_audio()
        try:
            from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
        except ImportError:
            self.sdr_status.setText("Áudio indisponível nesta versão do Qt")
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(dsp.AUDIO_RATE)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)
        device = QMediaDevices.defaultAudioOutput()
        want = self.audio_dev.currentData()
        for d in QMediaDevices.audioOutputs():
            if want and d.description() == want:
                device = d
        self.sink = QAudioSink(device, fmt, self)
        self.sink.setBufferSize(dsp.AUDIO_RATE * 2 // 2)  # ~0,5 s
        self.sink_io = self.sink.start()

    def _close_audio(self):
        if self.sink is not None:
            try:
                self.sink.stop()
            except Exception:
                pass
        self.sink = self.sink_io = None
        self._audio_q.clear()

    def change_volume(self, v):
        if self.receiver:
            self.receiver.set_volume(v / 100)

    def change_squelch(self, v):
        if self.receiver:
            self.receiver.set_squelch(float(v))

    def click_tune(self, delta_hz):
        self.w.retune_nominal_downlink(delta_hz)

    # --------------------------------------------------------- tempo real
    def fast_tick(self):
        """4 Hz: Doppler no SDR e nos equipamentos, gravação AOS→LOS, pipeline."""
        try:
            snap = self.w.doppler_snapshot()
        except Exception:
            snap = None
        self.last_snapshot = snap
        if not snap:
            return
        rx_hz, mode = snap["rx_hz"], snap["rx_mode"]
        self.rx_info.setText(f"RX {rx_hz / 1e6:.5f} MHz · {mode} · Doppler {snap['rx_offset_hz']:+d} Hz")
        self.pipeline_label.setText(f"{snap['name']} · Pipeline: {telemetry.PIPELINE_LABELS.get(snap['pipeline'], '—')}")
        self.waterfall.channel_hz = rx_hz
        self.waterfall.filter_hz = dsp.CHANNEL_WIDTH.get(rigs.normalize_mode(mode) if mode != "PKT" else "FM", 12_000)
        self.waterfall.band = snap.get("band")
        rec = self.receiver
        if rec and rec.status.running:
            rec.tune(rx_hz)
            rec.set_mode("FM" if rigs.normalize_mode(mode) in ("FM", "PKT") else rigs.normalize_mode(mode))
            rec.set_decoder(snap["pipeline"])
            self._recording(snap)
        self._dispatch_rigs(snap)

    def _recording(self, snap):
        rec = self.receiver
        visible = bool(snap.get("visible"))
        if self.record.isChecked() and visible and not self._was_visible:
            name = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{snap['norad']}_{''.join(c for c in snap['name'] if c.isalnum())[:20]}"
            rec.start_recording(self.w.config.dir / "gravacoes", name, self.record_iq.isChecked())
            self.w.log(f"Gravação da passagem iniciada: {name}")
        if self._was_visible and not visible and rec.status.recording:
            path = rec.status.recording
            rec.stop_recording()
            self.w.log(f"Gravação da passagem concluída: {path}")
        self._was_visible = visible

    # ------------------------------------------------------- equipamentos
    def connect_rigs(self):
        self.save_settings()
        self.disconnect_rigs()
        msgs = []
        for role in ("rx", "tx"):
            kind = self.cfg.get(f"{role}_device")
            other = self.rx_rig if role == "tx" and self.cfg.get("rx_device") == kind else None
            if other is not None:
                self.tx_rig = other
                continue
            try:
                if kind == "FT-817":
                    rig = rigs.FT817(self.w.log)
                    rig.connect(self.cfg["ft817_port"], self.cfg["ft817_baud"])
                elif kind == "RIGCTLD":
                    host, _, port = self.cfg["rigctld_host"].partition(":")
                    rig = rigs.Rigctld(self.w.log)
                    rig.connect(host or "127.0.0.1", int(port or 4532))
                else:
                    continue
                setattr(self, f"{role}_rig", rig)
                msgs.append(f"{role.upper()}: {rig.name} conectado")
            except Exception as exc:
                msgs.append(f"{role.upper()}: falha {kind}: {exc}")
        self.rig_status.setText(" · ".join(msgs) or "Nenhum equipamento externo a conectar (TS-2000/SDR já tratados).")
        self.dispatch.reset()

    def disconnect_rigs(self):
        for rig in {id(r): r for r in (self.rx_rig, self.tx_rig) if r}.values():
            try:
                rig.disconnect()
            except Exception:
                pass
        self.rx_rig = self.tx_rig = None
        self.rig_doppler.setChecked(False)

    def arm_rig_doppler(self, enabled):
        if enabled:
            if not (self.rx_rig or self.tx_rig):
                self.rig_doppler.setChecked(False)
                QMessageBox.information(self.w, "Equipamentos", "Conecte FT-817 ou rigctld antes.")
                return
            if QMessageBox.question(self.w, "Doppler nos equipamentos",
                                    "Permitir alterar periodicamente as frequências RX/TX dos equipamentos "
                                    "conectados? Nenhum comando de PTT é enviado; o TX não muda durante a "
                                    "transmissão.") != QMessageBox.Yes:
                self.rig_doppler.setChecked(False)
                return
            self.dispatch.reset()
            self.w.log("Doppler automático nos equipamentos habilitado pelo operador")
        else:
            self.w.log("Doppler automático nos equipamentos desabilitado")

    def _dispatch_rigs(self, snap):
        if not self.rig_doppler.isChecked() or "rig" in self.w.pending_jobs:
            return
        jobs = []
        same = self.rx_rig is not None and self.rx_rig is self.tx_rig
        rx_mode = rigs.normalize_mode(snap["rx_mode"])
        if self.rx_rig and self.dispatch.due("rx", snap["rx_hz"], rx_mode):
            jobs.append(("rx", self.rx_rig, snap["rx_hz"], rx_mode))
        tx_hz = snap.get("tx_hz")
        tx_mode = rigs.normalize_mode(snap["tx_mode"])
        if self.tx_rig and tx_hz and self.dispatch.due("tx", tx_hz, tx_mode):
            jobs.append(("tx", self.tx_rig, tx_hz, tx_mode))
        if not jobs:
            return

        def work():
            done = []
            for role, rig, hz, mode in jobs:
                ok = rig.set_rx(hz, mode) if role == "rx" else rig.set_tx(hz, mode, same_rig_rx=same)
                done.append((role, hz, mode, ok))
            return done
        self.w.background("rig", work)

    def rig_result(self, done):
        for role, hz, mode, ok in done:
            if ok:
                self.dispatch.mark(role, hz, mode)
        self.rig_status.setText(" · ".join(f"{r.upper()} {hz / 1e6:.5f} {m}{'' if ok else ' (aguardando fim do TX)'}"
                                           for r, hz, m, ok in done))

    # ----------------------------------------------------------- telemetria
    def toggle_kiss(self, enabled):
        self.cfg["kiss_enabled"] = bool(enabled)
        self.cfg["kiss_host"] = self.kiss_host.text().strip()
        self.w.config.save()
        if enabled:
            self.start_kiss()
        elif self.kiss:
            self.kiss.stop()
            self.kiss = None

    def start_kiss(self):
        host, _, port = (self.cfg.get("kiss_host") or "127.0.0.1:8100").partition(":")
        self.kiss = telemetry.KissTcpClient(host or "127.0.0.1", int(port or 8100),
                                            lambda f, s: self._frame_q.put((f, s)),
                                            on_status=lambda s: self._decoded_q.put(("status", s)))
        self.kiss.start()

    def _handle_frame(self, frame: bytes, source: str):
        snap = self.last_snapshot or {}
        norad, name = str(snap.get("norad", "")), snap.get("name", "")
        upload = self.satnogs_upload.isChecked()
        try:
            station = self.w.saved_station()
            call, lat, lon = station.callsign, station.lat, station.lon
        except Exception:
            call, lat, lon, upload = "", 0.0, 0.0, False

        def work():
            dec_name, fields = self.decoder.decode(frame, norad) if norad else ("", {})
            record = telemetry.make_record(frame, norad, name, source, dec_name, fields)
            path = self.tlm_log.append(record)
            status = ""
            if upload and norad and call:
                try:
                    status = f"SatNOGS HTTP {telemetry.upload_to_satnogs(frame, norad, call, lat, lon)}"
                except Exception as exc:
                    status = f"SatNOGS: {exc}"
            self._decoded_q.put(("frame", record, str(path), status))
        threading.Thread(target=work, daemon=True).start()

    def _add_frame_row(self, record, path, status):
        t = self.frames
        t.insertRow(0)
        fields = record["fields"] if record["fields"] != "{}" else ""
        for col, value in enumerate((record["utc"][11:19], record["source"], record["ax25"] or record["hex"],
                                     record["decoder"] or "—", fields)):
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            t.setItem(0, col, item)
        while t.rowCount() > 500:
            t.removeRow(t.rowCount() - 1)
        self.tlm_status.setText(f"{t.rowCount()} quadros · log {path}" + (f" · {status}" if status else ""))

    # -------------------------------------------------------- drenagem GUI
    def drain(self):
        rec = self.receiver
        if rec is not None:
            st = rec.status
            if st.running:
                self._led(True)
                self.level.setValue(int(np.clip(st.level_db + 90, 0, 60)))
                self.sdr_led.setToolTip(f"RTL-SDR ativo · centro {st.center_hz / 1e6:.4f} MHz · {st.mode}"
                                        + (f" · gravando {Path(st.recording).name}" if st.recording else ""))
            elif st.error:
                self._led(False)
                self.sdr_status.setText(st.error)
        if self.sink_io is not None:
            while self._audio_q:
                if self.sink.bytesFree() < 9600:
                    break
                self.sink_io.write(dsp.float_to_pcm16(self._audio_q.popleft()))
        try:
            while True:
                spec, center = self._spec_q.get_nowait()
                self.waterfall.push(spec, center)
        except queue.Empty:
            pass
        try:
            while True:
                frame, source = self._frame_q.get_nowait()
                self._handle_frame(frame, source)
        except queue.Empty:
            pass
        try:
            while True:
                item = self._decoded_q.get_nowait()
                if item[0] == "frame":
                    self._add_frame_row(*item[1:])
                else:
                    self.tlm_status.setText(item[1])
        except queue.Empty:
            pass

    def shutdown(self):
        for timer in (self.fast, self.ui_timer, self.detect_timer):
            timer.stop()
        if self.receiver:
            self.receiver.stop()
        if self.kiss:
            self.kiss.stop()
        self.disconnect_rigs()
        self._close_audio()


def make_dock(window) -> tuple[QDockWidget, SdrPanel]:
    dock = QDockWidget("SDR · Equipamentos RX/TX · Telemetria", window)
    dock.setObjectName("sdr_dock")
    panel = SdrPanel(window)
    dock.setWidget(panel)
    dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable |
                     QDockWidget.DockWidgetClosable)
    return dock, panel
