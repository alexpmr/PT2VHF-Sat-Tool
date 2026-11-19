"""Moldura de rádio realista ao redor do display (v1.9.2; mockup aprovado pelo operador em 07/11/2026).

Painel metálico escovado com parafusos, LCD rebaixado com sombra interna e reflexo de vidro, botão de sintonia
decorativo, botão AF, LED de alimentação e uma fileira de teclas de borracha. As teclas com função (A/B, RX ONLY,
TIPO, LUZ) são clicáveis; CAT, AUTO e SAT são indicadores (LED aceso conforme o estado). A etiqueta é um texto
livre do operador em fonte neutra (marca e modelo do rádio, indicativo…) — nunca logotipos de fabricantes.

O fundo (metal, parafusos, botões e etiqueta) é desenhado uma vez e guardado em cache; a cada atualização só
as teclas/LEDs são redesenhados.
"""
from __future__ import annotations

import math
import random

try:
    from PySide6.QtGui import (QColor, QConicalGradient, QFont, QImage, QLinearGradient, QPainter,
                               QPainterPath, QPen, QRadialGradient, QBrush)
    from PySide6.QtCore import QPointF, QRectF, Qt
except ImportError:  # PySide2
    from PySide2.QtGui import (QColor, QConicalGradient, QFont, QImage, QLinearGradient, QPainter,
                               QPainterPath, QPen, QRadialGradient, QBrush)
    from PySide2.QtCore import QPointF, QRectF, Qt

# teclas da moldura: (código do clique, texto, legenda secundária)
BEZEL_KEYS = (("swap", "A/B", "MAIN↔SUB"), ("rxonly", "RX ONLY", ""), ("type", "TIPO", "DISPLAY"),
              ("light", "LUZ", "DIMMER"))
BEZEL_LEDS = (("CAT", "LINK"), ("AUTO", "DOPPLER"), ("SAT", "TRACE"))
TOP, BOTTOM = 26, 40          # faixas da etiqueta e das teclas (unidades lógicas)
DOCKED_MIN, DOCKED_MAX = 196, 250


def layout(w: float, h: float) -> dict:
    """Retângulos (lógicos) da moldura: LCD interno, áreas esquerda/direita e faixa das teclas."""
    wide = w >= 640
    left = 86 if wide else 10
    right = 128 if wide else 10
    lcd = QRectF(left + 8, TOP + 8, max(80.0, w - left - right - 16), max(60.0, h - TOP - BOTTOM - 14))
    return {"wide": wide, "left": left, "right": right, "lcd": lcd, "keys_y": h - BOTTOM + 6}


def _font(px: float, bold: bool = True, stretch: int = 100, spacing: float = 0.0) -> QFont:
    f = QFont()
    try:
        f.setFamilies(["DejaVu Sans", "Segoe UI", "Helvetica Neue", "Arial"])
    except AttributeError:
        f.setFamily("Arial")
    f.setPixelSize(max(6, int(round(px))))
    f.setBold(bold)
    f.setStretch(stretch)
    f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def _text(p, rect, s, px, color, align=Qt.AlignCenter, bold=True, stretch=90, spacing=0.5):
    p.setFont(_font(px, bold, stretch, spacing))
    p.setPen(QColor(color))
    p.drawText(rect, align | Qt.AlignVCenter, s)


def _knob(p, cx, cy, r, big=False):
    for i in range(5):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 22))
        p.drawEllipse(QPointF(cx + 2, cy + 3), r + i, r + i)
    cg = QConicalGradient(cx, cy, 120)
    for k in range(37):
        cg.setColorAt(k / 36, QColor("#6d727a") if k % 2 else QColor("#2b2e33"))
    p.setPen(QPen(QColor("#121316"), 1))
    p.setBrush(QBrush(cg))
    p.drawEllipse(QPointF(cx, cy), r, r)
    for k in range(int(r * 3)):
        a = 2 * math.pi * k / int(r * 3)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1.0))
        p.drawLine(QPointF(cx + math.cos(a) * (r - 1), cy + math.sin(a) * (r - 1)),
                   QPointF(cx + math.cos(a) * (r * 0.86), cy + math.sin(a) * (r * 0.86)))
    rg = QRadialGradient(cx - r * 0.3, cy - r * 0.35, r * 1.1)
    rg.setColorAt(0, QColor("#5b6068")); rg.setColorAt(0.6, QColor("#25272b")); rg.setColorAt(1, QColor("#141518"))
    p.setPen(QPen(QColor("#0d0e10"), 1)); p.setBrush(rg)
    p.drawEllipse(QPointF(cx, cy), r * 0.82, r * 0.82)
    if big:
        dg = QRadialGradient(cx + r * .38, cy - r * .32, r * .2)
        dg.setColorAt(0, QColor("#08090a")); dg.setColorAt(1, QColor("#3b3e44"))
        p.setPen(Qt.NoPen); p.setBrush(dg)
        p.drawEllipse(QPointF(cx + r * .38, cy - r * .32), r * .16, r * .16)
    else:
        p.setPen(QPen(QColor("#e6e9ed"), 1.6))
        p.drawLine(QPointF(cx, cy - r * 0.75), QPointF(cx, cy - r * 0.4))


