"""v1.7.1: display do rádio destacável para outro monitor.

O próprio widget do display (LcdDisplay) é movido para uma janela própria e volta ao lugar ao fechar
a janela ou pelo menu de contexto — o mesmo widget, então A/B, RX ONLY, TIPO, LUZ e a contagem LOS
continuam funcionando e sincronizados. A janela mantém a proporção (dígitos crescem nítidos), tem tela
cheia (F11 ou duplo clique), sempre visível e sem bordas, e lembra monitor, posição, tamanho e modo.
"""
from __future__ import annotations

from .qt_compat import Qt, QWidget, QMenu, QApplication

DEFAULT_ASPECT = 7.5          # largura / altura do display destacado
MAX_HEIGHT_DOCKED = 170


def fit_aspect(width: int, height: int, aspect: float) -> tuple:
    """Maior retângulo com a proporção `aspect` que cabe em width×height, centralizado: (x, y, w, h)."""
    width, height = max(1, int(width)), max(1, int(height))
    if width / height > aspect:
        h = height; w = int(round(h * aspect))
    else:
        w = width; h = int(round(w / aspect))
    return (width - w) // 2, (height - h) // 2, w, h


def screen_for(saved_name: str, saved_rect, screens, primary):
    """Monitor salvo se ainda existir (por nome, ou pelo centro da janela salva); senão o principal."""
    for s in screens:
        if saved_name and s.name() == saved_name:
            return s
    if saved_rect:
        cx = saved_rect[0] + saved_rect[2] / 2
        cy = saved_rect[1] + saved_rect[3] / 2
        for s in screens:
            g = s.geometry()
            if g.x() <= cx < g.x() + g.width() and g.y() <= cy < g.y() + g.height():
                return s
    return primary


class DisplayWindow(QWidget):
    """Janela do display destacado. `on_close` devolve o display à janela principal."""

    def __init__(self, display, config, on_close):
        super().__init__(None)
        self.display, self.config, self.on_close = display, config, on_close
        self.setWindowTitle("PT2VHF Sat Tool · Display")
        self.setStyleSheet("background:#050505")
        self.aspect = float(config.values.get("display_window_aspect", DEFAULT_ASPECT) or DEFAULT_ASPECT)
        self._closing = False
        display.setParent(self)
        display.detached = True
        display.setMinimumHeight(60)
        display.setMaximumHeight(16777215)
        display.extra_menu = self.add_window_actions
        display.fullscreen_requested.connect(self.toggle_fullscreen)
        display.show()
        self.apply_flags(show=False)
        self.restore_placement()

    # ------------------------------------------------------------- modo
    def flag(self, key):
        return bool(self.config.values.get(key, False))

    def apply_flags(self, show=True):
        flags = Qt.Window
        if self.flag("display_window_on_top"):
            flags |= Qt.WindowStaysOnTopHint
        if self.flag("display_window_frameless"):
            flags |= Qt.FramelessWindowHint
        geometry = self.geometry()
        self.setWindowFlags(flags)
        if show:
            self.setGeometry(geometry)
            self.show()

    def toggle(self, key):
        self.config.values[key] = not self.flag(key)
        self.config.save()
        self.apply_flags()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self.config.values["display_window_fullscreen"] = self.isFullScreen()
        self.config.save()

    # ------------------------------------------------------------- posição
    def restore_placement(self):
        app = QApplication.instance()
        rect = self.config.values.get("display_window_rect")
        screens = app.screens() if app else []
        primary = app.primaryScreen() if app else None
        screen = screen_for(str(self.config.values.get("display_window_screen", "")), rect, screens, primary)
        avail = screen.availableGeometry() if screen is not None else None
        if rect and avail is not None and avail.contains(int(rect[0] + rect[2] / 2), int(rect[1] + rect[3] / 2)):
            self.setGeometry(int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
        elif avail is not None:  # monitor salvo sumiu: volta para o principal
            w = min(avail.width() - 40, 1100)
            h = int(w / self.aspect)
            self.setGeometry(avail.x() + (avail.width() - w) // 2, avail.y() + (avail.height() - h) // 2, w, h)
        else:
            self.resize(1100, int(1100 / self.aspect))

    def save_placement(self):
        if not self.isFullScreen():
            g = self.geometry()
            self.config.values["display_window_rect"] = [g.x(), g.y(), g.width(), g.height()]
        screen = self.screen() if hasattr(self, "screen") else None
        if screen is not None:
            self.config.values["display_window_screen"] = screen.name()
        self.config.values["display_window_fullscreen"] = self.isFullScreen()
        self.config.save()

    # ------------------------------------------------------------- eventos
    def resizeEvent(self, event):
        x, y, w, h = fit_aspect(self.width(), self.height(), self.aspect)
        self.display.setGeometry(x, y, w, h)
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.toggle_fullscreen(); return
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen(); return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        self.menu().popup(event.globalPos())

    def menu(self):
        menu = QMenu(self)
        self.add_window_actions(menu)
        menu.addAction("Voltar para a janela principal").triggered.connect(self.close)
        return menu

    def add_window_actions(self, menu):
        for text, func, checked in (("Tela cheia (F11)", self.toggle_fullscreen, self.isFullScreen()),
                                    ("Sempre visível", lambda: self.toggle("display_window_on_top"),
                                     self.flag("display_window_on_top")),
                                    ("Sem bordas", lambda: self.toggle("display_window_frameless"),
                                     self.flag("display_window_frameless"))):
            act = menu.addAction(text); act.setCheckable(True); act.setChecked(checked)
            act.triggered.connect(func)
        menu.addSeparator()

    def closeEvent(self, event):
        if not self._closing:
            self._closing = True
            self.save_placement()
            try:
                self.display.fullscreen_requested.disconnect(self.toggle_fullscreen)
            except (RuntimeError, TypeError):
                pass
            self.display.extra_menu = None
            self.on_close()
        event.accept()
