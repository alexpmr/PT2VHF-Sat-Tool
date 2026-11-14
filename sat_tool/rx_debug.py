"""v1.9.1: debug do áudio de RX (pedido do operador: "interrupção a cada 2 segundos").

Grava em diagnostics/rx-audio-debug.log (também entra no "Baixar log completo (ZIP)"):
- uma linha de resumo por segundo: blocos lidos do RTL-SDR, tempo máximo de leitura e de
  processamento, leituras da placa de som, maior intervalo entre leituras, nível do buffer,
  falhas (underruns), ajustes de deriva, descartes e o maior atraso da interface;
- eventos na hora em que acontecem: falta de áudio na placa (underrun), resintonia do centro,
  leitura lenta do RTL-SDR, descarte por excesso no buffer, mudança de estado da saída de áudio;
- interface travada: um vigia em outra thread nota quando o laço da interface atrasa mais que
  STALL_MS e grava a pilha da thread principal (mostra qual rotina segurou o programa).
Tudo em horário UTC com milissegundos. Desligado, não custa nada.
"""
from __future__ import annotations

import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

FILE_NAME = "rx-audio-debug.log"
MAX_BYTES = 8 * 1024 * 1024
STALL_MS = 150
SLOW_READ_MS = 250


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


class RxAudioDebug:
    def __init__(self, directory: Path):
        self.path = Path(directory) / FILE_NAME
        self.enabled = False
        self._lock = threading.Lock()
        self._fh = None
        self._reset()
        self._main_ident = threading.main_thread().ident
        self._beat = time.monotonic()
        self._stall_logged = 0.0
        self._watch: threading.Thread | None = None
        self._stop = threading.Event()

    def _reset(self):
        self.blocks = 0
        self.read_max = 0.0
        self.proc_max = 0.0
        self.pulls = 0
        self.pull_gap_max = 0.0
        self.ring_min = None
        self.ring_max = 0.0
        self.gui_late_max = 0.0
        self._last_pull = None
        self._second = time.monotonic()
        self._prev_counts = None

    # ------------------------------------------------------------- arquivo
    def start(self, header: str = ""):
        with self._lock:
            if self.enabled:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size > MAX_BYTES:
                old = self.path.with_suffix(self.path.suffix + ".previous")
                try:
                    if old.exists():
                        old.unlink()
                    self.path.replace(old)
                except OSError:
                    pass
            self._fh = self.path.open("a", encoding="utf-8", buffering=1)
            self._reset()
            self.enabled = True
        self.event(f"=== debug do áudio RX ligado {datetime.now(timezone.utc):%Y-%m-%d} (UTC) {header}")
        self.event("resumo/s: blocos=leituras do RTL-SDR (0,1 s cada) leitura_max/proc_max em ms; "
                   "placa=leituras da placa de som, intervalo_max em ms; buffer min/max em ms; "
                   "falhas/ajustes/descartes acumulados; gui_atraso_max em ms")
        self._stop.clear()
        self._beat = time.monotonic()
        self._watch = threading.Thread(target=self._watchdog, name="rx-debug-watch", daemon=True)
        self._watch.start()

    def stop(self):
        if not self.enabled:
            return
        self.event("=== debug do áudio RX desligado")
        self._stop.set()
        with self._lock:
            self.enabled = False
            if self._fh is not None:
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None

    def event(self, text: str):
        with self._lock:
            if self._fh is None:
                return
            try:
                self._fh.write(f"{_stamp()} {text}\n")
            except OSError:
                pass

    # ------------------------------------------------------ pontos de medida
    def sdr_block(self, read_s: float, proc_s: float, iq_len: int, audio_len: int):
        """Thread do receptor, a cada bloco lido do RTL-SDR."""
        if not self.enabled:
            return
        self.blocks += 1
        self.read_max = max(self.read_max, read_s)
        self.proc_max = max(self.proc_max, proc_s)
        if read_s * 1000 >= SLOW_READ_MS:
            self.event(f"RTL-SDR: leitura lenta {read_s * 1000:.0f} ms ({iq_len} amostras IQ → {audio_len} de áudio)")

    def retune(self, center_hz: int, target_hz: int):
        if self.enabled:
            self.event(f"resintonia: centro {center_hz / 1e6:.6f} MHz · canal {target_hz / 1e6:.6f} MHz")

    def pull(self, requested: int, ring_ms: float, underrun: bool):
        """Placa de som (QAudioSink, thread da interface) pedindo áudio."""
        if not self.enabled:
            return
        now = time.monotonic()
        if self._last_pull is not None:
            self.pull_gap_max = max(self.pull_gap_max, now - self._last_pull)
        self._last_pull = now
        self.pulls += 1
        self.ring_min = ring_ms if self.ring_min is None else min(self.ring_min, ring_ms)
        self.ring_max = max(self.ring_max, ring_ms)
        if underrun:
            self.event(f"FALTA DE ÁUDIO (underrun): placa pediu {requested * 1000 // 48000} ms, "
                       f"buffer tinha {ring_ms:.0f} ms; silêncio até reabastecer 300 ms")

    def heartbeat(self):
        """Chamado pelo laço da interface (timer de 40 ms)."""
        now = time.monotonic()
        late = now - self._beat
        self._beat = now
        if self.enabled:
            self.gui_late_max = max(self.gui_late_max, late)

    def second(self, ring, sink_state: str = ""):
        """Resumo uma vez por segundo (interface)."""
        if not self.enabled:
            return
        now = time.monotonic()
        if now - self._second < 1.0:
            return
        counts = (ring.underruns, ring.adjustments, getattr(ring, "drops", 0))
        self.event(f"resumo: blocos={self.blocks} leitura_max={self.read_max * 1000:.0f} proc_max={self.proc_max * 1000:.0f} "
                   f"placa={self.pulls} intervalo_max={self.pull_gap_max * 1000:.0f} "
                   f"buffer={self.ring_min or 0:.0f}/{self.ring_max:.0f} falhas={counts[0]} ajustes={counts[1]} "
                   f"descartes={counts[2]} gui_atraso_max={self.gui_late_max * 1000:.0f}"
                   + (f" saida={sink_state}" if sink_state else ""))
        self.blocks = self.pulls = 0
        self.read_max = self.proc_max = self.pull_gap_max = self.ring_max = self.gui_late_max = 0.0
        self.ring_min = None
        self._second = now

    # ------------------------------------------------------- vigia da interface
    def _watchdog(self):
        while not self._stop.wait(0.05):
            late = time.monotonic() - self._beat
            if late * 1000 < STALL_MS or time.monotonic() - self._stall_logged < 1.0:
                continue
            self._stall_logged = time.monotonic()
            frame = sys._current_frames().get(self._main_ident)
            stack = "".join(traceback.format_stack(frame, limit=12)) if frame is not None else "(sem pilha)\n"
            self.event(f"INTERFACE TRAVADA há {late * 1000:.0f} ms; a placa de som não recebe áudio enquanto isso. "
                       f"Pilha da thread principal:\n{stack.rstrip()}")
