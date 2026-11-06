"""Processamento de sinal do SDR (somente numpy): canalização, demodulação e espectro.

Fluxo (inspirado nos "pipelines" do SatDump): IQ do SDR → mixer para o canal →
decimação em dois estágios → demodulador FM/USB/LSB/CW → áudio 48 kHz.
Todos os blocos mantêm estado entre blocos de amostras (streaming sem cliques).
"""
from __future__ import annotations

import numpy as np

SDR_RATE = 960_000
AUDIO_RATE = 48_000
CW_PITCH_HZ = 700.0

# Larguras de canal (Hz) por modo: banda passante do áudio útil.
CHANNEL_WIDTH = {"FM": 12_000.0, "USB": 2_800.0, "LSB": 2_800.0, "CW": 500.0}


def lowpass_taps(cutoff_hz: float, rate: float, taps: int) -> np.ndarray:
    """FIR passa-baixa por janela de Blackman, ganho unitário em DC."""
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(2 * cutoff_hz / rate * n) * np.blackman(taps)
    return (h / h.sum()).astype(np.float32)


class FirDecimator:
    """Filtro FIR + decimação inteira, com histórico entre blocos."""

    def __init__(self, taps: np.ndarray, factor: int):
        self.taps = taps
        self.factor = int(factor)
        self.history = np.zeros(len(taps) - 1, dtype=np.complex64)
        self.phase = 0

    def process(self, x: np.ndarray) -> np.ndarray:
        data = np.concatenate([self.history, x.astype(np.complex64)])
        y = np.convolve(data, self.taps, mode="valid")
        self.history = data[-(len(self.taps) - 1):]
        out = y[self.phase::self.factor]
        self.phase = (self.phase - len(y)) % self.factor
        return out.astype(np.complex64)


class Mixer:
    """Oscilador numérico contínuo: desloca o espectro de -offset_hz."""

    def __init__(self, rate: float):
        self.rate = float(rate)
        self.phase = 0.0
        self.offset_hz = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.offset_hz:
            return x
        step = -2 * np.pi * self.offset_hz / self.rate
        ph = self.phase + step * np.arange(len(x))
        self.phase = float((self.phase + step * len(x)) % (2 * np.pi))
        return (x * np.exp(1j * ph)).astype(np.complex64)


