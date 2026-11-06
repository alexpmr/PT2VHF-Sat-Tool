"""Display "LCD de rádio" âmbar de matriz de pontos (estilo Yaesu FT-891), v1.6.0.

Fonte bitmap 5×7 própria (sem dependências), pixels quadrados com grade levemente visível,
retroiluminação âmbar. Linha grande de RX, linha menor de TX, barra estilo S-meter e
indicadores invertidos. Só exibe dados: nunca envia comandos ao rádio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .qt_compat import Qt, QWidget

try:
    from PySide6.QtGui import QPainter, QColor, QLinearGradient, QFont
    from PySide6.QtCore import QRectF, Signal
except ImportError:  # PySide2
    from PySide2.QtGui import QPainter, QColor, QLinearGradient, QFont
    from PySide2.QtCore import QRectF, Signal

# 5×7: cada caractere = 7 linhas de 5 bits (bit 4 = coluna esquerda).
FONT = {
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E), "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F), "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02), "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E), "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E), "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11), "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E), "D": (0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F), "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F), "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E), "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11), "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11), "N": (0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E), "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D), "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E), "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E), "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A), "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x11, 0x0A, 0x04, 0x04, 0x04), "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    ".": (0, 0, 0, 0, 0, 0x0C, 0x0C), ":": (0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0),
    "-": (0, 0, 0, 0x1F, 0, 0, 0), "+": (0, 0x04, 0x04, 0x1F, 0x04, 0x04, 0),
    "/": (0, 0x01, 0x02, 0x04, 0x08, 0x10, 0), "%": (0x18, 0x19, 0x02, 0x04, 0x08, 0x13, 0x03),
    "°": (0x0C, 0x12, 0x12, 0x0C, 0, 0, 0), "<": (0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02),
    ">": (0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08), "=": (0, 0, 0x1F, 0, 0x1F, 0, 0),
    " ": (0, 0, 0, 0, 0, 0, 0), "?": (0x0E, 0x11, 0x01, 0x02, 0x04, 0, 0x04),
}
THEMES = {
    "âmbar": ("#ffc34d", "#e09a22", "#2b1802", "#d99a2e"),
    "verde": ("#b8f06a", "#7fc23a", "#13280a", "#86c24a"),
    "azul": ("#9ad8ff", "#5aa8e0", "#08182a", "#6aaee0"),
}


def text_width(text: str) -> int:
    """Largura em pixels lógicos (5 + 1 de espaço por caractere)."""
    return max(0, len(text) * 6 - 1)


def format_radio_hz(hz: int | None) -> tuple[str, str]:
    """435637710 → ("435.637.7", "1"): parte principal com 10 Hz e último dígito (1 Hz) menor."""
    if hz is None:
        return "---.---.-", "-"
    tens = int(round(hz / 10))
    mhz, rest = divmod(tens, 100_000)
    khz, sub = divmod(rest, 100)
    return f"{mhz}.{khz:03d}.{sub:02d}"[:-1], f"{sub % 10}"


@dataclass
class LcdState:
    rx_hz: int | None = None
    rx_mode: str = ""
    tx_hz: int | None = None
    tx_mode: str = ""
    rx_only: bool = False
    swapped: bool = False
    doppler_hz: int | None = None
    elevation: float | None = None
    visible: bool = False
    signal: int | None = None        # S-meter 0–30 (TS-2000 MAIN) quando houver CAT/SDR
    sat_on: bool = False
    link: str = ""                   # "CAT", "SDR", ""
    auto: bool = False
    transmitting: bool = False
    power_w: int | None = None
    swr: float | None = None
    extras: dict = field(default_factory=dict)


class LcdDisplay(QWidget):
    """Widget do display. set_state() atualiza; botões A/B (MAIN↔SUB) e RX ONLY emitem sinais."""
    swap_clicked = Signal()
    rx_only_clicked = Signal()

    def __init__(self, parent=None, theme: str = "âmbar"):
        super().__init__(parent)
        self.state = LcdState()
        self.theme = theme if theme in THEMES else "âmbar"
        self.setMinimumHeight(118)
        self.setMaximumHeight(170)
        self._keys = {}
        self.setMouseTracking(True)
        self.setToolTip("Clique em A/B para inverter MAIN↔SUB (TX/RX) · RX ONLY para operar só em recepção")

    def set_theme(self, theme: str):
        if theme in THEMES:
            self.theme = theme
            self.update()

    def set_state(self, **values):
        for key, value in values.items():
            setattr(self.state, key, value)
        self.setAccessibleName(self.accessible_text())
        self.update()

    def accessible_text(self) -> str:
        st = self.state
        rx = f"RX {st.rx_hz / 1e6:.5f} MHz {st.rx_mode}" if st.rx_hz else "RX —"
        tx = "somente recepção" if st.rx_only or not st.tx_hz else f"TX {st.tx_hz / 1e6:.5f} MHz {st.tx_mode}"
        return f"{rx} · {tx}"

    # ------------------------------------------------------------ desenho
    def _glyph(self, p, x, y, ch, px, on, off, grid=True):
        rows = FONT.get(ch.upper(), FONT["?"])
        for r, bits in enumerate(rows):
            for c in range(5):
                lit = bits & (1 << (4 - c))
                if lit or grid:
                    p.fillRect(QRectF(x + c * px, y + r * px, px * 0.86, px * 0.86), on if lit else off)

    def _text(self, p, x, y, text, px, on, off, grid=True):
        for i, ch in enumerate(text):
            self._glyph(p, x + i * 6 * px, y, ch, px, on, off, grid)
        return x + text_width(text) * px

    def _tag(self, p, x, y, text, px, on, bg):
        w = (text_width(text) + 4) * px
        h = 11 * px
        p.fillRect(QRectF(x, y, w, h), on)
        self._text(p, x + 2 * px, y + 2 * px, text, px, bg, on, grid=False)
        return x + w + 3 * px

    def paintEvent(self, event):
        light, dark, ink, faint = (QColor(c) for c in THEMES[self.theme])
        off = QColor(faint)
        off.setAlpha(70)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, light)
        g.setColorAt(1, dark)
        p.fillRect(self.rect(), g)
        st = self.state
        H, W = self.height(), self.width()
        big = max(2.0, min(H / 30.0, W / 140.0))
        small = max(1.2, big * 0.42)
        x0, y = 8.0, 6.0
        # Linha principal: RX
        x = self._tag(p, x0, y, ("SUB " if st.swapped else "") + "RX", small, ink, light)
        if st.rx_mode:
            self._text(p, x0, y + 12 * small, st.rx_mode[:4].upper(), small, ink, off, grid=False)
        x = max(x, x0 + 30 * small)
        main, last = format_radio_hz(st.rx_hz)
        x = self._text(p, x, y, main, big, ink, off)
        self._text(p, x + big, y + 2 * big, last, big * 0.72, ink, off)
        y += max(8.5 * big, 21 * small)
        # Linha secundária: TX ou RX ONLY
        if st.rx_only or not st.tx_hz:
            self._tag(p, x0, y, "RX ONLY", small, ink, light)
            self._text(p, x0 + 50 * small, y + 2 * small, "SOMENTE RECEPCAO", small, ink, off, grid=False)
        else:
            x = self._tag(p, x0, y, ("MAIN " if st.swapped else "") + "TX", small, ink, light)
            if st.tx_mode:
                x = self._text(p, x + 2 * small, y + 2 * small, st.tx_mode[:4].upper(), small, ink, off, grid=False)
            tmain, tlast = format_radio_hz(st.tx_hz)
            x = self._text(p, max(x + 6 * small, x0 + 30 * small), y, tmain + tlast, small * 1.6, ink, off)
        y += 13 * small
        # Barra estilo S-meter: sinal (CAT/SDR) ou elevação
        if st.signal is not None:
            label, value, scale = "S", max(0, min(30, st.signal)), 30
        else:
            el = st.elevation if st.elevation is not None else 0.0
            label, value, scale = "EL", max(0.0, min(90.0, el)), 90
        lx = self._text(p, x0, y, label, small, ink, off, grid=False) + 3 * small
        segs = 30
        seg_w = (W - lx - 70 * small) / segs
        for i in range(segs):
            lit = i < round(value / scale * segs)
            p.fillRect(QRectF(lx + i * seg_w, y + 2 * small, seg_w * 0.7, 5 * small), ink if lit else off)
        tail = (f"{st.elevation:+.0f}°" if st.elevation is not None else "") if st.signal is None else \
            (f"S{min(9, st.signal * 9 // 15)}" if st.signal <= 15 else f"+{(st.signal - 15) * 4}")
        self._text(p, lx + segs * seg_w + 3 * small, y, tail, small, ink, off, grid=False)
        y += 10 * small
        # Indicadores invertidos
        tags = []
        if st.doppler_hz is not None:
            tags.append(f"DOP {st.doppler_hz:+d}")
        tags.append("VIS" if st.visible else "ABX")
        if st.sat_on:
            tags.append("SAT")
        if st.link:
            tags.append(st.link)
        if st.auto:
            tags.append("AUTO")
        if st.swapped:
            tags.append("MAIN<>SUB")
        if st.transmitting:
            tags.append("TX ON")
        if st.power_w is not None:
            tags.append(f"PWR {st.power_w}W")
        if st.swr is not None:
            tags.append(f"SWR {st.swr:.1f}")
        ex = st.extras or {}
        if ex.get("preamp"):
            tags.append("PRE")
        if ex.get("attenuator"):
            tags.append("ATT")
        if ex.get("nb"):
            tags.append("NB")
        if ex.get("nr"):
            tags.append(f"NR{ex['nr']}")
        x = x0
        for tag in tags:
            if x + (text_width(tag) + 4) * small > W - 120 * small:
                break
            x = self._tag(p, x, y, tag, small, ink, light)
        # Teclas A/B e RX ONLY (estilo das teclas do painel)
        self._keys = {}
        kx = W - 116 * small
        for key, label in (("swap", "A/B"), ("rxonly", "RX ONLY")):
            w = (text_width(label) + 8) * small
            rect = QRectF(kx, y - small, w, 11 * small)
            p.fillRect(rect, ink)
            self._text(p, kx + 4 * small, y + small, label, small, light, ink, grid=False)
            self._keys[key] = rect
            kx += w + 4 * small
        p.end()

    def mousePressEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        for key, rect in self._keys.items():
            if rect.contains(pos):
                (self.swap_clicked if key == "swap" else self.rx_only_clicked).emit()
                return
        super().mousePressEvent(event)
