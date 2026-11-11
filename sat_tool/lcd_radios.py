"""v1.7.1: modelos de display no estilo de rádios VHF/UHF reais (sem logotipos), dentro do display do Sat Tool.

Mockups aprovados pelo operador em 07/11/2026 (docs/backlog/display-ic706-ic7100-realista-v2.png e
display-outros-modelos-mockup.png). Os comandos do app ocupam o lugar das funções equivalentes do rádio:
teclas soft/abas → A/B (MAIN↔SUB), RX ONLY, TIPO, LUZ; ícones → SAT, AUTO, CAT, DOP; área de memória →
nome do satélite + LOS m:ss. O escopo usa a FFT real do RTL-SDR (mesma do painel SDR); sem SDR mostra
"SDR DESLIGADO". Tudo desenhado em vetor/pixels inteiros, nítido em qualquer DPI.
"""
from __future__ import annotations

from .lcd import (QColor, QImage, QPen, QPointF, QRectF, DISPLAY_KEYS, MODEL_THEMES, LcdState, _Digital, _Matrix,
                  _Seven, countdown_text, freq_parts, sides, smeter_text)

try:
    from PySide6.QtGui import QPolygonF
except ImportError:  # pragma: no cover
    from PySide2.QtGui import QPolygonF

SCOPE_MODELS = ("ic706", "ic7100", "ft991", "ic9700")
KEY_LABELS = dict(DISPLAY_KEYS)
KEY_ORDER = ("swap", "rxonly", "type", "light")


def theme_for(model: str, theme: str) -> str:
    allowed = MODEL_THEMES.get(model)
    if allowed and theme not in allowed:
        return allowed[0]
    return theme


# ---------------------------------------------------------------- peças comuns
def _signal_frac(st: LcdState) -> tuple[float, str]:
    if st.signal is not None:
        return max(0.0, min(1.0, st.signal / 30)), smeter_text(int(st.signal))
    el = st.elevation if st.elevation is not None else 0.0
    return max(0.0, min(1.0, el / 90)), (f"EL {el:+.0f}°" if st.elevation is not None else "")


def _count(st: LcdState) -> str:
    if st.los_s is not None:
        return "LOS " + countdown_text(st.los_s)
    if st.aos_s is not None:
        return "AOS " + countdown_text(st.aos_s)
    return ""


def _short_freq(hz):
    main, last = freq_parts(hz)
    return main + last


def _meter(style, x, y, w, frac, labels, hh, tx=False):
    """Medidor com escala impressa acima (como os S/Po dos rádios)."""
    u = style.u
    px = 9 * u
    n = 24
    seg = w / n
    for i, text in enumerate(labels):
        lx = x + (i / max(1, len(labels) - 1)) * (w - style.text_w(text, px))
        style.label(lx, y, text, px)
    style.bar(x, y + 12 * u, frac, n, seg, hh)
    return x + w


def _scope_color(v: float) -> QColor:
    v = max(0.0, min(1.0, v))
    stops = ((0.0, (4, 10, 40)), (0.35, (10, 90, 200)), (0.6, (40, 220, 220)), (0.8, (250, 230, 60)),
             (1.0, (255, 60, 40)))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if v <= b:
            t = (v - a) / (b - a)
            return QColor(*(int(ca[k] + (cb[k] - ca[k]) * t) for k in range(3)))
    return QColor(255, 60, 40)


