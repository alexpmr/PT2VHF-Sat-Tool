"""v1.8.0: medidor compacto de CPU e RAM do próprio programa, na barra do topo (como no PT2VHF APRS Client).

CPU: uso do processo em % da capacidade total da máquina (todas as CPUs). RAM: memória residente do processo
em MB; a barra mostra a fração da RAM física. Usa psutil quando disponível e, sem ele, a biblioteca padrão.
"""
from __future__ import annotations

import os
import sys
import time

from .qt_compat import Qt, QTimer, QWidget

try:
    from PySide6.QtGui import QPainter, QColor, QFont
    from PySide6.QtCore import QRectF
except ImportError:  # PySide2
    from PySide2.QtGui import QPainter, QColor, QFont
    from PySide2.QtCore import QRectF

try:
    import psutil
except Exception:  # pragma: no cover - sem psutil, usa a biblioteca padrão
    psutil = None


class ProcessUsage:
    """Amostra o uso de CPU (% de todas as CPUs) e a memória residente (bytes) deste processo."""

    def __init__(self):
        self.cpus = os.cpu_count() or 1
        self.proc = psutil.Process() if psutil else None
        if self.proc is not None:
            self.proc.cpu_percent(None)   # primeira chamada só zera a referência
        self._last = (time.monotonic(), time.process_time())

    def cpu_percent(self) -> float:
        if self.proc is not None:
            return max(0.0, min(100.0, self.proc.cpu_percent(None) / self.cpus))
        now, cpu = time.monotonic(), time.process_time()
        wall, used = now - self._last[0], cpu - self._last[1]
        self._last = (now, cpu)
        return max(0.0, min(100.0, used / wall * 100.0 / self.cpus)) if wall > 0 else 0.0

    def rss_bytes(self) -> int:
        if self.proc is not None:
            return int(self.proc.memory_info().rss)
        if sys.platform.startswith("linux"):
            try:
                with open("/proc/self/statm") as fh:
                    return int(fh.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            except (OSError, ValueError):
                return 0
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                return int(pmc.WorkingSetSize)
            return 0
        import resource   # macOS: pico (ru_maxrss em bytes)
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

    @staticmethod
    def total_bytes() -> int:
        if psutil:
            return int(psutil.virtual_memory().total)
        try:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError, AttributeError):
            return 0


class ResourceMeter(QWidget):
    """Bloco "CPU x,x% / RAM nnn MB", cada linha com uma barrinha verde (âmbar/vermelha quando alto)."""

    BG = QColor("#0d1d2e")
    BORDER = QColor("#2c5d86")
    LABEL = QColor("#9fb8d0")
    VALUE = QColor("#e8f3ff")
    TRACK = QColor("#1c3049")

    def __init__(self, parent=None, interval_ms: int = 2000):
        super().__init__(parent)
        self.usage = ProcessUsage()
        self.total = self.usage.total_bytes()
        self.cpu = 0.0
        self.rss = 0
        self.setFixedWidth(118)
        self.setToolTip("Uso de CPU e memória do PT2VHF Sat Tool")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sample)
        self.timer.start(interval_ms)
        self.sample()

    def sample(self):
        self.cpu = self.usage.cpu_percent()
        self.rss = self.usage.rss_bytes()
        self.setAccessibleName(self.text())
        self.update()

    def text(self) -> str:
        return f"CPU {self.cpu:.1f}% · RAM {self.rss / 1048576:.0f} MB"

    @staticmethod
    def _color(frac):
        return QColor("#3fd18e") if frac < 0.6 else (QColor("#e0aa55") if frac < 0.85 else QColor("#e06666"))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        p.setPen(self.BORDER); p.setBrush(self.BG)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 5, 5)
        rows = (("CPU", f"{self.cpu:.1f}%", self.cpu / 100.0),
                ("RAM", f"{self.rss / 1048576:.0f} MB", self.rss / self.total if self.total else 0.0))
        pad, line = 6, (h - 4) / 2
        font = QFont(); font.setPixelSize(max(8, int(line * 0.52))); font.setBold(True); p.setFont(font)
        fm = p.fontMetrics()
        for i, (lab, val, frac) in enumerate(rows):
            top = 2 + i * line
            base = top + fm.ascent() + 1
            p.setPen(self.LABEL); p.drawText(int(pad), int(base), lab)
            p.setPen(self.VALUE); p.drawText(int(w - pad - fm.horizontalAdvance(val)), int(base), val)
            bar_y = top + line - 4
            p.setPen(Qt.NoPen); p.setBrush(self.TRACK)
            p.drawRoundedRect(QRectF(pad, bar_y, w - 2 * pad, 2.5), 1, 1)
            p.setBrush(self._color(frac))
            p.drawRoundedRect(QRectF(pad, bar_y, max(2.5, (w - 2 * pad) * max(0.0, min(1.0, frac))), 2.5), 1, 1)
        p.end()
