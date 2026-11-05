"""Receptor SDR embutido (RTL-SDR): detecção, leitura IQ, Doppler, áudio, decodificação e gravação.

Sem Qt aqui: roda numa thread própria e entrega áudio, espectro e quadros por callbacks.
A sintonia acompanha o Doppler por deslocamento digital do canal (sem regravar o
oscilador do dongle a cada passo); o centro só é reposicionado quando o canal se
afasta demais, evitando cliques. O canal fica deslocado de IF_OFFSET do centro para
fugir do pico de DC do RTL-SDR.
"""
from __future__ import annotations

import sys
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from . import ax25, dsp

IF_OFFSET = 120_000          # canal a 120 kHz do centro (fora do pico de DC)
RETUNE_MARGIN = 300_000      # reposiciona o centro se o canal passar disso
BLOCK = 96_000               # 0,1 s a 960 kS/s
RTL_IDS = {(0x0BDA, 0x2838), (0x0BDA, 0x2832)}

ZADIG_HELP = ("O Windows está usando o driver de TV digital no RTL-SDR. Instale o driver WinUSB "
              "uma única vez com o Zadig (zadig.akeo.ie): Options → List All Devices → "
              "\"Bulk-In, Interface (Interface 0)\" → WinUSB → Replace Driver. Depois reconecte o dongle.")
LINUX_HELP = ("Sem permissão para o RTL-SDR. Instale a regra udev incluída no pacote "
              "(linux/rtl-sdr.rules em /etc/udev/rules.d/) e bloqueie o módulo dvb_usb_rtl28xxu; reconecte.")


@dataclass
class SdrDevice:
    index: int
    name: str
    serial: str = ""
    remote: str = ""   # host:porta quando rtl_tcp

    @property
    def label(self) -> str:
        if self.remote:
            return f"rtl_tcp {self.remote}"
        return f"{self.name} #{self.index}" + (f" · S/N {self.serial}" if self.serial else "")


def _librtlsdr():
    try:
        import pyrtlsdrlib  # noqa: F401 — fornece a biblioteca nativa empacotada
    except Exception:
        pass
    from rtlsdr.librtlsdr import librtlsdr
    return librtlsdr


def detect_devices() -> tuple[list[SdrDevice], str]:
    """Lista dongles RTL-SDR visíveis. Retorna (dispositivos, mensagem de diagnóstico)."""
    try:
        lib = _librtlsdr()
    except Exception as exc:
        return [], f"Biblioteca librtlsdr indisponível: {type(exc).__name__}"
    import ctypes
    devices = []
    try:
        count = int(lib.rtlsdr_get_device_count())
        for i in range(count):
            name = lib.rtlsdr_get_device_name(i)
            name = name.decode("utf-8", "replace") if isinstance(name, bytes) else str(name or "RTL-SDR")
            m, p, s = (ctypes.create_string_buffer(256) for _ in range(3))
            serial = ""
            if lib.rtlsdr_get_device_usb_strings(i, m, p, s) == 0:
                serial = s.value.decode("utf-8", "replace")
            devices.append(SdrDevice(i, name or "RTL-SDR", serial))
    except Exception as exc:
        return [], f"Falha ao listar RTL-SDR: {exc}"
    return devices, ("" if devices else "Nenhum RTL-SDR conectado")


def open_error_help(exc: BaseException) -> str:
    text = str(exc)
    if sys.platform == "win32" and ("-12" in text or "-3" in text or "-5" in text or "LIBUSB" in text.upper()):
        return ZADIG_HELP
    if sys.platform.startswith("linux") and ("-3" in text or "ermission" in text or "busy" in text.lower() or "-6" in text):
        return LINUX_HELP
    return f"Não foi possível abrir o RTL-SDR: {text}"


@dataclass
class SdrSettings:
    gain_db: Optional[float] = None    # None = automático
    ppm: int = 0
    bias_tee: bool = False
    squelch_db: float = -200.0
    volume: float = 0.8