class Demodulator:
    """Converte IQ (taxa SDR_RATE, canal deslocado de offset_hz) em áudio float32 48 kHz."""

    def __init__(self, mode: str = "FM", sdr_rate: int = SDR_RATE):
        if sdr_rate % AUDIO_RATE:
            raise ValueError("A taxa do SDR deve ser múltipla de 48 kHz")
        self.sdr_rate = sdr_rate
        self.mixer = Mixer(sdr_rate)
        total = sdr_rate // AUDIO_RATE
        first = 5 if total % 5 == 0 else (4 if total % 4 == 0 else 1)
        self.stage1 = FirDecimator(lowpass_taps(40_000, sdr_rate, 63), first)
        self.mid_rate = sdr_rate // first
        self.stage2_factor = total // first
        self.squelch_db = -200.0
        self.volume = 1.0
        self.level_db = -200.0
        self._agc = 1e-3
        self._last = np.complex64(1)
        self._bfo_phase = 0.0
        self.last_channel = np.zeros(0, dtype=np.complex64)
        # v1.6.0: squelch por qualidade do sinal (0–100): FM por ruído do discriminador,
        # SSB/CW por SNR em relação ao piso estimado; histerese, retenção e rampa sem cliques.
        self.squelch_pct = 0.0
        self.quality = 0.0
        self._floor_db = None
        self._open = True
        self._gain = 1.0
        self._hold_until = 0
        self._samples = 0
        self.width_hz = None
        self.set_mode(mode)

    def set_mode(self, mode: str, width_hz: float | None = None):
        mode = (mode or "FM").upper()
        self.mode = mode if mode in CHANNEL_WIDTH else "FM"
        self.width_hz = width_hz
        width = float(width_hz) if width_hz else CHANNEL_WIDTH[self.mode]
        cutoff = width / 2 if self.mode in ("FM", "CW") else width / 2
        self.stage2 = FirDecimator(lowpass_taps(max(cutoff, 600.0) if self.mode != "CW" else max(100.0, width / 2),
                                                self.mid_rate, 129), self.stage2_factor)
        # SSB: canal complexo 0..2,8 kHz (USB) ou -2,8..0 (LSB) via filtro deslocado.
        if self.mode in ("USB", "LSB"):
            base = lowpass_taps(width / 2, AUDIO_RATE, 129)
            sign = 1 if self.mode == "USB" else -1
            n = np.arange(len(base)) - (len(base) - 1) / 2
            self.sideband = (base * np.exp(2j * np.pi * sign * (width / 2) / AUDIO_RATE * n)).astype(np.complex64)
        else:
            self.sideband = None
        self._sb_hist = np.zeros(128, dtype=np.complex64)
        self._audio_lp = lowpass_taps(3_500, AUDIO_RATE, 63)
        self._audio_hist = np.zeros(62, dtype=np.float32)

    @property
    def offset_hz(self) -> float:
        return self.mixer.offset_hz

    @offset_hz.setter
    def offset_hz(self, value: float):
        self.mixer.offset_hz = float(value)

    def process(self, iq: np.ndarray) -> np.ndarray:
        x = self.stage2.process(self.stage1.process(self.mixer.process(iq)))
        self.last_channel = x  # IQ do canal a 48 kHz (gravação opcional)
        if not len(x):
            return np.zeros(0, dtype=np.float32)
        power = float(np.mean(np.abs(x) ** 2)) + 1e-20
        self.level_db = 10 * np.log10(power)
        if self.mode == "FM":
            prev = np.concatenate([[self._last], x[:-1]])
            self._last = x[-1]
            audio = np.angle(x * np.conj(prev)).astype(np.float32) / np.pi
            raw = audio
            data = np.concatenate([self._audio_hist, audio])
            audio = np.convolve(data, self._audio_lp, mode="valid").astype(np.float32)
            self._audio_hist = data[-62:]
            # Ruído do discriminador: energia acima da voz (bruto − passa-baixa 3,5 kHz), como num rádio FM.
            delay = len(self._audio_lp) // 2
            hf = raw[:len(raw) - delay] - audio[delay:] if len(raw) > delay else raw
            noise = float(np.sqrt(np.mean(hf ** 2))) if len(hf) else 1.0
            self.noise_hf = noise
            self.quality = float(np.clip((0.16 - noise) / 0.13 * 100.0, 0, 100))
            audio *= 2.0
        else:
            if self.sideband is not None:
                data = np.concatenate([self._sb_hist, x])
                x = np.convolve(data, self.sideband, mode="valid").astype(np.complex64)
                self._sb_hist = data[-128:]
                audio = x.real.astype(np.float32)
            else:  # CW: batimento com BFO de 700 Hz
                step = 2 * np.pi * CW_PITCH_HZ / AUDIO_RATE
                ph = self._bfo_phase + step * np.arange(len(x))
                self._bfo_phase = float((self._bfo_phase + step * len(x)) % (2 * np.pi))
                audio = (x * np.exp(1j * ph)).real.astype(np.float32)
            # SNR do canal sobre o piso de ruído (mínimo móvel que sobe devagar).
            if self._floor_db is None or self.level_db < self._floor_db:
                self._floor_db = self.level_db
            else:
                self._floor_db += 0.02
            self.quality = float(np.clip((self.level_db - self._floor_db) / 20.0 * 100.0, 0, 100))
            peak = float(np.max(np.abs(audio))) + 1e-12
            self._agc = max(peak, self._agc * 0.9)  # AGC de ataque rápido, queda lenta
            audio = audio / self._agc * 0.5
        if self.level_db < self.squelch_db:
            audio = np.zeros_like(audio)
        audio = self._apply_squelch(audio)
        return np.clip(audio * self.volume, -1.0, 1.0).astype(np.float32)

    def _apply_squelch(self, audio: np.ndarray) -> np.ndarray:
        n = len(audio)
        self._samples += n
        if self.squelch_pct <= 0:
            self._open = True
        elif self.quality >= self.squelch_pct:
            self._open = True
            self._hold_until = self._samples + int(0.3 * AUDIO_RATE)   # segura 300 ms
        elif self.quality < self.squelch_pct - 5 and self._samples > self._hold_until:
            self._open = False
        target = 1.0 if self._open else 0.0
        if target == self._gain:
            return audio if target else np.zeros_like(audio)
        ramp = np.clip(self._gain + (target - self._gain) * np.arange(1, n + 1) / max(1, int(0.01 * AUDIO_RATE)),
                       0.0, 1.0).astype(np.float32)
        self._gain = float(ramp[-1])
        return audio * ramp


def power_spectrum_db(iq: np.ndarray, fft_size: int = 4096) -> np.ndarray:
    """Espectro médio em dB (centralizado em 0 Hz), para o waterfall."""
    n = len(iq) // fft_size
    if n < 1:
        iq = np.pad(iq, (0, fft_size - len(iq)))
        n = 1
    frames = iq[:n * fft_size].reshape(n, fft_size) * np.hanning(fft_size).astype(np.float32)
    spec = np.mean(np.abs(np.fft.fft(frames, axis=1)) ** 2, axis=0)
    return (10 * np.log10(np.fft.fftshift(spec) / fft_size ** 2 + 1e-20)).astype(np.float32)


def float_to_pcm16(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
