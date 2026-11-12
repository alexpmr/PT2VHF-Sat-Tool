"""Indicação visual do rotor em tempo real.

v1.7.1: mini-bússola + arco de elevação.
v1.7.2: dois gauges separados — DIREÇÃO (azimute 0–360°, rosa dos ventos) e ELEVAÇÃO (0–90°) —
cada um com escala graduada, ponteiro da posição real (verde), alvo do satélite (amarelo tracejado)
e o valor numérico no próprio gauge. ``RotorCompass`` continua sendo o conjunto (mesma API).
"""
from __future__ import annotations

import math

from .qt_compat import Qt, QWidget

try:
    from PySide6.QtGui import QPainter, QColor, QPen, QFont
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtWidgets import QHBoxLayout
except ImportError:  # PySide2
    from PySide2.QtGui import QPainter, QColor, QPen, QFont
    from PySide2.QtCore import QPointF, QRectF
    from PySide2.QtWidgets import QHBoxLayout

REAL = QColor("#5af08a")
TARGET = QColor("#f5c542")
DIAL = QColor("#2c5d86")
FACE = QColor("#0d1d2e")
TICK = QColor("#6f93b5")
TEXT = QColor("#cfe6ff")

CARDINALS = (("N", 0), ("L", 90), ("S", 180), ("O", 270))


def _fmt(v) -> str:
    return "—" if v is None else f"{v:.0f}°"


def _pen(color, width, dashed=False):
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    if dashed:
        pen.setStyle(Qt.DashLine)
    return pen


class _Gauge(QWidget):
    """Base: guarda valor real/alvo e redesenha."""

    kind = ""

    def __init__(self, parent=None, size: int = 74):
        super().__init__(parent)
        self.real = None
        self.target = None
        self.flip = False

    def set_values(self, real=None, target=None, flip=False):
        self.real, self.target, self.flip = real, target, bool(flip)
        self.setAccessibleName(self.accessible_text())
        self.setToolTip(self.accessible_text() + "\nVerde: posição real · amarelo tracejado: alvo do satélite")
        self.update()

    def accessible_text(self) -> str:
        return f"{self.kind}: real {_fmt(self.real)} · alvo {_fmt(self.target)}"

    def _font(self, p, px, bold=True):
        f = QFont(); f.setPixelSize(max(7, int(px))); f.setBold(bold); p.setFont(f)

    @staticmethod
    def caption_height(size: int) -> int:
        return max(14, int(size * 0.24))

    def _caption(self, p, prefix, dial_h):
        """Valor numérico abaixo do mostrador (nunca coberto pelos ponteiros), em caixa escura p/ qualquer tema."""
        box = QRectF(0, dial_h + 1, self.width(), self.height() - dial_h - 1)
        p.setPen(Qt.NoPen); p.setBrush(FACE); p.drawRoundedRect(box, 3, 3)
        self._font(p, box.height() * 0.78)
        fm = p.fontMetrics()
        val = _fmt(self.real)
        pre = prefix + " "
        x = box.center().x() - (fm.horizontalAdvance(pre) + fm.horizontalAdvance(val)) / 2
        y = box.center().y() + (fm.ascent() - fm.descent()) / 2
        p.setPen(TEXT); p.drawText(QPointF(x, y), pre)
        p.setPen(REAL if self.real is not None else TEXT)
        p.drawText(QPointF(x + fm.horizontalAdvance(pre), y), val)


class AzimuthGauge(_Gauge):
    """Gauge de DIREÇÃO: mostrador circular 0–360° com rosa dos ventos e valor no centro."""

    kind = "Direção"

    def __init__(self, parent=None, size: int = 74):
        super().__init__(parent, size)
        self.setFixedSize(size, size + self.caption_height(size))
        self.setAccessibleName(self.accessible_text())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        s = self.width()
        c = QPointF(self.width() / 2, s / 2)
        r = s / 2 - 2
        p.setPen(_pen(DIAL, 2)); p.setBrush(FACE)
        p.drawEllipse(c, r, r)

        def at(ang, rad):
            a = math.radians(ang)
            return QPointF(c.x() + rad * math.sin(a), c.y() - rad * math.cos(a))

        for deg in range(0, 360, 10):  # escala: traço a cada 10°, maior a cada 30°
            major = deg % 30 == 0
            p.setPen(_pen(TICK, 1.6 if major else 1))
            p.drawLine(at(deg, r - 1), at(deg, r - (s * 0.09 if major else s * 0.045)))
        self._font(p, s / 9)
        fm = p.fontMetrics()
        for lab, ang in CARDINALS:
            pt = at(ang, r - s * 0.19)
            p.setPen(TEXT if lab != "N" else QColor("#ff8a7a"))
            p.drawText(QPointF(pt.x() - fm.horizontalAdvance(lab) / 2, pt.y() + fm.ascent() / 2 - 1), lab)

        if self.target is not None:
            p.setPen(_pen(TARGET, 2, dashed=True))
            p.drawLine(c, at(self.target, r - 3))
        if self.real is not None:
            p.setPen(_pen(REAL, 3))
            p.drawLine(at(self.real + 180, s * 0.08), at(self.real, r - 4))
        p.setPen(Qt.NoPen); p.setBrush(REAL if self.real is not None else TICK)
        p.drawEllipse(c, 3, 3)

        self._caption(p, "AZ", s)
        p.end()