class RtlSource:
    """Fonte IQ real (pyrtlsdr), local ou rtl_tcp."""

    def __init__(self, device: SdrDevice, settings: SdrSettings):
        if device.remote:
            from rtlsdr import RtlSdrTcpClient
            host, _, port = device.remote.partition(":")
            self.sdr = RtlSdrTcpClient(hostname=host, port=int(port or 1234))
        else:
            _librtlsdr()
            from rtlsdr import RtlSdr
            self.sdr = RtlSdr(device_index=device.index)
        self.sdr.sample_rate = dsp.SDR_RATE
        if settings.ppm:
            self.sdr.freq_correction = int(settings.ppm)
        self.sdr.gain = "auto" if settings.gain_db is None else float(settings.gain_db)
        if settings.bias_tee and hasattr(self.sdr, "set_bias_tee"):
            self.sdr.set_bias_tee(True)

    def set_center(self, hz: int):
        self.sdr.center_freq = int(hz)

    def read(self, n: int) -> np.ndarray:
        return np.asarray(self.sdr.read_samples(n), dtype=np.complex64)

    def close(self):
        try:
            if hasattr(self.sdr, "set_bias_tee"):
                self.sdr.set_bias_tee(False)
        except Exception:
            pass
        self.sdr.close()


class SimulatedSource:
    """Fonte sintética para testes e demonstração: portadora (opcionalmente modulada) + ruído."""

    def __init__(self, signal_hz: float = 0.0, fm_tone: float = 0.0, afsk_audio: Optional[np.ndarray] = None):
        self.center = 0
        self.signal_hz = float(signal_hz)
        self.fm_tone = fm_tone
        self.afsk = afsk_audio
        self.t = 0
        self.fm_phase = 0.0
        self.rng = np.random.default_rng(7)

    def set_center(self, hz: int):
        self.center = int(hz)

    def read(self, n: int) -> np.ndarray:
        idx = self.t + np.arange(n)
        self.t += n
        f = self.signal_hz - self.center
        phase = 2 * np.pi * f * idx / dsp.SDR_RATE
        if self.afsk is not None:
            # FM 5 kHz de desvio com o áudio AFSK repetido
            a = np.interp(idx / dsp.SDR_RATE * dsp.AUDIO_RATE % len(self.afsk),
                          np.arange(len(self.afsk)), self.afsk)
            dev = 2 * np.pi * 5000 * np.cumsum(a) / dsp.SDR_RATE + self.fm_phase
            self.fm_phase = float(dev[-1])
            phase = phase + dev
        elif self.fm_tone:
            phase = phase + 5000 / self.fm_tone * np.sin(2 * np.pi * self.fm_tone * idx / dsp.SDR_RATE)
        noise = (self.rng.normal(0, 0.05, n) + 1j * self.rng.normal(0, 0.05, n))
        time.sleep(0)  # cede a CPU
        return (np.exp(1j * phase) * 0.5 + noise).astype(np.complex64)

    def close(self):
        pass


@dataclass
class ReceiverStatus:
    running: bool = False
    center_hz: int = 0
    channel_hz: int = 0
    mode: str = "FM"
    level_db: float = -200.0
    frames: int = 0
    error: str = ""
    recording: str = ""


class PassRecorder:
    """Grava a passagem como no SatDump: áudio WAV 48 kHz e, opcional, IQ do canal (cf32 48 kHz)."""

    def __init__(self, folder: Path, name: str, iq: bool = False):
        folder.mkdir(parents=True, exist_ok=True)
        self.audio_path = folder / f"{name}.wav"
        self.wav = wave.open(str(self.audio_path), "wb")
        self.wav.setnchannels(1)
        self.wav.setsampwidth(2)
        self.wav.setframerate(dsp.AUDIO_RATE)
        self.iq_file = open(folder / f"{name}_iq48k.cf32", "wb") if iq else None

    def write(self, audio: np.ndarray, channel_iq: Optional[np.ndarray] = None):
        self.wav.writeframes(dsp.float_to_pcm16(audio))
        if self.iq_file is not None and channel_iq is not None:
            self.iq_file.write(channel_iq.astype(np.complex64).tobytes())

    def close(self):
        self.wav.close()
        if self.iq_file:
            self.iq_file.close()


