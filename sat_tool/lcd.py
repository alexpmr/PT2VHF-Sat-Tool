"""Display de rádio do Sat Tool (v1.6.0, modelos selecionáveis na v1.7.0).

Modelos (Configurações → Apresentação → Tipo de display), todos com o layout do TS-2000
(MAIN e SUB lado a lado) exceto o Clássico da v1.6.0:
- "matriz": matriz de pontos âmbar (fonte 5×7 Normal ou Negrito 6×7), temas âmbar/verde/azul;
- "led7": LED de 7 segmentos âmbar; "lcd7": LCD de 7 segmentos âmbar (visual do TS-2000);
- "digital": tela colorida (TFT); "classico": RX em cima / TX embaixo (v1.6.0).

Tudo é desenhado numa imagem do tamanho físico da tela (pixels reais × devicePixelRatio): os pontos
da matriz caem sempre em pixels inteiros, sem os "pixels defeituosos" de posições fracionárias.
Só exibe dados: nunca envia comandos ao rádio (A/B e RX ONLY apenas emitem sinais).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .qt_compat import Qt, QWidget

import time

try:
    from PySide6.QtGui import (QPainter, QColor, QLinearGradient, QFont, QFontMetricsF, QImage, QPen,
                               QPolygonF, QTransform)
    from PySide6.QtCore import QRectF, QPointF, Signal
except ImportError:  # PySide2
    from PySide2.QtGui import (QPainter, QColor, QLinearGradient, QFont, QFontMetricsF, QImage, QPen,
                               QPolygonF, QTransform)
    from PySide2.QtCore import QRectF, QPointF, Signal

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




MODELS = {
    "matriz": "Matriz de pontos âmbar",
    "led7": "LED de 7 segmentos âmbar",
    "lcd7": "LCD de 7 segmentos âmbar",
    "digital": "Digital (tela colorida)",
    "classico": "Clássico v1.6.0 (RX em cima, TX embaixo)",
}
FONTS = {"normal": "Normal", "negrito": "Negrito"}
SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc",
       "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g", " ": ""}


def countdown_text(seconds: float | None) -> str:
    """Contagem curta para o display: 5:42, 0:28, 1H05 (acima de 1 h)."""
    if seconds is None:
        return ""
    s = max(0, int(seconds))
    if s >= 3600:
        return f"{s // 3600}H{(s % 3600) // 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


def smeter_text(signal: int) -> str:
    """TS-2000: 0–15 = S0–S9; acima, +dB em passos de ~4 dB."""
    return f"S{min(9, signal * 9 // 15)}" if signal <= 15 else f"S9+{(signal - 15) * 4}"


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
    signal: int | None = None        # S-meter 0–30 (TS-2000) quando houver CAT/SDR
    sat_on: bool = False
    link: str = ""                   # "CAT", "SDR", ""
    auto: bool = False
    transmitting: bool = False
    power_w: int | None = None
    swr: float | None = None
    extras: dict = field(default_factory=dict)
    los_s: float | None = None       # v1.7.0: segundos até o LOS (só durante a passagem em curso)
    aos_s: float | None = None       # v1.7.0: segundos até o próximo AOS (só fora da passagem)
    rotor: str = ""                  # v1.7.0: "AZ 123 EL 45" quando houver rotor


def indicator_tags(st: LcdState) -> list[tuple[str, bool]]:
    """Indicadores da linha de baixo: (texto, destaque/pisca)."""
    tags = []
    # contagem primeiro: é o indicador que não pode sumir quando falta largura
    if st.los_s is not None:
        tags.append(("LOS " + countdown_text(st.los_s), st.los_s <= 30))
    elif st.aos_s is not None:
        tags.append(("AOS " + countdown_text(st.aos_s), False))
    if st.sat_on:
        tags.append(("SAT", False))
    if st.link:
        tags.append((st.link, False))
    if st.auto:
        tags.append(("AUTO", False))
    if st.swapped:
        tags.append(("MAIN<>SUB", False))
    if st.doppler_hz is not None and not st.swapped:
        tags.append((f"DOP {st.doppler_hz / 1000:+.1f}k", False))
    tags.append(("VIS" if st.visible else "ABX", False))
    if st.elevation is not None and st.visible:
        tags.append((f"EL {st.elevation:+.0f}°", False))
    if st.rotor:
        tags.append((st.rotor, False))
    ex = st.extras or {}
    for key, text in (("preamp", "PRE"), ("attenuator", "ATT"), ("nb", "NB")):
        if ex.get(key):
            tags.append((text, False))
    if ex.get("nr"):
        tags.append((f"NR{ex['nr']}", False))
    return tags


def sides(st: LcdState) -> list[dict]:
    """Lados MAIN (esquerda) e SUB (direita), como no TS-2000."""
    main = {"name": "MAIN", "role": "RX", "hz": st.rx_hz, "mode": st.rx_mode}
    sub = {"name": "SUB", "role": "TX", "hz": st.tx_hz, "mode": st.tx_mode}
    if st.swapped:
        main.update(role="TX", hz=st.tx_hz, mode=st.tx_mode)
        sub.update(role="RX", hz=st.rx_hz, mode=st.rx_mode)
    for side in (main, sub):
        side["off"] = side["role"] == "TX" and (st.rx_only or not st.tx_hz)
    return [main, sub]


def freq_parts(hz: int | None) -> tuple[str, str]:
    return format_radio_hz(hz)


# ---------------------------------------------------------------- estilos de desenho (pixels físicos)
class _Style:
    """Primitivas comuns. Coordenadas em pixels físicos; u = escala (1 unidade de projeto)."""
    radius = 2.0

    def __init__(self, p: QPainter, w: int, h: int, u: float, theme: str):
        self.p, self.w, self.h, self.u = p, w, h, u
        self.theme = theme

    # textos pequenos (fonte do sistema)
    def font(self, px: float, bold: bool = True) -> QFont:
        f = QFont()
        try:
            f.setFamilies(["DejaVu Sans", "Segoe UI", "Helvetica Neue", "Arial"])
        except AttributeError:
            f.setFamily("Arial")
        f.setPixelSize(max(6, int(round(px))))
        f.setBold(bold)
        f.setStretch(88)
        return f

    def text_w(self, s: str, px: float) -> float:
        return QFontMetricsF(self.font(px)).horizontalAdvance(s)

    def label(self, x, y, s, px=None, color=None):
        px = px or 13 * self.u
        self.p.setFont(self.font(px))
        self.p.setPen(color or self.ink)
        self.p.drawText(QPointF(x, y + px * 0.95), s)
        return x + self.text_w(s, px)

    def tag_w(self, s):
        return self.text_w(s, 12 * self.u) + 10 * self.u

    def tag(self, x, y, s, bg=None, fg=None, blink=False):
        if blink and int(time.monotonic() * 2) % 2:
            bg, fg = fg or self.tag_fg, bg or self.tag_bg
        w = self.tag_w(s)
        self.p.setPen(QColor(0, 0, 0, 0))
        self.p.setBrush(bg or self.tag_bg)
        self.p.drawRoundedRect(QRectF(x, y, w, 19 * self.u), self.radius * self.u, self.radius * self.u)
        self.label(x + 5 * self.u, y + 2.5 * self.u, s, 12 * self.u, fg or self.tag_fg)
        return x + w + 6 * self.u

    def key_w(self, s):
        return self.text_w(s, 12 * self.u) + 18 * self.u

    def key(self, x, y, s):
        w = self.key_w(s)
        r = QRectF(x, y - 2 * self.u, w, 21 * self.u)
        self.p.setPen(QPen(self.ink, max(1.0, 1.2 * self.u)))
        self.p.setBrush(QColor(0, 0, 0, 0))
        self.p.drawRoundedRect(r, 3 * self.u, 3 * self.u)
        self.label(x + 9 * self.u, y + 1.5 * self.u, s, 12 * self.u)
        return r

    def bar(self, x, y, frac, n, seg, hh):
        self.p.setPen(QColor(0, 0, 0, 0))
        lit_n = round(max(0.0, min(1.0, frac)) * n)
        for i in range(n):
            self.p.setBrush(self.bar_color(i, n) if i < lit_n else self.off)
            self.p.drawRect(QRectF(x + i * seg, y, seg - 2 * self.u, hh))
        return x + n * seg

    def bar_color(self, i, n):
        return self.ink

    def separator(self, x):
        self.p.fillRect(QRectF(x, 10 * self.u, max(1.0, 1.5 * self.u), self.h - 50 * self.u), self.off)

    # números grandes: implementados por cada estilo
    def digits_w(self, s, size):
        raise NotImplementedError

    def digits(self, x, y, s, size):
        raise NotImplementedError


class _Matrix(_Style):
    """Matriz de pontos (fonte 5×7 Normal ou 6×7 Negrito), pontos sempre em pixels inteiros."""
    radius = 0.0

    def __init__(self, p, w, h, u, theme, bold=False):
        super().__init__(p, w, h, u, theme)
        light, dark, ink, faint = (QColor(c) for c in THEMES.get(theme, THEMES["âmbar"]))
        self.light, self.dark, self.ink = light, dark, ink
        self.off = QColor(faint)
        self.off.setAlpha(38)
        self.tag_bg, self.tag_fg = ink, light
        self.bold = bold
        self.small = max(2, int(round(2 * u)))  # pitch dos textos pequenos

    def background(self):
        g = QLinearGradient(0, 0, 0, self.h)
        g.setColorAt(0, self.light)
        g.setColorAt(1, self.dark)
        self.p.fillRect(QRectF(0, 0, self.w, self.h), g)

    def glyph(self, x, y, ch, pitch, on, grid, bold):
        x, y = int(round(x)), int(round(y))
        cols = 6 if bold else 5
        dot = pitch - max(1, pitch // 10) if pitch >= 4 else pitch
        for r, bits in enumerate(FONT.get(ch.upper(), FONT["?"])):
            if bold:
                bits = (bits << 1) | bits
            for c in range(cols):
                lit = bits & (1 << (cols - 1 - c))
                if lit or grid:
                    self.p.fillRect(x + c * pitch, y + r * pitch, dot, dot, on if lit else self.off)

    def mtext(self, x, y, s, pitch, on=None, grid=False, bold=False):
        adv = 7 if bold else 6
        for i, ch in enumerate(s):
            self.glyph(x + i * adv * pitch, y, ch, pitch, on or self.ink, grid, bold)
        return x + (len(s) * adv - 1) * pitch

    def label(self, x, y, s, px=None, color=None):
        return self.mtext(x, y + self.small, s, self.small, color)

    def text_w(self, s, px):
        return (len(s) * 6 - 1) * self.small

    def tag(self, x, y, s, bg=None, fg=None, blink=False):
        if blink and int(time.monotonic() * 2) % 2:
            bg, fg = fg or self.tag_fg, bg or self.tag_bg
        sp = self.small
        w = (len(s) * 6 - 1 + 4) * sp
        x, y = int(round(x)), int(round(y))
        self.p.fillRect(x, y, w, 11 * sp, bg or self.tag_bg)
        self.mtext(x + 2 * sp, y + 2 * sp, s, sp, fg or self.tag_fg)
        return x + w + 3 * sp

    def tag_w(self, s):
        return (len(s) * 6 - 1 + 4) * self.small + 3 * self.small

    def key_w(self, s):
        return (len(s) * 6 - 1 + 8) * self.small

    def key(self, x, y, s):
        sp = self.small
        w = self.key_w(s)
        x, y = int(round(x)), int(round(y))
        self.p.fillRect(x, y - sp, w, 11 * sp + 2 * sp, self.ink)
        self.mtext(x + 4 * sp, y + sp, s, sp, self.light)
        return QRectF(x, y - sp, w, 13 * sp)

    def bar(self, x, y, frac, n, seg, hh):
        x, y, seg, hh = int(round(x)), int(round(y)), max(3, int(round(seg))), max(2, int(round(hh)))
        lit_n = round(max(0.0, min(1.0, frac)) * n)
        for i in range(n):
            self.p.fillRect(x + i * seg, y, seg - 2, hh, self.ink if i < lit_n else self.off)
        return x + n * seg

    def digits_w(self, s, pitch):
        adv = 7 if self.bold else 6
        return (len(s) * adv - 1) * pitch

    def digits(self, x, y, s, pitch):
        return self.mtext(x, y, s, pitch, grid=True, bold=self.bold)


def _seg_polys(x, y, w, h, t):
    g = t * 0.18
    m = h / 2

    def hor(cx0, cx1, cy):
        return QPolygonF([QPointF(cx0 + g, cy), QPointF(cx0 + t / 2 + g, cy - t / 2),
                          QPointF(cx1 - t / 2 - g, cy - t / 2), QPointF(cx1 - g, cy),
                          QPointF(cx1 - t / 2 - g, cy + t / 2), QPointF(cx0 + t / 2 + g, cy + t / 2)])

    def ver(cx, cy0, cy1):
        return QPolygonF([QPointF(cx, cy0 + g), QPointF(cx + t / 2, cy0 + t / 2 + g),
                          QPointF(cx + t / 2, cy1 - t / 2 - g), QPointF(cx, cy1 - g),
                          QPointF(cx - t / 2, cy1 - t / 2 - g), QPointF(cx - t / 2, cy0 + t / 2 + g)])
    x0, x1 = x + t / 2, x + w - t / 2
    y0, y1, y2 = y + t / 2, y + m, y + h - t / 2
    return {"a": hor(x0, x1, y0), "g": hor(x0, x1, y1), "d": hor(x0, x1, y2),
            "f": ver(x0, y0, y1), "b": ver(x1, y0, y1), "e": ver(x0, y1, y2), "c": ver(x1, y1, y2)}


class _Seven(_Style):
    """7 segmentos vetoriais (nítidos em qualquer DPI). LED: aceso com brilho; LCD: escuro sobre âmbar."""

    def __init__(self, p, w, h, u, theme, led=True):
        super().__init__(p, w, h, u, theme)
        self.led = led
        light, dark, ink, faint = (QColor(c) for c in THEMES.get(theme, THEMES["âmbar"]))
        if led:
            self.ink = QColor(light)
            self.off = QColor(light); self.off.setAlpha(22)
            self.glow = QColor(light); self.glow.setAlpha(55)
            self.tag_bg = QColor(light); self.tag_bg.setAlpha(40)
            self.tag_fg = QColor(light)
        else:
            self.light, self.dark = light, dark
            self.ink = QColor(ink)
            self.off = QColor(ink); self.off.setAlpha(26)
            self.glow = None
            self.tag_bg, self.tag_fg = QColor(ink), QColor(light)

    def background(self):
        g = QLinearGradient(0, 0, 0, self.h)
        if self.led:
            g.setColorAt(0, QColor("#1a1006")); g.setColorAt(1, QColor("#0b0602"))
            self.p.fillRect(QRectF(0, 0, self.w, self.h), g)
            r = QLinearGradient(0, 0, 0, self.h * 0.4)
            r.setColorAt(0, QColor(255, 255, 255, 14)); r.setColorAt(1, QColor(255, 255, 255, 0))
            self.p.fillRect(QRectF(0, 0, self.w, self.h * 0.4), r)
        else:
            g.setColorAt(0, self.light); g.setColorAt(1, self.dark)
            self.p.fillRect(QRectF(0, 0, self.w, self.h), g)

    @staticmethod
    def _metrics(h):
        w, gap = h * 0.5, h * 0.3
        return w, h * 0.12, gap

    def digits_w(self, s, h):
        w, t, gap = self._metrics(h)
        n = sum(1 for ch in s if ch != ".")
        return n * (w + gap) - gap

    def _seven(self, x, y, s, h, on, off, glow):
        w, t, gap = self._metrics(h)
        p = self.p
        p.save()
        p.setTransform(QTransform().translate(x, y + h).shear(-0.08, 0).translate(-x, -(y + h)), True)
        p.setPen(QColor(0, 0, 0, 0))
        cx = x
        for ch in s:
            if ch == ".":
                r = QRectF(cx - gap / 2 - t / 2, y + h - t, t, t)
                p.setBrush(on)
                p.drawRect(r)
                continue
            lit = SEG.get(ch, "")
            for name, poly in _seg_polys(cx, y, w, h, t).items():
                if name in lit and glow is not None:
                    p.setPen(QPen(glow, t * 0.6))
                    p.setBrush(QColor(0, 0, 0, 0))
                    p.drawPolygon(poly)
                    p.setPen(QColor(0, 0, 0, 0))
                p.setBrush(on if name in lit else off)
                p.drawPolygon(poly)
            cx += w + gap
        p.restore()
        return cx - gap

    def digits(self, x, y, s, h):
        if not self.led:
            self._seven(x + 1.2 * self.u, y + 1.2 * self.u, s, h, QColor(90, 50, 0, 40), QColor(0, 0, 0, 0), None)
        return self._seven(x, y, s, h, self.ink, self.off, self.glow)


class _Digital(_Style):
    radius = 4.0

    def __init__(self, p, w, h, u, theme):
        super().__init__(p, w, h, u, theme)
        self.ink = QColor("#f2f5f8")
        self.off = QColor(255, 255, 255, 22)
        self.tag_bg, self.tag_fg = QColor("#1f3f66"), QColor("#cfe6ff")
        self.dim = QColor(255, 255, 255, 110)

    def background(self):
        g = QLinearGradient(0, 0, 0, self.h)
        g.setColorAt(0, QColor("#0d1a2b")); g.setColorAt(1, QColor("#050b14"))
        self.p.fillRect(QRectF(0, 0, self.w, self.h), g)

    def dfont(self, h):
        f = QFont()
        try:
            f.setFamilies(["DejaVu Sans Mono", "Consolas", "Menlo", "Courier New"])
        except AttributeError:
            f.setFamily("Courier New")
        f.setPixelSize(max(8, int(h * 1.32)))
        f.setBold(True)
        return f

    def digits_w(self, s, h):
        return QFontMetricsF(self.dfont(h)).horizontalAdvance(s)

    def digits(self, x, y, s, h):
        self.p.setFont(self.dfont(h))
        self.p.setPen(self.ink)
        self.p.drawText(QPointF(x - 2 * self.u, y + h), s)
        return x + self.digits_w(s, h) - 2 * self.u

    def bar_color(self, i, n):
        return QColor("#39d353") if i < n * 0.6 else (QColor("#f5c542") if i < n * 0.8 else QColor("#ff5a4f"))


def make_style(model, p, w, h, u, theme, font):
    if model == "led7":
        return _Seven(p, w, h, u, theme, led=True)
    if model == "lcd7":
        return _Seven(p, w, h, u, theme, led=False)
    if model == "digital":
        return _Digital(p, w, h, u, theme)
    return _Matrix(p, w, h, u, theme, bold=(font == "negrito"))


def paint_ts2000(style: _Style, st: LcdState) -> dict:
    """Layout TS-2000 (MAIN | SUB). Retorna os retângulos das teclas (pixels físicos)."""
    u, W, H = style.u, style.w, style.h
    style.background()
    half = W / 2
    digital = isinstance(style, _Digital)
    matrix = isinstance(style, _Matrix)
    margin = 12 * u
    avail = half - 2 * margin - 4 * u
    # tamanho dos dígitos: o maior que caiba na metade (frequência + dígito de 1 Hz menor)
    if matrix:
        size = max(2, int(round(5 * u)))
        while size > 2 and style.digits_w("436.795.1", size) + 6 * size > avail:
            size -= 1
        small_size = max(2, size - 1)
        dig_h = 7 * size
    else:
        size = 44 * u if digital else 40 * u
        while size > 14 * u and (style.digits_w("436.795.1", size) + style.digits_w("2", size * 0.68)
                                 + 0.4 * size + (40 * u if digital else 0)) > avail:
            size -= 1 * u
        small_size = size * 0.68
        dig_h = size
    for side, x0 in zip(sides(st), (margin, half + margin)):
        y = 8 * u
        rc = QColor("#2fbf4a") if digital and side["role"] == "RX" else None
        tc = QColor("#d8443a") if digital and side["role"] == "TX" else None
        x = style.tag(x0, y, side["name"])
        x = style.tag(x, y, "TX OFF" if side["off"] else side["role"], bg=rc or tc)
        if side["mode"]:
            style.label(x, y + 2 * u, side["mode"][:4].upper())
        if side["role"] == "TX" and st.transmitting and not side["off"]:
            style.tag(x0 + avail - style.tag_w("ON AIR"), y, "ON AIR", bg=QColor("#d8443a") if digital else None)
        main_s, last = freq_parts(None if side["off"] else side["hz"])
        dy = y + 28 * u
        if matrix:
            dy = int(round(dy))
            xe = style.digits(x0, dy, main_s, size)
            style.digits(xe + size, dy + (7 * size - 7 * small_size), last, small_size)
        else:
            dy2 = dy + (44 * u - dig_h)
            xe = style.digits(x0, dy2, main_s, size)
            gap = (0.3 * size + 0.08 * size) if not digital else 2 * u   # inclinação dos segmentos
            xs = style.digits(xe + gap, dy2 + dig_h - small_size, last, small_size)
            if digital and xs + style.text_w("MHz", 11 * u) + 8 * u < x0 + avail:
                style.label(xs + 6 * u, dy2 + dig_h - 12 * u, "MHz",
                            11 * u, QColor(255, 255, 255, 110))
        y = dy + max(dig_h, 44 * u) + 8 * u
        seg = 9 * u if avail > 300 * u else 7 * u
        n = 22 if avail > 300 * u else 14
        if side["role"] == "RX":
            lx = style.label(x0, y - 3 * u, "S") + 6 * u
            if st.signal is not None:
                ex = style.bar(lx, y, st.signal / 30, n, seg, 9 * u)
                style.label(ex + 6 * u, y - 3 * u, smeter_text(int(st.signal)))
            else:  # sem medidor: elevação do satélite
                el = st.elevation if st.elevation is not None else 0.0
                ex = style.bar(lx, y, max(0.0, el) / 90, n, seg, 9 * u)
                style.label(ex + 6 * u, y - 3 * u, f"EL {el:+.0f}°" if st.elevation is not None else "")
        elif not side["off"]:
            lx = style.label(x0, y - 3 * u, "PO") + 6 * u
            pw = st.power_w or 0
            ex = style.bar(lx, y, pw / 100, n, seg, 9 * u)
            txt = (f"{pw}W" if st.power_w is not None else "") + (f"  SWR {st.swr:.1f}" if st.swr is not None else "")
            style.label(ex + 6 * u, y - 3 * u, txt.strip())
    style.separator(half - 1)
    # indicadores + teclas
    y = H - 27 * u
    keys = {}
    kx = W - margin
    for key, lab in (("rxonly", "RX ONLY"), ("swap", "A/B")):
        kx -= style.key_w(lab)
        keys[key] = style.key(kx, y, lab)
        kx -= 8 * u
    x = margin
    for text, blink in indicator_tags(st):
        if x + style.tag_w(text) > kx:
            break
        x = style.tag(x, y, text, blink=blink)
    return keys


def paint_classic(style: _Matrix, st: LcdState) -> dict:
    """Layout da v1.6.0 (RX grande em cima, TX embaixo), agora com pontos em grade inteira."""
    u, W, H = style.u, style.w, style.h
    style.background()
    sp = style.small
    big = max(2, int(round(min(H / 30.0, W / 140.0))))
    x0, y = int(round(8 * u)), int(round(6 * u))
    x = style.tag(x0, y, ("SUB " if st.swapped else "") + "RX")
    if st.rx_mode:
        style.mtext(x0, y + 12 * sp, st.rx_mode[:4].upper(), sp)
    x = max(x, x0 + 30 * sp)
    main, last = format_radio_hz(st.rx_hz)
    x = style.mtext(x, y, main, big, grid=True)
    style.mtext(x + big, y + 2 * big, last, max(2, big - 1), grid=True)
    y += max(int(8.5 * big), 21 * sp)
    if st.rx_only or not st.tx_hz:
        style.tag(x0, y, "RX ONLY")
        style.mtext(x0 + 50 * sp, y + 2 * sp, "SOMENTE RECEPCAO", sp)
    else:
        x = style.tag(x0, y, ("MAIN " if st.swapped else "") + "TX")
        if st.tx_mode:
            x = style.mtext(x + 2 * sp, y + 2 * sp, st.tx_mode[:4].upper(), sp)
        tmain, tlast = format_radio_hz(st.tx_hz)
        style.mtext(max(x + 6 * sp, x0 + 30 * sp), y, tmain + tlast, max(2, int(round(sp * 1.6))), grid=True)
    y += 13 * sp
    if st.signal is not None:
        lab, value, scale = "S", max(0, min(30, st.signal)), 30
    else:
        el = st.elevation if st.elevation is not None else 0.0
        lab, value, scale = "EL", max(0.0, min(90.0, el)), 90
    lx = style.mtext(x0, y, lab, sp) + 3 * sp
    style.bar(lx, y + 2 * sp, value / scale, 30, (W - lx - 80 * sp) / 30, 5 * sp)
    y += 10 * sp
    keys = {}
    kx = W - 8 * u
    for key, lab in (("rxonly", "RX ONLY"), ("swap", "A/B")):
        w = (len(lab) * 6 - 1 + 8) * sp
        kx -= w
        keys[key] = style.key(kx, y, lab)
        kx -= 4 * sp
    x = x0
    for text, blink in indicator_tags(st):
        if x + style.tag_w(text) > kx:
            break
        x = style.tag(x, y, text, blink=blink)
    return keys


class LcdDisplay(QWidget):
    """Widget do display. set_state() atualiza; teclas A/B (MAIN↔SUB) e RX ONLY emitem sinais."""
    swap_clicked = Signal()
    rx_only_clicked = Signal()

    def __init__(self, parent=None, theme: str = "âmbar", model: str = "matriz", font: str = "normal"):
        super().__init__(parent)
        self.state = LcdState()
        self.theme = theme if theme in THEMES else "âmbar"
        self.model = model if model in MODELS else "matriz"
        self.font_style = font if font in FONTS else "normal"
        self.setMinimumHeight(118)
        self.setMaximumHeight(170)
        self._keys = {}
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)
        self.setToolTip("Clique em A/B para inverter MAIN↔SUB (TX/RX) · RX ONLY para operar só em recepção")

    def set_theme(self, theme: str):
        if theme in THEMES:
            self.theme = theme
            self.update()

    def set_model(self, model: str):
        if model in MODELS:
            self.model = model
            self.update()

    def set_font_style(self, font: str):
        if font in FONTS:
            self.font_style = font
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
        extra = ""
        if st.los_s is not None:
            extra = " · LOS em " + countdown_text(st.los_s)
        return f"{rx} · {tx}{extra}"

    def render_image(self, width: int, height: int, dpr: float = 1.0) -> tuple[QImage, dict]:
        """Desenha o display em pixels físicos (usado pelo paintEvent, testes e prévia das Configurações)."""
        pw, ph = max(1, int(round(width * dpr))), max(1, int(round(height * dpr)))
        img = QImage(pw, ph, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor("#000000"))
        p = QPainter(img)
        aa = self.model in ("led7", "lcd7", "digital")
        p.setRenderHint(QPainter.Antialiasing, aa)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        u = ph / 132.0
        style = make_style("matriz" if self.model == "classico" else self.model, p, pw, ph, u, self.theme,
                           "normal" if self.model == "classico" else self.font_style)
        keys = paint_classic(style, self.state) if self.model == "classico" else paint_ts2000(style, self.state)
        p.end()
        img.setDevicePixelRatio(dpr)
        return img, {k: QRectF(r.x() / dpr, r.y() / dpr, r.width() / dpr, r.height() / dpr) for k, r in keys.items()}

    def paintEvent(self, event):
        dpr = float(self.devicePixelRatioF()) if hasattr(self, "devicePixelRatioF") else 1.0
        img, self._keys = self.render_image(self.width(), self.height(), dpr)
        p = QPainter(self)
        p.drawImage(0, 0, img)
        p.end()

    def key_at(self, pos) -> str | None:
        for key, rect in self._keys.items():
            if rect.adjusted(-4, -4, 4, 4).contains(pos):
                return key
        return None

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        self.setCursor(Qt.PointingHandCursor if self.key_at(pos) else Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        key = self.key_at(pos)
        if key:
            (self.swap_clicked if key == "swap" else self.rx_only_clicked).emit()
            event.accept()
            return
        super().mousePressEvent(event)
