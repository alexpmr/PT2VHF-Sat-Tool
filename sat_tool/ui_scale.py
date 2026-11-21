"""v1.9.2: ajuste proporcional da interface para caber em telas baixas sem rolar (pedido do PU2MUS / operador).

A aba Operação precisa de ~840 px de área útil da janela (mais a barra de título) em escala 100 %. Em telas
menores (ex.: notebook 1366×768 com a barra de tarefas) o programa inteiro é reduzido na mesma proporção com
QT_SCALE_FACTOR — fontes, display, botões, espaçamentos e mapa — mantendo tudo no lugar. Nunca abaixo de 80 %
(o texto ficaria pequeno demais; abaixo disso volta a rolagem) e nunca acima de 100 %.

O fator precisa ser definido ANTES de criar a QApplication:
- Windows: altura útil da tela (sem a barra de tarefas) em pixels lógicos, lida pela API do Windows;
- qualquer sistema: se depois de aberto ainda houver rolagem com a janela maximizada, o fator que faria caber
  é guardado e usado a partir da próxima abertura;
- Configurações → Tema → "Escala da interface" permite fixar 100 %/95 %/90 %/85 %/80 % (vale ao reabrir).
"""
from __future__ import annotations

import math
import os
import sys

NEEDED_HEIGHT = 880      # altura útil de tela (com barra de título) para a aba Operação sem rolagem a 100 %
MIN_SCALE = 0.80
CHOICES = (("auto", "Automática"), (1.0, "100 %"), (0.95, "95 %"), (0.9, "90 %"), (0.85, "85 %"), (0.8, "80 %"))


def clamp(value: float) -> float:
    """Entre 80 % e 100 %, arredondado para baixo em passos de 1 % (arredondar para cima voltaria a rolar)."""
    return max(MIN_SCALE, min(1.0, math.floor(float(value) * 100 + 1e-9) / 100))


def windows_work_area_height() -> int | None:
    """Altura útil da tela principal (sem a barra de tarefas) em pixels lógicos (96 dpi), antes do Qt."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        if not ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            return None
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 90) or 96                                  # LOGPIXELSY
        ctypes.windll.user32.ReleaseDC(0, hdc)
        # mesma unidade das duas medidas (com ou sem DPI-awareness): pixels lógicos = físicos × 96 / dpi
        return int(round((rect.bottom - rect.top) * 96 / dpi))
    except Exception:
        return None


def choose_scale(setting, screen_height: int | None, learned: dict | None) -> float:
    """Fator final: escolha manual > tela medida (Windows) > aprendido numa abertura anterior > 100 %."""
    if setting not in (None, "", "auto"):
        try:
            return clamp(setting)
        except (TypeError, ValueError):
            pass
    candidates = []
    if screen_height:
        candidates.append(screen_height / NEEDED_HEIGHT)
    if isinstance(learned, dict) and learned.get("scale"):
        same_screen = not screen_height or not learned.get("screen_h") or \
            abs(int(learned["screen_h"]) - int(screen_height)) <= 8
        if same_screen:
            candidates.append(float(learned["scale"]))
    return clamp(min(candidates)) if candidates else 1.0


def apply_before_qt(values: dict) -> float:
    """Define QT_SCALE_FACTOR conforme a configuração/tela. Respeita um QT_SCALE_FACTOR já definido pelo usuário."""
    if os.environ.get("QT_SCALE_FACTOR"):
        try:
            return float(os.environ["QT_SCALE_FACTOR"])
        except ValueError:
            return 1.0
    scale = choose_scale(values.get("ui_scale", "auto"), windows_work_area_height(), values.get("ui_scale_learned"))
    if scale < 0.995:
        os.environ["QT_SCALE_FACTOR"] = f"{scale:.2f}"
    return scale


def current_scale() -> float:
    try:
        return float(os.environ.get("QT_SCALE_FACTOR") or 1.0)
    except ValueError:
        return 1.0


def learn_from_window(window, scroll, available_height: int) -> dict | None:
    """Com a janela maximizada (ou ocupando a tela toda), se a aba ainda rola, calcula o fator que faria caber."""
    try:
        content = scroll.widget().height()
        viewport = scroll.viewport().height()
    except Exception:
        return None
    if content <= viewport + 2 or viewport <= 0:
        return None
    if not (window.isMaximized() or window.isFullScreen() or window.height() >= available_height * 0.95):
        return None   # janela pequena por escolha do operador: não reduz o programa
    scale = current_scale()
    proposed = clamp(scale * viewport / content - 0.005)
    if proposed >= scale:
        return None
    return {"scale": proposed, "screen_h": int(round(available_height * scale))}
