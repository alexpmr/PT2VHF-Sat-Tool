"""v1.7.1: tema do programa (Configurações → Aparência).

A folha de estilo é gerada a partir da folha original (tema escuro da v1.7.0), transformando cada cor:
tema pronto (escuro, escuro alto contraste, claro, noturno vermelho) e ajustes finos (cor de destaque,
brilho, contraste, saturação, tamanho da fonte). As cores de alerta (vermelho de PARAR/CAT, âmbar de
avisos) mantêm o matiz em todos os temas, e a legibilidade é conferida pelo contraste WCAG.
"""
from __future__ import annotations

import colorsys
import re

PRESETS = {
    "escuro": "Escuro (padrão)",
    "alto_contraste": "Escuro alto contraste",
    "claro": "Claro",
    "noturno": "Noturno vermelho (preserva a visão noturna)",
}
DEFAULTS = {"theme_preset": "escuro", "theme_accent_hue": -1, "theme_brightness": 100, "theme_contrast": 100,
            "theme_saturation": 100, "theme_font_px": 12, "theme_follow_display": False, "theme_follow_map": False}
ACCENT_HUES = {"Original (ciano)": -1, "Azul": 215, "Verde": 140, "Âmbar": 40, "Roxo": 275, "Rosa": 330}
HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
BASE_TEXT, BASE_BG = "#e8edf5", "#0b1526"


def _rgb(hexcolor: str) -> tuple:
    h = hexcolor.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def is_alert(hexcolor: str) -> bool:
    """Vermelhos/âmbar saturados (PARAR, erro CAT, avisos): preservam o matiz em qualquer tema."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(hexcolor))
    deg = h * 360
    return s > 0.35 and l > 0.2 and (deg < 25 or deg > 340 or 30 <= deg <= 55)


def transform(hexcolor: str, opts: dict) -> str:
    o = {**DEFAULTS, **(opts or {})}
    h, l, s = colorsys.rgb_to_hls(*_rgb(hexcolor))
    alert = is_alert(hexcolor)
    preset = o["theme_preset"]
    if preset == "alto_contraste":
        l = l * 0.55 if l < 0.5 else min(1.0, 0.5 + (l - 0.5) * 1.6 + 0.08)
    elif preset == "claro":
        l = 1.0 - l * 0.92
        if not alert:
            s *= 0.85
    elif preset == "noturno":
        if not alert:
            h, s = 0.0, max(0.55, s)
        l = l * 0.75
    accent = int(o["theme_accent_hue"])
    deg = h * 360
    if accent >= 0 and not alert and s > 0.3 and 160 <= deg <= 205 and preset != "noturno":
        h = accent / 360.0
    l = 0.5 + (l - 0.5) * (o["theme_contrast"] / 100.0)
    l = l * (o["theme_brightness"] / 100.0)
    s = s * (o["theme_saturation"] / 100.0)
    return _hex(colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s))))


def transform_qss(qss: str, opts: dict) -> str:
    o = {**DEFAULTS, **(opts or {})}
    out = HEX.sub(lambda m: transform(m.group(0), o), qss or "")
    if int(o["theme_font_px"]) != 12:
        out = out.replace("font-size:12px}", f"font-size:{int(o['theme_font_px'])}px}}", 1)
    return out


def luminance(hexcolor: str) -> float:
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(hexcolor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_contrast(opts: dict) -> float:
    """Contraste do texto principal sobre o fundo no tema escolhido (WCAG AA ≥ 4,5)."""
    return contrast_ratio(transform(BASE_TEXT, opts), transform(BASE_BG, opts))


def display_dim(opts: dict) -> float:
    """Fator de brilho do display/mapa quando 'acompanhar o brilho' estiver ligado (0,3–1,0)."""
    o = {**DEFAULTS, **(opts or {})}
    factor = o["theme_brightness"] / 100.0 * (0.6 if o["theme_preset"] == "noturno" else 1.0)
    return max(0.3, min(1.0, factor))