def _scope(style, rect: QRectF, st: LcdState, ink: QColor, grid: QColor, waterfall: bool, fill=None):
    """Espectro (e waterfall) com os dados reais do RTL-SDR; marcador vermelho no canal."""
    p, u = style.p, style.u
    p.save()
    p.setClipRect(rect)
    p.setPen(QPen(grid, max(1.0, 0.8 * u)))
    p.setBrush(fill if fill is not None else QColor(0, 0, 0, 0))
    p.drawRect(rect)
    spec = list(st.scope or [])
    spec_h = rect.height() * (0.55 if waterfall else 1.0)
    sr = QRectF(rect.x(), rect.y(), rect.width(), spec_h)
    for i in range(1, 4):
        gx = sr.x() + sr.width() * i / 4
        p.drawLine(QPointF(gx, sr.y()), QPointF(gx, sr.bottom()))
    if not spec:
        text = "SDR DESLIGADO"
        style.label(rect.center().x() - style.text_w(text, 11 * u) / 2, rect.center().y() - 7 * u, text, 11 * u, grid)
        p.restore()
        return rect
    n = len(spec)
    poly = QPolygonF()
    poly.append(QPointF(sr.x(), sr.bottom()))
    for i, v in enumerate(spec):
        poly.append(QPointF(sr.x() + sr.width() * i / max(1, n - 1), sr.bottom() - max(0.0, min(1.0, v)) * (spec_h - 2 * u)))
    poly.append(QPointF(sr.right(), sr.bottom()))
    area = QColor(ink); area.setAlpha(70)
    p.setPen(QPen(ink, max(1.0, 1.1 * u)))
    p.setBrush(area)
    p.drawPolygon(poly)
    if waterfall and st.scope_rows:
        rows = st.scope_rows[:48]
        cols = max(len(r) for r in rows)
        img = QImage(cols, len(rows), QImage.Format_RGB32)
        img.fill(QColor(4, 10, 40))
        for y, row in enumerate(rows):
            for x, v in enumerate(row):
                img.setPixelColor(x, y, _scope_color(v))
        p.drawImage(QRectF(rect.x(), sr.bottom(), rect.width(), rect.height() - spec_h), img)
    p.setPen(QPen(QColor("#ff3b30"), max(1.0, 1.4 * u)))
    cx = rect.center().x()
    p.drawLine(QPointF(cx, rect.y()), QPointF(cx, rect.bottom()))
    if st.scope_span_hz:
        lab = f"±{st.scope_span_hz / 1000:.0f}k"
        style.label(rect.right() - style.text_w(lab, 9 * u) - 3 * u, rect.y() + 2 * u, lab, 9 * u, grid)
    p.restore()
    return rect


def _keys(style, x, y, x_max, order=KEY_ORDER, prefix=None):
    """Teclas funcionais (rótulos do Sat Tool). Retorna (dict de retângulos, x final)."""
    u = style.u
    keys = {}
    for i, key in enumerate(order):
        lab = KEY_LABELS[key]
        if prefix:
            pre = prefix[i]
            x = style.label(x, y + 1 * u, pre, 9 * u) + 3 * u
        if x + style.key_w(lab) > x_max:
            break
        keys[key] = style.key(x, y, lab)
        x = keys[key].right() + 7 * u
    return keys, x


def _tags(style, x, y, x_max, items):
    for text, blink in items:
        if not text:
            continue
        if x + style.tag_w(text) > x_max:
            break
        x = style.tag(x, y, text, blink=blink)
    return x


def _status_items(st: LcdState):
    items = []
    count = _count(st)
    if count:
        items.append((count, st.los_s is not None and st.los_s <= 30))
    if st.sat_on:
        items.append(("SAT", False))
    if st.link:
        items.append((st.link, False))
    if st.auto:
        items.append(("AUTO", False))
    if st.doppler_hz is not None and not st.swapped:
        items.append((f"DOP {st.doppler_hz / 1000:+.1f}k", False))
    if st.rotor:
        items.append((st.rotor, False))
    return items


def _tx_text(sub):
    if sub["off"]:
        return "RX ONLY"
    return f"{sub['role']} {_short_freq(sub['hz'])} {sub['mode'][:4].upper()}".strip()