class SdrReceiver:
    """Thread de recepção. Métodos públicos são seguros para chamar da GUI."""

    def __init__(self, source_factory: Callable[[], object], *,
                 on_audio: Callable[[np.ndarray], None] = lambda a: None,
                 on_spectrum: Callable[[np.ndarray, int], None] = lambda s, c: None,
                 on_frame: Callable[[bytes, str], None] = lambda f, src: None,
                 fft_size: int = 4096, spectrum_hz: float = 20.0):
        self.source_factory = source_factory
        self.on_audio, self.on_spectrum, self.on_frame = on_audio, on_spectrum, on_frame
        self.fft_size = fft_size
        self.spectrum_period = 1.0 / spectrum_hz
        self.demod = dsp.Demodulator("FM")
        self.afsk: Optional[ax25.AfskDemodulator] = None
        self.status = ReceiverStatus()
        self._lock = threading.Lock()
        self._target = 0
        self._center = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._recorder: Optional[PassRecorder] = None
        self._last_spec = 0.0

    # --- controle (GUI) -------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="sdr-rx", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self.stop_recording()

    def tune(self, downlink_hz: int):
        """Frequência do canal já com Doppler; pode ser chamada várias vezes por segundo."""
        with self._lock:
            self._target = int(downlink_hz)

    def set_mode(self, mode: str):
        with self._lock:
            mode = (mode or "FM").upper()
            if mode != self.demod.mode:
                offset = self.demod.offset_hz
                self.demod.set_mode(mode)
                self.demod.offset_hz = offset
            self.status.mode = self.demod.mode

    def set_decoder(self, pipeline: str):
        with self._lock:
            self.afsk = ax25.AfskDemodulator() if pipeline == "afsk1200" else None

    def set_squelch(self, db: float):
        self.demod.squelch_db = float(db)

    def set_volume(self, v: float):
        self.demod.volume = float(v)

    def start_recording(self, folder: Path, name: str, iq: bool = False):
        with self._lock:
            if self._recorder is None:
                self._recorder = PassRecorder(folder, name, iq)
                self.status.recording = str(self._recorder.audio_path)

    def stop_recording(self):
        with self._lock:
            if self._recorder is not None:
                self._recorder.close()
                self._recorder = None
                self.status.recording = ""

    # --- thread ---------------------------------------------------------
    def _run(self):
        source = None
        try:
            source = self.source_factory()
            self.status.running, self.status.error = True, ""
            while not self._stop.is_set():
                with self._lock:
                    target = self._target
                if target:
                    if not self._center or abs(target - self._center) > RETUNE_MARGIN or \
                            abs(target - self._center) < IF_OFFSET / 2:
                        self._center = target - IF_OFFSET
                        source.set_center(self._center)
                    self.demod.offset_hz = target - self._center
                iq = source.read(BLOCK)
                self._process(iq, target)
        except Exception as exc:
            self.status.error = open_error_help(exc)
        finally:
            self.status.running = False
            if source is not None:
                try:
                    source.close()
                except Exception:
                    pass

    def _process(self, iq: np.ndarray, target: int):
        with self._lock:
            audio = self.demod.process(iq)
            afsk = self.afsk
            recorder = self._recorder
        st = self.status
        st.center_hz, st.channel_hz, st.level_db = self._center, target, self.demod.level_db
        self.on_audio(audio)
        if recorder is not None:
            recorder.write(audio, self.demod.last_channel)
        if afsk is not None:
            for frame in afsk.process(audio):
                st.frames += 1
                self.on_frame(frame, "SDR AFSK1200")
        now = time.monotonic()
        if now - self._last_spec >= self.spectrum_period:
            self._last_spec = now
            self.on_spectrum(dsp.power_spectrum_db(iq, self.fft_size), self._center)