def paint_background(w: float, h: float, label: str, sublabel: str, dpr: float = 1.0) -> QImage:
    """Metal escovado, parafusos, etiqueta, AF/PWR à esquerda e dial à direita (sem as teclas).
    Desenhado em pixels físicos (w×h lógicos × dpr) para ficar nítido em qualquer escala de tela."""
    img = QImage(max(1, int(round(w * dpr))), max(1, int(round(h * dpr))), QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.scale(dpr, dpr)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    lay = layout(w, h)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor("#4a4e55")); g.setColorAt(0.08, QColor("#34373c"))
    g.setColorAt(0.5, QColor("#26282c")); g.setColorAt(1, QColor("#1a1b1e"))
    p.setPen(QPen(QColor("#5c6169"), 1.2)); p.setBrush(g)
    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)
    rnd = random.Random(3)
    p.save()
    clip = QPainterPath(); clip.addRoundedRect(QRectF(0, 0, w, h), 10, 10); p.setClipPath(clip)
    for i in range(int(h * 1.5)):
        yy = i * 0.67
        a = rnd.randint(3, 12)
        p.setPen(QPen(QColor(255, 255, 255, a) if rnd.random() < .5 else QColor(0, 0, 0, a), 0.5))
        p.drawLine(QPointF(0, yy), QPointF(w, yy))
    p.restore()
    p.setPen(QPen(QColor(255, 255, 255, 40), 1)); p.drawLine(QPointF(10, 1.5), QPointF(w - 10, 1.5))
    for sx, sy in ((9, 9), (w - 9, 9), (9, h - 9), (w - 9, h - 9)):
        rg = QRadialGradient(sx - 1, sy - 1, 4.5)
        rg.setColorAt(0, QColor("#9aa0a8")); rg.setColorAt(1, QColor("#3a3d42"))
        p.setPen(QPen(QColor("#1a1b1e"), .8)); p.setBrush(rg); p.drawEllipse(QPointF(sx, sy), 3.6, 3.6)
        p.setPen(QPen(QColor("#2a2c30"), 1)); p.drawLine(QPointF(sx - 2, sy), QPointF(sx + 2, sy))
    # etiqueta do operador (texto livre, fonte neutra) e faixa de serviço
    lx = lay["lcd"].x()
    if label:
        _text(p, QRectF(lx, 3, w * 0.45, 20), label.upper(), 15, "#f2f4f6", Qt.AlignLeft, stretch=115, spacing=2.5)
    if sublabel:
        fm_w = (len(label) * 13 + 24) if label else 0
        _text(p, QRectF(lx + fm_w, 5, w * 0.4, 16), sublabel.upper(), 9, "#aeb4bc", Qt.AlignLeft, spacing=1.5)
    _text(p, QRectF(w - lay["right"] - 300, 5, 290, 16), "144 / 440 MHz · SATELLITE", 9, "#aeb4bc",
          Qt.AlignRight, spacing=1.2)
    # moldura rebaixada do LCD
    r = lay["lcd"]
    fg = QLinearGradient(0, r.y() - 6, 0, r.bottom() + 6)
    fg.setColorAt(0, QColor("#08090b")); fg.setColorAt(1, QColor("#2b2e33"))
    p.setPen(QPen(QColor("#555a62"), 1)); p.setBrush(fg)
    p.drawRoundedRect(r.adjusted(-6, -6, 6, 6), 6, 6)
    if lay["wide"]:
        # esquerda: LED PWR e botão AF; direita: dial de sintonia
        cx = lay["left"] / 2 + 2
        lg = QRadialGradient(cx - 18, r.y() + 10, 6)
        lg.setColorAt(0, QColor("#ff6a3d")); lg.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen); p.setBrush(lg); p.drawEllipse(QPointF(cx - 18, r.y() + 10), 5, 5)
        _text(p, QRectF(cx - 12, r.y() + 3, 40, 14), "PWR", 8, "#d9dde2")
        kr = min(24.0, max(14.0, r.height() * 0.22))
        _knob(p, cx, r.center().y() + 10, kr)
        _text(p, QRectF(cx - 40, r.center().y() + 10 - kr - 16, 80, 12), "AF · SQL", 8, "#d9dde2")
        dr = min(56.0, max(26.0, min(lay["right"] / 2 - 10, (h - TOP) / 2 - 12)))
        _knob(p, w - lay["right"] / 2 - 2, (TOP + h) / 2 - 4, dr, big=True)
        _text(p, QRectF(w - lay["right"] / 2 - 42, TOP - 2, 80, 12), "MAIN", 8, "#d9dde2")
    p.end()
    img.setDevicePixelRatio(dpr)
    return img