# ---------------------------------------------------------------- IC-706MKIIG
def paint_ic706(style: _Seven, st: LcdState) -> dict:
    u, W, H = style.u, style.w, style.h
    style.background()
    main, sub = sides(st)
    m = 10 * u
    scope_w = min(0.24 * W, 260 * u) if W > 760 * u else 0
    right = W - m - (scope_w + 10 * u if scope_w else 0)
    # medidor S/Po com escala impressa
    frac, mtxt = _signal_frac(st)
    tx = st.transmitting and not sub["off"]
    if tx:
        frac, mtxt = (st.power_w or 0) / 100, (f"{st.power_w}W" if st.power_w is not None else "")
    lab = "Po" if tx else "S"
    lx = style.label(m, 12 * u, lab, 12 * u) + 6 * u
    mw = min(0.36 * W, 330 * u)
    labels = ("0", "25", "50", "75", "100%") if tx else ("1", "3", "5", "7", "9", "+20", "+40", "+60dB")
    ex = _meter(style, lx, 2 * u, mw, frac, labels, 7 * u)
    style.label(ex + 8 * u, 12 * u, mtxt, 11 * u)
    # coluna de ícones fixos
    y = 30 * u
    for text in ((main["mode"] or "FM")[:4].upper(), "SAT" if st.sat_on else "", "AUTO" if st.auto else "",
                 "VFO B" if st.swapped else "VFO A"):
        if text:
            style.label(m, y, text, 10 * u)
            y += 14 * u
    # frequência 7 seg. (dígitos menores que o TS-2000, como no 706)
    fx = m + 56 * u
    main_s, last = freq_parts(main["hz"])
    size = 52 * u
    mem_w = 190 * u
    while size > 18 * u and fx + style.digits_w(main_s, size) + 0.5 * size + style.digits_w("2", size * 0.6) + mem_w > right:
        size -= 1 * u
    fy = 28 * u
    xe = style.digits(fx, fy, main_s, size)
    xe = style.digits(xe + 0.38 * size, fy + size * 0.4, last, size * 0.6)
    # área de memória: satélite, contagem e TX (logo depois da frequência, como no LCD do 706)
    mx = min(right - mem_w, xe + 30 * u)
    style.label(mx, 30 * u, (st.sat_name or "—").upper()[:16], 13 * u)
    count = _count(st)
    if count:
        style.tag(mx, 48 * u, count, blink=st.los_s is not None and st.los_s <= 30)
    style.label(mx, 70 * u, _tx_text(sub), 11 * u)
    # band scope simples
    if scope_w:
        scope_r = _scope(style, QRectF(W - m - scope_w, 4 * u, scope_w, 88 * u), st, style.ink, style.off, waterfall=False)
    # linha de teclas soft no LCD (F-1) — A/B, RX ONLY, TIPO, LUZ
    ky = H - 25 * u
    x = style.tag(m, ky, "F-1")
    keys, x = _keys(style, x + 4 * u, ky, W - m)
    _tags(style, x + 6 * u, ky, W - m, [(t, b) for t, b in _status_items(st) if not t.startswith(("LOS", "AOS", "SAT", "AUTO"))])
    if scope_w:
        keys["scope"] = scope_r
    return keys


# ---------------------------------------------------------------- IC-7100
def paint_ic7100(style: _Matrix, st: LcdState) -> dict:
    u, W, H = style.u, style.w, style.h
    style.background()
    main, sub = sides(st)
    sp = style.small
    m = int(round(8 * u))
    # barra de status invertida
    bar_h = 12 * sp
    style.p.fillRect(QRectF(0, 0, W, bar_h), style.ink)
    x = m
    for text in ((main["mode"] or "FM")[:4].upper(), "SAT" if st.sat_on else "", "AUTO" if st.auto else "",
                 st.link, "RX ONLY" if st.rx_only else ""):
        if text:
            x = style.mtext(x, 3 * sp, text, sp, style.light) + 6 * sp
    count = _count(st)
    if count:
        style.mtext(W - m - (len(count) * 6 - 1) * sp, 3 * sp, count, sp, style.light)
    scope_w = int(min(0.3 * W, 300 * u)) if W > 700 * u else 0
    right = W - m - (scope_w + 8 * sp if scope_w else 0)
    # medidor S
    y = bar_h + 3 * sp
    frac, mtxt = _signal_frac(st)
    lx = style.mtext(m, y, "S", sp) + 3 * sp
    bw = min(right - lx - 40 * sp, 260 * u)
    ex = style.bar(lx, y + sp, frac, 20, bw / 20, 5 * sp)
    style.mtext(ex + 3 * sp, y, mtxt, sp)
    # VFO A grande
    y += 9 * sp
    ky = H - 13 * sp
    style.tag(m, y + sp, "B" if st.swapped else "A")       # VFO A/B em etiqueta invertida
    main_s, last = freq_parts(main["hz"])
    big = max(2, int(round(5 * u)))
    fx = m + 12 * sp
    while big > 2 and (fx + style.digits_w(main_s, big) + 8 * big > right or y + 7 * big + 11 * sp > ky - sp):
        big -= 1
    xe = style.digits(fx, y, main_s, big)
    style.mtext(xe + big, y + 2 * big, last, max(2, big - 1), grid=True)
    # SUB/TX menor
    y2 = y + 7 * big + 2 * sp
    style.mtext(m, y2, ("SUB " if not st.swapped else "MAIN ") + _tx_text(sub), sp)
    if st.sat_name:
        name = st.sat_name.upper()[:18]
        style.mtext(right - (len(name) * 6 - 1) * sp, y2, name, sp)
    if scope_w:
        r = QRectF(W - m - scope_w, bar_h + 3 * sp, scope_w, ky - bar_h - 6 * sp)
        _scope(style, r, st, style.ink, style.off, waterfall=False)
    # abas touch
    keys, x = _keys(style, m, ky, W - m)
    if scope_w:
        keys["scope"] = r
    return keys


