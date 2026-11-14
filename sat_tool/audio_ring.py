"""Buffer de áudio do SDR com jitter buffer e compensação de deriva (v1.6.0).

A thread de recepção escreve (push) blocos float32 48 kHz; a placa de som lê (pull) pelo
QAudioSink. Alvo de ~300 ms no buffer: acima de 600 ms o áudio é levemente comprimido
(0,5 %), abaixo de 150 ms levemente esticado — compensa a diferença entre o relógio do
RTL-SDR e o da placa de som sem cortes. Falta de dados devolve silêncio e conta underrun.
"""
from __future__ import annotations

import threading

import numpy as np

RATE = 48_000


class AudioRing:
    def __init__(self, target_ms: int = 300, max_ms: int = 1500):
        self._buf = np.zeros(0, dtype=np.float32)
        self._lock = threading.Lock()
        self.target = int(RATE * target_ms / 1000)
        self.max = int(RATE * max_ms / 1000)
        self.primed = False
        self.underruns = 0
        self.adjustments = 0
        self.drops = 0

    @property
    def level_ms(self) -> float:
        return len(self._buf) * 1000.0 / RATE

    def push(self, audio: np.ndarray):
        audio = np.asarray(audio, dtype=np.float32)
        if not len(audio):
            return
        with self._lock:
            n = len(self._buf)
            factor = 1.0
            if self.primed and n > 2 * self.target:
                factor = 0.995
            elif self.primed and n < self.target // 2:
                factor = 1.005
            if factor != 1.0:
                m = max(1, int(round(len(audio) * factor)))
                audio = np.interp(np.linspace(0, len(audio) - 1, m), np.arange(len(audio)), audio).astype(np.float32)
                self.adjustments += 1
            self._buf = np.concatenate([self._buf, audio])
            if len(self._buf) > self.max:  # nunca acumula atraso: descarta o mais antigo
                self._buf = self._buf[-self.target:]
                self.drops += 1
            if not self.primed and len(self._buf) >= self.target:
                self.primed = True

    def pull(self, n: int) -> np.ndarray:
        with self._lock:
            if not self.primed:
                return np.zeros(n, dtype=np.float32)
            if len(self._buf) < n:
                out = np.concatenate([self._buf, np.zeros(n - len(self._buf), dtype=np.float32)])
                self._buf = np.zeros(0, dtype=np.float32)
                self.underruns += 1
                self.primed = False  # reabastece antes de voltar a tocar
                return out
            out, self._buf = self._buf[:n], self._buf[n:]
            return out

    def clear(self):
        with self._lock:
            self._buf = np.zeros(0, dtype=np.float32)
            self.primed = False