def paint_overlay(p: QPainter, w: float, h: float, state, active: set) -> dict:
    """Teclas (clicáveis) e LEDs indicadores; retorna os retângulos lógicos das teclas com função."""
    lay = layout(w, h)
    x0, y = lay["lcd"].x(), lay["keys_y"]
    kw, kh, gap = 74.0, 20.0, 9.0
    keys = {}
    leds = {"CAT": getattr(state, "link", "") == "CAT", "AUTO": bool(getattr(state, "auto", False)),
            "SAT": bool(getattr(state, "sat_on", False))}
    items = [(code, t, sub, True) for code, t, sub in BEZEL_KEYS] + [(None, t, sub, False) for t, sub in BEZEL_LEDS]
    max_n = max(1, int((lay["lcd"].width() + gap) // (kw + gap)))
    for i, (code, t, sub, func) in enumerate(items[:max_n]):
        x = x0 + i * (kw + gap)
        r = QRectF(x, y, kw, kh)
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 90)); p.drawRoundedRect(r.translated(1, 2.5), 4, 4)
        g = QLinearGradient(0, y, 0, y + kh)
        g.setColorAt(0, QColor("#4d5158")); g.setColorAt(.5, QColor("#33363b")); g.setColorAt(1, QColor("#26282c"))
        p.setPen(QPen(QColor("#15161a"), 1)); p.setBrush(g); p.drawRoundedRect(r, 4, 4)
        p.setPen(QPen(QColor(255, 255, 255, 45), 1)); p.drawLine(QPointF(x + 4, y + 1.2), QPointF(x + kw - 4, y + 1.2))
        _text(p, r, t, 9, "#eef1f4" if func else "#b8bec6")
        lit = (t in active) if func else leds.get(t, False)
        if t == "A/B":
            lit = bool(getattr(state, "swapped", False))
        if lit:
            lg = QRadialGradient(x + kw - 7, y + 5, 4)
            lg.setColorAt(0, QColor("#55ff88")); lg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setPen(Qt.NoPen); p.setBrush(lg); p.drawEllipse(QPointF(x + kw - 7, y + 5), 3.5, 3.5)
        if sub:
            _text(p, QRectF(x - 8, y + kh + 1, kw + 16, 11), sub, 7.5, "#e0a24a")
        if func:
            keys["bz_" + code] = r
    return keys


def glass(p: QPainter, r: QRectF):
    """Sombra interna e reflexo de vidro sobre o LCD."""
    for i in range(6):
        p.setPen(QPen(QColor(0, 0, 0, 70 - i * 11), 1)); p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(i * .6, i * .6, -i * .6, -i * .6))
    path = QPainterPath()
    path.moveTo(r.x(), r.y()); path.lineTo(r.x() + r.width() * 0.42, r.y())
    path.lineTo(r.x() + r.width() * 0.30, r.bottom()); path.lineTo(r.x(), r.bottom()); path.closeSubpath()
    gg = QLinearGradient(r.x(), r.y(), r.x() + r.width() * .4, r.bottom())
    gg.setColorAt(0, QColor(255, 255, 255, 36)); gg.setColorAt(1, QColor(255, 255, 255, 0))
    p.setPen(Qt.NoPen); p.setBrush(gg); p.drawPath(path)