# ---------------------------------------------------------------- FT-897/857
def paint_ft897(style: _Seven, st: LcdState) -> dict:
    u, W, H = style.u, style.w, style.h
    style.background()
    main, sub = sides(st)
    m = 10 * u
    # ícones superiores
    x = m
    for text in ((main["mode"] or "FM")[:4].upper(), "SAT" if st.sat_on else "", "VFO B" if st.swapped else "VFO A",
                 "AUTO" if st.auto else "", st.link):
        if text:
            x = style.label(x, 4 * u, text, 11 * u) + 10 * u
    count = _count(st)
    if count:
        style.tag(W - m - style.tag_w(count), 2 * u, count, blink=st.los_s is not None and st.los_s <= 30)
    # frequência grande
    main_s, last = freq_parts(main["hz"])
    side_w = min(0.3 * W, 300 * u)
    size = 60 * u
    while size > 18 * u and m + style.digits_w(main_s, size) + 0.5 * size + style.digits_w("2", size * 0.62) > W - side_w - m:
        size -= 1 * u
    fy = 24 * u
    xe = style.digits(m, fy, main_s, size)
    style.digits(xe + 0.38 * size, fy + size * 0.38, last, size * 0.62)
    # lado direito: TX e satélite
    sx = W - side_w - m + 10 * u
    style.label(sx, 26 * u, (st.sat_name or "—").upper()[:18], 13 * u)
    style.label(sx, 44 * u, _tx_text(sub), 11 * u)
    frac, mtxt = _signal_frac(st)
    _meter(style, sx, 58 * u, side_w - 30 * u, frac, ("S1", "3", "5", "7", "9", "+20", "+60"), 7 * u)
    # linha multifunção A/B/C (+F) com as legendas no próprio LCD
    ky = H - 25 * u
    keys, x = _keys(style, m, ky, W - m, prefix=("[A]", "[B]", "[C]", "F"))
    _tags(style, x + 6 * u, ky, W - m, [(t, b) for t, b in _status_items(st)
                                         if not t.startswith(("LOS", "AOS", "SAT", "AUTO", "CAT", "SDR"))])
    return keys


# ---------------------------------------------------------------- IC-910H
def paint_ic910(style: _Seven, st: LcdState) -> dict:
    u, W, H = style.u, style.w, style.h
    style.background()
    m = 10 * u
    row_h = 44 * u
    meter_w = min(0.3 * W, 300 * u)
    for i, side in enumerate(sides(st)):
        y = 3 * u + i * (row_h + 3 * u)
        x = style.tag(m, y + 2 * u, side["name"])
        style.tag(m, y + 22 * u, "TX OFF" if side["off"] else side["role"])
        style.label(x + 2 * u, y + 4 * u, (side["mode"] or "")[:4].upper(), 11 * u)
        main_s, last = freq_parts(None if side["off"] else side["hz"])
        size = 34 * u
        fx = m + 92 * u
        while size > 14 * u and fx + style.digits_w(main_s, size) + 0.5 * size + style.digits_w("2", size * 0.62) > W - meter_w - 2 * m:
            size -= 1 * u
        xe = style.digits(fx, y + 4 * u, main_s, size)
        style.digits(xe + 0.38 * size, y + 4 * u + size * 0.38, last, size * 0.62)
        # medidor por banda: S no RX, Po no TX
        mx = W - meter_w - m
        if side["role"] == "RX":
            frac, txt = _signal_frac(st)
            labels = ("S1", "3", "5", "7", "9", "+20", "+40", "+60")
        else:
            frac = 0.0 if side["off"] else (st.power_w or 0) / 100
            txt = "" if side["off"] or st.power_w is None else f"{st.power_w}W"
            labels = ("Po", "25", "50", "75", "100%")
        _meter(style, mx, y + 6 * u, meter_w - 40 * u, frac, labels, 7 * u)
        style.label(W - m - 34 * u, y + 18 * u, txt, 10 * u)
    ky = H - 25 * u
    x = style.tag(m, ky, "SATELLITE") if st.sat_on else m
    keys, x = _keys(style, x, ky, W - m)
    _tags(style, x + 6 * u, ky, W - m, [(t, b) for t, b in _status_items(st) if t != "SAT"])
    return keys