class ElevationGauge(_Gauge):
    """Gauge de ELEVAÇÃO: quadrante 0° (horizonte) a 90° (zênite) com escala e valor."""

    kind = "Elevação"

    def __init__(self, parent=None, size: int = 74):
        super().__init__(parent, size)
        self.setFixedSize(int(size * 1.05), size + self.caption_height(size))
        self.setAccessibleName(self.accessible_text())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        H = self.width() / 1.05
        pad = 3
        r = H - 2 * pad - 2
        o = QPointF(pad + 1, H - pad - 1)  # centro do quadrante: canto inferior esquerdo

        def at(el, rad):
            a = math.radians(max(0.0, min(90.0, el)))
            return QPointF(o.x() + rad * math.cos(a), o.y() - rad * math.sin(a))

        p.setPen(_pen(DIAL, 2)); p.setBrush(FACE)
        p.drawPie(QRectF(o.x() - r, o.y() - r, 2 * r, 2 * r), 0, 90 * 16)
        self._font(p, H / 10, bold=False)
        fm = p.fontMetrics()
        for deg in range(0, 91, 5):  # traço a cada 5°, maior e numerado a cada 30°
            major = deg % 30 == 0
            p.setPen(_pen(TICK, 1.6 if major else 1))
            p.drawLine(at(deg, r - 1), at(deg, r - (H * 0.1 if major else H * 0.05)))
            if major and 0 < deg < 90:
                pt = at(deg, r - H * 0.2)
                lab = str(deg)
                p.setPen(TEXT)
                p.drawText(QPointF(pt.x() - fm.horizontalAdvance(lab) / 2, pt.y() + fm.ascent() / 2), lab)

        if self.target is not None:
            p.setPen(_pen(TARGET, 2, dashed=True))
            p.drawLine(o, at(self.target, r - 3))
        if self.real is not None:
            p.setPen(_pen(REAL, 3))
            p.drawLine(o, at(self.real, r - 4))
        p.setPen(Qt.NoPen); p.setBrush(REAL if self.real is not None else TICK)
        p.drawEllipse(o, 3, 3)

        self._caption(p, "EL", H)
        self._font(p, H / 9)
        if self.flip:
            p.setPen(TARGET)
            p.drawText(QPointF(self.width() - p.fontMetrics().horizontalAdvance("FLIP") - 3,
                               p.fontMetrics().ascent() + 1), "FLIP")
        p.end()


class RotorCompass(QWidget):
    """Conjunto dos dois gauges (direção à esquerda, elevação à direita), atualizados a cada leitura do rotor.

    ``real``/``target`` são tuplas (az, el) já convertidas para o apontamento real (sem sobreposição e sem flip).
    """

    def __init__(self, parent=None, size: int = 74):
        super().__init__(parent)
        self.real = None
        self.target = None
        self.flip = False
        self.az_gauge = AzimuthGauge(size=size)
        self.el_gauge = ElevationGauge(size=size)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(max(4, size // 12))
        lay.addWidget(self.az_gauge)
        lay.addWidget(self.el_gauge)
        self.setToolTip("Rotor em tempo real: direção (esquerda) e elevação (direita)\n"
                        "Verde: posição real · amarelo tracejado: alvo do satélite")
        self.setAccessibleName(self.accessible_text())

    def set_values(self, real=None, target=None, flip=False):
        self.real, self.target, self.flip = real, target, bool(flip)
        self.az_gauge.set_values(real[0] if real else None, target[0] if target else None, flip)
        self.el_gauge.set_values(real[1] if real else None, target[1] if target else None, flip)
        self.setAccessibleName(self.accessible_text())

    def accessible_text(self) -> str:
        def fmt(p):
            return f"AZ {p[0]:.0f}° EL {p[1]:.0f}°" if p else "—"
        return f"Rotor real {fmt(self.real)} · alvo {fmt(self.target)}" + (" · flip" if self.flip else "")

    @staticmethod
    def pointing(az: float, el: float) -> tuple:
        """Coordenadas do rotor (az até 450°, el até 180° no flip) → apontamento real (az 0–360, el 0–90)."""
        if el > 90:
            return ((az + 180.0) % 360.0, 180.0 - el)
        return (az % 360.0, el)
