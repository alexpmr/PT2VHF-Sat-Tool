"""v1.7.1: mini-bússola (azimute real × alvo, indicador de flip) e arco de elevação do rotor."""
from __future__ import annotations

import math

from .qt_compat import Qt, QWidget

try:
    from PySide6.QtGui import QPainter, QColor, QPen, QFont
    from PySide6.QtCore import QPointF, QRectF
except ImportError:  # PySide2
    from PySide2.QtGui import QPainter, QColor, QPen, QFont
    from PySide2.QtCore import QPointF, QRectF

REAL = QColor("#5af08a")
TARGET = QColor("#f5c542")
DIAL = QColor("#2c5d86")
TEXT = QColor("#cfe6ff")


class RotorCompass(QWidget):
    """Bússola (esquerda) + arco de elevação 0–90° (direita). Posição real verde, alvo amarelo tracejado."""

    def __init__(self, parent=None, size: int = 74):
        super().__init__(parent)
        self.real = None      # (az, el) já sem a sobreposição (0–360) e sem flip
        self.target = None
        self.flip = False
        self.setFixedSize(int(size * 2.25), size)
        self.setToolTip("Rotor: posição real (verde) × alvo do satélite (amarelo)")

    def set_values(self, real=None, target=None, flip=False):
        self.real, self.target, self.flip = real, target, bool(flip)
        self.setAccessibleName(self.accessible_text())
        self.update()

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

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        h = self.height()
        r = h / 2 - 4
        c = QPointF(h / 2, h / 2)
        p.setPen(QPen(DIAL, 2)); p.setBrush(QColor("#0d1d2e"))
        p.drawEllipse(c, r, r)
        f = QFont(); f.setPixelSize(max(8, int(h / 7))); f.setBold(True); p.setFont(f)
        p.setPen(TEXT)
        for lab, ang in (("N", 0), ("L", 90), ("S", 180), ("O", 270)):
            a = math.radians(ang)
            pt = QPointF(c.x() + (r - 9) * math.sin(a) - 4, c.y() - (r - 9) * math.cos(a) + 4)
            p.drawText(pt, lab)

        def needle(az, color, dashed=False):
            a = math.radians(az)
            pen = QPen(color, 3 if not dashed else 2)
            if dashed:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawLine(c, QPointF(c.x() + (r - 4) * math.sin(a), c.y() - (r - 4) * math.cos(a)))
        if self.target:
            needle(self.target[0], TARGET, dashed=True)
        if self.real:
            needle(self.real[0], REAL)
        p.setBrush(REAL); p.setPen(Qt.NoPen); p.drawEllipse(c, 3, 3)
        # arco de elevação (0° à esquerda/baixo, 90° no alto)
        ex, ey, er = h + 6, h - 6, h - 14
        rect = QRectF(ex, ey - er, 2 * er, 2 * er)
        p.setPen(QPen(DIAL, 5)); p.setBrush(Qt.NoBrush)
        p.drawArc(rect, 90 * 16, 90 * 16)

        def el_mark(el, color, dashed=False):
            a = math.radians(90 - max(0.0, min(90.0, el)))
            pen = QPen(color, 3 if not dashed else 2)
            if dashed:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            center = QPointF(ex + er, ey)
            p.drawLine(QPointF(center.x() - er * math.cos(math.radians(el)) * 0.55, center.y() - er * math.sin(math.radians(el)) * 0.55),
                       QPointF(center.x() - er * math.cos(math.radians(el)), center.y() - er * math.sin(math.radians(el))))
            return a
        if self.target:
            el_mark(self.target[1], TARGET, dashed=True)
        if self.real:
            el_mark(self.real[1], REAL)
        p.setPen(TEXT)
        p.drawText(QPointF(ex + er * 0.55, ey - 4), "EL")
        if self.flip:
            p.setPen(TARGET)
            p.drawText(QPointF(ex + er * 0.35, 12), "FLIP")
        p.end()