# ---------------------------------------------------------------- FT-991A / IC-9700 (TFT)
def paint_tft(style: _Digital, st: LcdState, variant: str) -> dict:
    u, W, H = style.u, style.w, style.h
    style.background()
    main, sub = sides(st)
    m = 10 * u
    split = W * (0.5 if W > 700 * u else 1.0)
    # barra de status
    x = style.tag(m, 4 * u, (main["mode"] or "FM")[:4].upper(), bg=QColor("#1f5fa8"))
    for text, blink in _status_items(st):
        if x + style.tag_w(text) > split - m:
            break
        x = style.tag(x, 4 * u, text, blink=blink)
    # MAIN grande
    label_main = "MAIN" if variant == "ic9700" else ("VFO-B" if st.swapped else "VFO-A")
    style.label(m, 28 * u, label_main, 11 * u, QColor("#7fd0ff"))
    style.tag(m, 44 * u, "TX OFF" if main["off"] else main["role"],
              bg=QColor("#2fbf4a") if main["role"] == "RX" else QColor("#d8443a"))
    main_s, last = freq_parts(main["hz"])
    size = 38 * u
    fx = m + 52 * u
    while size > 14 * u and fx + style.digits_w(main_s, size) + style.digits_w("2", size * 0.66) + 10 * u > split - m:
        size -= 1 * u
    xe = style.digits(fx, 26 * u, main_s, size)
    style.digits(xe + 2 * u, 26 * u + size * 0.34, last, size * 0.66)
    # SUB menor
    sub_label = "SUB" if variant == "ic9700" else ("VFO-A" if st.swapped else "VFO-B")
    y2 = 26 * u + size + 8 * u
    style.label(m, y2, sub_label, 11 * u, QColor("#7fd0ff"))
    style.label(m + 52 * u, y2, _tx_text(sub), 13 * u)
    frac, mtxt = _signal_frac(st)
    if y2 + 20 * u < H - 30 * u:
        lx = style.label(m, y2 + 18 * u, "S", 11 * u) + 6 * u
        ex = style.bar(lx, y2 + 20 * u, frac, 20, min(9 * u, (split - lx - 60 * u) / 20), 7 * u)
        style.label(ex + 6 * u, y2 + 18 * u, mtxt, 11 * u)
    # escopo + waterfall à direita
    if split < W:
        r = QRectF(split + 4 * u, 4 * u, W - split - m - 4 * u, H - 34 * u)
        _scope(style, r, st, QColor("#e8f2ff"), QColor(255, 255, 255, 60), waterfall=True, fill=QColor("#02060d"))
        if st.sat_name:
            style.label(r.x() + 4 * u, r.y() + 2 * u, st.sat_name[:24], 10 * u, QColor("#9fd6ff"))
    # abas touch
    ky = H - 24 * u
    keys, x = _keys(style, m, ky, W - m)
    for inert in ("SCOPE", "MENU"):
        if x + style.key_w(inert) > W - m:
            break
        x = style.key(x, ky, inert).right() + 7 * u
    if split < W:
        keys["scope"] = r
    return keys


def make_radio_style(model, p, w, h, u, theme):
    theme = theme_for(model, theme)
    if model == "ic7100":
        return _Matrix(p, w, h, u, "branco")
    if model in ("ft991", "ic9700"):
        return _Digital(p, w, h, u, theme)
    return _Seven(p, w, h, u, theme, led=False)


def paint_radio(model: str, style, st: LcdState) -> dict:
    if model == "ic706":
        return paint_ic706(style, st)
    if model == "ic7100":
        return paint_ic7100(style, st)
    if model == "ft897":
        return paint_ft897(style, st)
    if model == "ic910":
        return paint_ic910(style, st)
    return paint_tft(style, st, model)
