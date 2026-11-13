"""v1.9.0: aba SSTV do painel SDR — recepção (RTL-SDR ou placa de som do rádio), imagem salva e transmissão.

Doppler: quem segue o satélite é o receptor (RTL-SDR do programa ou rádio com Auto CAT/Doppler nos
equipamentos); o desvio de tom que sobrar é medido no cabeçalho VIS e descontado pelo decodificador.
Transmissão: o programa gera o áudio e toca na saída escolhida; o PTT fica com o VOX do rádio ou da
interface (o programa nunca aciona PTT).
"""
from __future__ import annotations

import queue
import threading
from datetime import datetime, timezone

import numpy as np

from . import sstv
from .qt_compat import (Qt, QTimer, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                        QComboBox, QCheckBox, QLineEdit, QFileDialog, QMessageBox, QGroupBox)

try:
    from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QDesktopServices
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
except ImportError:   # pragma: no cover - edição Windows 7 (PySide2)
    from PySide2.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QDesktopServices
    from PySide2.QtCore import QBuffer, QByteArray, QIODevice, QUrl

SDR_SOURCE = "sdr"
RATE = 48000


def qimage_from_rgb(rgb: np.ndarray) -> QImage:
    rgb = np.ascontiguousarray(rgb[..., :3], dtype=np.uint8)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def rgb_from_qimage(image: QImage) -> np.ndarray:
    image = image.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = image.width(), image.height(), image.bytesPerLine()
    data = image.constBits()
    try:
        raw = bytes(data)
    except TypeError:   # PySide2: sip.voidptr
        data.setsize(image.sizeInBytes() if hasattr(image, "sizeInBytes") else image.byteCount())
        raw = bytes(data)
    arr = np.frombuffer(raw, np.uint8)[:bpl * h].reshape(h, bpl)
    return arr[:, :w * 3].reshape(h, w, 3).copy()


def stamp(image: QImage, text: str) -> QImage:
    """Texto (indicativo) no canto superior esquerdo, como de costume no SSTV."""
    if not text:
        return image
    out = image.convertToFormat(QImage.Format_RGB888)
    painter = QPainter(out)
    font = QFont(); font.setBold(True); font.setPixelSize(max(14, out.height() // 12))
    painter.setFont(font)
    painter.setPen(QColor(0, 0, 0))
    painter.drawText(7, 7 + font.pixelSize(), text)
    painter.setPen(QColor(255, 255, 0))
    painter.drawText(5, 5 + font.pixelSize(), text)
    painter.end()
    return out


class SstvWorker:
    """Fila de áudio → decodificador numa thread; os eventos voltam por outra fila para a interface."""

    def __init__(self, rate=RATE):
        self.audio_q: queue.Queue = queue.Queue(maxsize=400)
        self.events_q: queue.Queue = queue.Queue()
        self.decoder = sstv.Decoder(rate)
        self.running = False
        self._thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.decoder.reset()
        self._thread = threading.Thread(target=self._run, name="sat-sstv", daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        try:
            self.audio_q.put_nowait(None)
        except queue.Full:
            pass

    def push(self, audio):
        if self.running:
            try:
                self.audio_q.put_nowait(np.asarray(audio, dtype=np.float32))
            except queue.Full:
                pass

    def _run(self):
        while self.running:
            block = self.audio_q.get()
            if block is None:
                break
            try:
                for event in self.decoder.feed(block):
                    kind, image = event[0], event[1]
                    self.events_q.put((kind, image.mode.name, image.pixels.copy() if kind == "done" else None,
                                       image.rows_done, image.offset_hz, image.slant_ppm, image))
            except Exception as exc:   # pragma: no cover - mantém a aba viva
                self.events_q.put(("error", str(exc), None, 0, 0.0, 0.0, None))
                self.decoder.reset()


class SstvPanel(QWidget):
    def __init__(self, sdr_panel):
        super().__init__(sdr_panel)
        self.sdr = sdr_panel
        self.w = sdr_panel.w
        self.cfg = self.w.config.values
        self.folder = self.w.config.dir / "sstv"
        self.worker = SstvWorker()
        self.source = None          # QAudioSource da placa de som
        self.source_io = None
        self.current = None         # Image em recepção
        self.last_rgb = None
        self.last_meta = {}
        self.tx_rgb = None
        self.tx_audio = None
        self.sink = None
        self.tx_buffer = None
        self._build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.drain)
        self.timer.start(120)

    # ------------------------------------------------------------------ UI
    def _build(self):
        root = QVBoxLayout(self)
        rx = QGroupBox("Receber SSTV")
        rg = QGridLayout(rx)
        self.rx_source = QComboBox()
        self.rx_source.addItem("RTL-SDR do programa", SDR_SOURCE)
        for name in self._inputs():
            self.rx_source.addItem(f"Placa de som: {name}", name)
        index = self.rx_source.findData(self.cfg.get("sstv_rx_source", SDR_SOURCE))
        self.rx_source.setCurrentIndex(max(0, index))
        rg.addWidget(QLabel("Áudio de"), 0, 0); rg.addWidget(self.rx_source, 0, 1, 1, 2)
        self.rx_button = QPushButton("Receber")
        self.rx_button.setCheckable(True)
        self.rx_button.toggled.connect(self.toggle_rx)
        rg.addWidget(self.rx_button, 0, 3)
        self.rx_mode = QComboBox()
        self.rx_mode.addItem("Automático (VIS)", "")
        for name in sstv.MODES:
            self.rx_mode.addItem(name, name)
        self.rx_mode.setToolTip("Automático reconhece o modo pelo cabeçalho VIS; escolha um modo para começar sem VIS")
        rg.addWidget(QLabel("Modo"), 1, 0); rg.addWidget(self.rx_mode, 1, 1)
        self.start_now = QPushButton("Começar agora")
        self.start_now.setToolTip("Inicia a imagem no modo escolhido sem esperar o VIS (sinal já em andamento)")
        self.start_now.clicked.connect(self.force_start)
        rg.addWidget(self.start_now, 1, 2)
        self.autosave = QCheckBox("Salvar cada imagem automaticamente")
        self.autosave.setChecked(bool(self.cfg.get("sstv_autosave", True)))
        self.autosave.toggled.connect(lambda v: self._set("sstv_autosave", bool(v)))
        rg.addWidget(self.autosave, 1, 3)
        self.rx_status = QLabel("Parado. Ligue o RTL-SDR (ou ligue o áudio do rádio na placa de som) e clique em Receber.")
        self.rx_status.setWordWrap(True)
        self.rx_status.setStyleSheet("color:#a8cee0;font-size:11px")
        rg.addWidget(self.rx_status, 2, 0, 1, 4)
        self.preview = QLabel()
        self.preview.setMinimumSize(320, 256)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background:#05111c;border:1px solid #1d3b52")
        rg.addWidget(self.preview, 3, 0, 1, 4)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Salvar imagem…")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_as)
        self.open_folder = QPushButton("Abrir pasta das imagens")
        self.open_folder.clicked.connect(self.show_folder)
        buttons.addWidget(self.save_button); buttons.addWidget(self.open_folder); buttons.addStretch(1)
        rg.addLayout(buttons, 4, 0, 1, 4)
        doppler = QLabel("Doppler: o RTL-SDR do programa (ou o rádio com Auto CAT / Doppler nos equipamentos) "
                         "acompanha o satélite; o desvio de tom que sobrar é medido no cabeçalho VIS e descontado.")
        doppler.setWordWrap(True)
        doppler.setStyleSheet("color:#8fb3c7;font-size:10px")
        rg.addWidget(doppler, 5, 0, 1, 4)
        root.addWidget(rx)

        tx = QGroupBox("Transmitir SSTV")
        tg = QGridLayout(tx)
        self.tx_pick = QPushButton("Escolher imagem…")
        self.tx_pick.clicked.connect(self.pick_image)
        self.tx_mode = QComboBox()
        for name in sstv.MODES:
            self.tx_mode.addItem(name, name)
        self.tx_mode.setCurrentIndex(max(0, self.tx_mode.findData(self.cfg.get("sstv_tx_mode", "Robot 36"))))
        self.tx_mode.currentIndexChanged.connect(self._tx_changed)
        tg.addWidget(self.tx_pick, 0, 0); tg.addWidget(QLabel("Modo"), 0, 1); tg.addWidget(self.tx_mode, 0, 2)
        self.tx_text = QLineEdit(str(self.cfg.get("sstv_tx_text", "") or self.cfg.get("callsign", "")))
        self.tx_text.setPlaceholderText("Texto na imagem (ex.: indicativo)")
        self.tx_text.editingFinished.connect(self._tx_changed)
        tg.addWidget(QLabel("Texto"), 1, 0); tg.addWidget(self.tx_text, 1, 1, 1, 2)
        self.tx_output = QComboBox()
        for name in self._outputs():
            self.tx_output.addItem(name, name)
        self.tx_output.setCurrentIndex(max(0, self.tx_output.findData(self.cfg.get("sstv_tx_output", ""))))
        tg.addWidget(QLabel("Saída de áudio"), 2, 0); tg.addWidget(self.tx_output, 2, 1, 1, 2)
        self.tx_preview = QLabel()
        self.tx_preview.setMinimumSize(160, 128)
        self.tx_preview.setAlignment(Qt.AlignCenter)
        self.tx_preview.setStyleSheet("background:#05111c;border:1px solid #1d3b52")
        tg.addWidget(self.tx_preview, 0, 3, 4, 1)
        row = QHBoxLayout()
        self.tx_button = QPushButton("Transmitir")
        self.tx_button.setEnabled(False)
        self.tx_button.clicked.connect(self.transmit)
        self.tx_stop = QPushButton("Parar")
        self.tx_stop.setEnabled(False)
        self.tx_stop.clicked.connect(self.stop_tx)
        self.tx_wav = QPushButton("Salvar WAV…")
        self.tx_wav.setEnabled(False)
        self.tx_wav.clicked.connect(self.save_wav)
        row.addWidget(self.tx_button); row.addWidget(self.tx_stop); row.addWidget(self.tx_wav); row.addStretch(1)
        tg.addLayout(row, 3, 0, 1, 3)
        self.tx_status = QLabel("PTT pelo VOX do rádio ou da interface de áudio: o programa não aciona PTT. "
                                "O uplink segue o Doppler pelo Auto CAT / Doppler nos equipamentos.")
        self.tx_status.setWordWrap(True)
        self.tx_status.setStyleSheet("color:#a8cee0;font-size:11px")
        tg.addWidget(self.tx_status, 4, 0, 1, 4)
        root.addWidget(tx)
        root.addStretch(1)

    def _set(self, key, value):
        self.cfg[key] = value
        self.w.config.save()

    @staticmethod
    def _devices(kind):
        try:
            from PySide6.QtMultimedia import QMediaDevices
        except ImportError:
            return []
        try:
            return list(getattr(QMediaDevices, kind)())
        except Exception:
            return []

    def _inputs(self):
        return [d.description() for d in self._devices("audioInputs")]

    def _outputs(self):
        return [d.description() for d in self._devices("audioOutputs")] or ["Padrão do sistema"]

    # ------------------------------------------------------------ recepção
    def toggle_rx(self, on):
        if on:
            source = self.rx_source.currentData()
            self._set("sstv_rx_source", source)
            self.worker.start()
            if source != SDR_SOURCE and not self._open_input(source):
                self.rx_button.setChecked(False)
                return
            self.rx_button.setText("Parar recepção")
            self.rx_status.setText("Aguardando o cabeçalho VIS…")
            self.w.log(f"SSTV: recepção ligada ({self.rx_source.currentText()})")
        else:
            self._close_input()
            self.worker.stop()
            self.rx_button.setText("Receber")
            if self.current is not None and self.current.rows_done:
                self._finish(self.current, partial=True)
            self.current = None
            self.rx_status.setText("Parado.")
            self.w.log("SSTV: recepção desligada")

    @property
    def listening_sdr(self):
        return self.worker.running and self.rx_source.currentData() == SDR_SOURCE

    def feed_sdr(self, audio):
        """Chamado pela thread do receptor RTL-SDR (áudio 48 kHz)."""
        if self.worker.running and self.cfg.get("sstv_rx_source", SDR_SOURCE) == SDR_SOURCE:
            self.worker.push(audio)

    def _open_input(self, name):
        try:
            from PySide6.QtMultimedia import QAudioFormat, QAudioSource
        except ImportError:
            self.rx_status.setText("Placa de som indisponível nesta versão do Qt; use o RTL-SDR.")
            return False
        device = next((d for d in self._devices("audioInputs") if d.description() == name), None)
        if device is None:
            self.rx_status.setText(f"Entrada de áudio não encontrada: {name}")
            return False
        fmt = QAudioFormat()
        fmt.setSampleRate(RATE); fmt.setChannelCount(1); fmt.setSampleFormat(QAudioFormat.Int16)
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()
        self._in_rate = fmt.sampleRate()
        self._in_channels = max(1, fmt.channelCount())
        self._in_float = fmt.sampleFormat() == QAudioFormat.Float
        if self._in_rate != RATE:
            self.worker.decoder = sstv.Decoder(self._in_rate)
        self.source = QAudioSource(device, fmt, self)
        self.source_io = self.source.start()
        self.source_io.readyRead.connect(self._read_input)
        return True

    def _read_input(self):
        if self.source_io is None:
            return
        raw = bytes(self.source_io.readAll())
        if not raw:
            return
        if self._in_float:
            data = np.frombuffer(raw[:len(raw) // 4 * 4], np.float32)
        else:
            data = np.frombuffer(raw[:len(raw) // 2 * 2], "<i2").astype(np.float32) / 32768.0
        if self._in_channels > 1:
            data = data[:len(data) // self._in_channels * self._in_channels].reshape(-1, self._in_channels).mean(axis=1)
        self.worker.push(data)

    def _close_input(self):
        if self.source is not None:
            try:
                self.source.stop()
            except Exception:
                pass
        self.source = self.source_io = None
        if self.worker.decoder.rate != RATE:
            self.worker.decoder = sstv.Decoder(RATE)

    def force_start(self):
        name = self.rx_mode.currentData()
        if not name:
            QMessageBox.information(self, "SSTV", "Escolha o modo para começar sem o cabeçalho VIS.")
            return
        if not self.rx_button.isChecked():
            self.rx_button.setChecked(True)
        dec = self.worker.decoder
        dec.force_mode(name, start_s=(dec.base + len(dec.freq)) / dec.fr)
        self.current = dec.image
        self.rx_status.setText(f"Recebendo {name} (início manual)…")

    def drain(self):
        changed = False
        while True:
            try:
                kind, mode, pixels, rows, offset, slant, image = self.worker.events_q.get_nowait()
            except queue.Empty:
                break
            if kind == "error":
                self.w.log(f"SSTV: {mode}")
                continue
            if kind == "start":
                self.current = image
                self.last_meta = self._meta()
                self.rx_status.setText(f"Recebendo {mode} · desvio de tom {offset:+.0f} Hz")
                self.w.log(f"SSTV: VIS {mode} reconhecido, desvio de tom {offset:+.0f} Hz")
            elif kind == "rows":
                self.current = image
                changed = True
            elif kind == "done":
                image.pixels = pixels
                self._finish(image)
        if changed and self.current is not None:
            img = self.current
            self.last_rgb = img.pixels
            self._show(img.pixels, self.preview)
            self.rx_status.setText(f"Recebendo {img.mode.name} · linha {img.rows_done}/{img.mode.height} · "
                                   f"desvio de tom {img.offset_hz:+.0f} Hz")
            self.save_button.setEnabled(True)

    def _meta(self):
        snap = getattr(self.sdr, "last_snapshot", None) or {}
        return {"sat": str(snap.get("name") or ""), "norad": str(snap.get("norad") or "")}

    def _finish(self, image, partial=False):
        self.last_rgb = image.pixels.copy()
        self._show(self.last_rgb, self.preview)
        self.save_button.setEnabled(True)
        state = "incompleta" if partial else "completa"
        text = f"Imagem {image.mode.name} {state} · inclinação corrigida {image.slant_ppm:+.0f} ppm"
        if self.autosave.isChecked():
            path = self.auto_path(image.mode.name)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                qimage_from_rgb(self.last_rgb).save(str(path))
                text += f" · salva em {path}"
                self.w.log(f"SSTV: imagem salva em {path}")
            except OSError as exc:
                text += f" · falha ao salvar: {exc}"
        self.rx_status.setText(text)
        self.current = None

    def auto_path(self, mode_name):
        meta = self.last_meta or self._meta()
        sat = "".join(c for c in meta.get("sat", "") if c.isalnum())[:20]
        stamp_text = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = "_".join(p for p in (stamp_text, mode_name.replace(" ", ""), sat) if p)
        return self.folder / f"{name}.png"

    def _show(self, rgb, label):
        pix = QPixmap.fromImage(qimage_from_rgb(rgb))
        label.setPixmap(pix.scaled(label.width(), label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def save_as(self):
        if self.last_rgb is None:
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Salvar imagem SSTV", str(self.auto_path("SSTV")),
                                              "PNG (*.png);;JPEG (*.jpg)")
        if path:
            qimage_from_rgb(self.last_rgb).save(path)
            self.rx_status.setText(f"Imagem salva em {path}")

    def show_folder(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))

    # ---------------------------------------------------------- transmissão
    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Imagem para SSTV", str(self.folder),
                                              "Imagens (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.load_tx_image(path)

    def load_tx_image(self, path):
        image = QImage(str(path))
        if image.isNull():
            QMessageBox.warning(self, "SSTV", "Não foi possível abrir a imagem.")
            return False
        self.tx_source = image
        self._tx_changed()
        return True

    def _tx_changed(self, *_):
        self._set("sstv_tx_mode", self.tx_mode.currentData())
        self._set("sstv_tx_text", self.tx_text.text().strip())
        if getattr(self, "tx_source", None) is None:
            return
        mode = sstv.MODES[self.tx_mode.currentData()]
        scaled = self.tx_source.scaled(mode.width, mode.height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.tx_rgb = rgb_from_qimage(stamp(scaled, self.tx_text.text().strip()))
        self.tx_audio = sstv.encode(self.tx_rgb, mode.name, RATE)
        self._show(self.tx_rgb, self.tx_preview)
        self.tx_button.setEnabled(True)
        self.tx_wav.setEnabled(True)
        self.tx_status.setText(f"{mode.name}: {mode.width}×{mode.height}, {mode.duration_s + 0.91:.0f} s de áudio. "
                               "PTT pelo VOX do rádio ou da interface: o programa não aciona PTT.")

    def save_wav(self):
        if self.tx_audio is None:
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Salvar áudio SSTV", str(self.folder / "sstv_tx.wav"), "WAV (*.wav)")
        if path:
            sstv.write_wav(path, self.tx_audio, RATE)
            self.tx_status.setText(f"Áudio salvo em {path}")

    def transmit(self):
        if self.tx_audio is None:
            return
        try:
            from PySide6.QtMultimedia import QAudioFormat, QAudioSink
        except ImportError:
            self.tx_status.setText("Saída de áudio indisponível nesta versão do Qt; use Salvar WAV.")
            return
        if QMessageBox.question(self, "Transmitir SSTV",
                                "Tocar o áudio SSTV na saída escolhida? O rádio só transmite se o VOX (ou a "
                                "interface) estiver ligado; confira a frequência de uplink e a potência.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._set("sstv_tx_output", self.tx_output.currentData())
        devices = self._devices("audioOutputs")
        device = next((d for d in devices if d.description() == self.tx_output.currentData()), None)
        if device is None:
            from PySide6.QtMultimedia import QMediaDevices
            device = QMediaDevices.defaultAudioOutput()
        fmt = QAudioFormat()
        fmt.setSampleRate(RATE); fmt.setChannelCount(1); fmt.setSampleFormat(QAudioFormat.Int16)
        pcm = (np.clip(self.tx_audio, -1, 1) * 32767).astype("<i2").tobytes()
        self.stop_tx()
        self.tx_buffer = QBuffer(self)
        self.tx_buffer.setData(QByteArray(pcm))
        self.tx_buffer.open(QIODevice.ReadOnly)
        self.sink = QAudioSink(device, fmt, self)
        self.sink.stateChanged.connect(self._tx_state)
        self.sink.start(self.tx_buffer)
        self.tx_button.setEnabled(False)
        self.tx_stop.setEnabled(True)
        self.tx_status.setText(f"Transmitindo {self.tx_mode.currentData()} ({len(self.tx_audio) / RATE:.0f} s)…")
        self.w.log(f"SSTV: transmissão {self.tx_mode.currentData()} iniciada em {device.description()}")

    def _tx_state(self, state):
        try:
            from PySide6.QtMultimedia import QAudio
        except ImportError:
            return
        if state == QAudio.IdleState:
            self.stop_tx(done=True)

    def stop_tx(self, done=False):
        if self.sink is not None:
            try:
                self.sink.stop()
            except Exception:
                pass
            self.sink = None
            self.tx_status.setText("Transmissão concluída." if done else "Transmissão interrompida.")
            self.w.log("SSTV: transmissão " + ("concluída" if done else "interrompida"))
        self.tx_buffer = None
        self.tx_button.setEnabled(self.tx_audio is not None)
        self.tx_stop.setEnabled(False)

    def shutdown(self):
        self.stop_tx()
        self._close_input()
        self.worker.stop()
