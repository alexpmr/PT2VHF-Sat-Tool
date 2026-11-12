"""v1.7.1: controles das Configurações do tamanho do conteúdo (não esticados na largura toda).

Cada QComboBox, QDoubleSpinBox e QLineEdit recebe largura máxima medida pela fonte/DPI do próprio
widget: menus pela opção mais longa, campos numéricos pela maior entrada válida (com sufixo) e campos
de texto pelo número de caracteres esperado. Linhas horizontais e grades ganham uma sobra à direita,
de modo que rótulo e campo fiquem juntos e o espaço extra fique depois.
"""
from .qt_compat import QComboBox, QDoubleSpinBox, QLineEdit, QHBoxLayout, QGridLayout, QWidget, QObject, QTimer

try:
    from PySide6.QtCore import QEvent
except ImportError:  # PySide2
    from PySide2.QtCore import QEvent

# Caracteres esperados por campo de texto (atributo da janela → (largura em caracteres, maxLength ou 0)).
TEXT_FIELDS = {
    "callsign": (12, 12),
    "lat": (12, 0),
    "lon": (12, 0),
    "grid_locator": (10, 10),
    "map_edit_lat": (12, 0),
    "map_edit_lon": (12, 0),
}
DEFAULT_TEXT_CHARS = 40       # pesquisas, nomes, URLs e caminhos: mais largos, mas com limite
COMBO_PADDING = 44            # seta + margens do estilo
SPIN_PADDING = 40             # botões ▲▼ + margens


def _advance(widget, text: str) -> int:
    fm = widget.fontMetrics()
    return fm.horizontalAdvance(text) if hasattr(fm, "horizontalAdvance") else fm.width(text)


def combo_width(combo) -> int:
    longest = max([combo.itemText(i) for i in range(combo.count())] + [combo.currentText(), "0000"], key=len)
    widest = max((_advance(combo, combo.itemText(i)) for i in range(combo.count())), default=0)
    width = max(widest, _advance(combo, longest))
    if combo.isEditable():  # porta COM etc.: lista muda em tempo de execução
        width = max(width, _advance(combo, "COM999 · USB Serial")) + 24
    return width + COMBO_PADDING


def spin_width(spin) -> int:
    texts = [spin.textFromValue(spin.minimum()), spin.textFromValue(spin.maximum())]
    return max(_advance(spin, spin.prefix() + t + spin.suffix()) for t in texts) + SPIN_PADDING


def text_width(edit, chars: int) -> int:
    return _advance(edit, "W" * max(1, chars // 2) + "0" * (chars - chars // 2)) + 18


def fit_widget(widget, chars: int = 0, max_length: int = 0):
    if isinstance(widget, QComboBox):
        width = combo_width(widget)
    elif isinstance(widget, QDoubleSpinBox):
        width = spin_width(widget)
    elif isinstance(widget, QLineEdit):
        width = text_width(widget, chars or DEFAULT_TEXT_CHARS)
        if max_length:
            widget.setMaxLength(max_length)
    else:
        return 0
    if isinstance(widget, QLineEdit) and not chars:
        widget.setMaximumWidth(width)  # pesquisas/nomes/URLs: crescem até o limite
    else:
        widget.setFixedWidth(width)
    return width


def _add_trailing_space(layout, seen):
    if layout is None or id(layout) in seen:
        return
    seen.add(id(layout))
    if isinstance(layout, QGridLayout):
        if not getattr(layout, "_pt2vhf_fitted", False):
            for c in range(layout.columnCount()):
                layout.setColumnStretch(c, 0)
                # rótulos inteiros numa linha (sem quebrar palavra a palavra quando a coluna não estica)
                widest = 0
                for r in range(layout.rowCount()):
                    item = layout.itemAtPosition(r, c)
                    w = item.widget() if item is not None else None
                    if w is not None and hasattr(w, "wordWrap") and hasattr(w, "text"):
                        widest = max(widest, _advance(w, w.text()) + 6)
                if widest:
                    layout.setColumnMinimumWidth(c, min(widest, 420))
            layout.setColumnStretch(layout.columnCount(), 1)
            layout._pt2vhf_fitted = True
    elif isinstance(layout, QHBoxLayout):
        if not getattr(layout, "_pt2vhf_fitted", False):
            for i in range(layout.count()):
                layout.setStretch(i, 0)
            layout.addStretch(1)
            layout._pt2vhf_fitted = True
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        if item.layout() is not None:
            _add_trailing_space(item.layout(), seen)
        elif item.widget() is not None and item.widget().layout() is not None:
            _add_trailing_space(item.widget().layout(), seen)


def fit_settings(window, root: QWidget):
    """Aplica larguras pelo conteúdo a todos os campos dentro de `root` (aba Configurações)."""
    named = {}
    for attr, spec in TEXT_FIELDS.items():
        w = getattr(window, attr, None)
        if w is not None:
            named[id(w)] = spec
    widths = {}
    for cls in (QComboBox, QDoubleSpinBox, QLineEdit):
        for w in root.findChildren(cls):
            if isinstance(w, QLineEdit) and isinstance(w.parent(), (QComboBox, QDoubleSpinBox)):
                continue  # editor interno de combo/spin
            chars, max_len = named.get(id(w), (0, 0))
            widths[w] = fit_widget(w, chars, max_len)
    seen = set()
    for w in root.findChildren(QWidget):
        if w.layout() is not None:
            _add_trailing_space(w.layout(), seen)
    return widths


def fit_combo_to_current(combo, min_text: str = "0000000000") -> int:
    """v1.8.0: menus da tela principal com a largura do texto escolhido (não esticados na linha toda).

    A lista aberta fica pelo menos tão larga quanto a opção mais longa, para nada aparecer cortado."""
    text = combo.currentText() or min_text
    width = max(_advance(combo, text), _advance(combo, min_text)) + COMBO_PADDING
    combo.setFixedWidth(width)
    count = combo.count()
    if count and count <= 3000 and getattr(combo, "_pt2vhf_popup_count", None) != count:
        widest = max(_advance(combo, combo.itemText(i)) for i in range(count))
        combo.view().setMinimumWidth(widest + COMBO_PADDING)
        combo._pt2vhf_popup_count = count
    return width


class _RefitOnFont(QObject):
    def __init__(self, combo, min_text):
        super().__init__(combo)
        self.combo, self.min_text = combo, min_text

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.FontChange, QEvent.StyleChange, QEvent.Show):
            QTimer.singleShot(0, lambda: fit_combo_to_current(self.combo, self.min_text))
        return False


def keep_combo_fitted(combo, min_text: str = "0000000000"):
    """Reajusta ao trocar a opção (mesmo com sinais do combo bloqueados), a lista ou a fonte/tema."""
    refit = lambda *_: QTimer.singleShot(0, lambda: fit_combo_to_current(combo, min_text))
    combo.currentTextChanged.connect(refit)
    model = combo.model()
    for sig in (model.rowsInserted, model.rowsRemoved, model.modelReset, model.dataChanged):
        sig.connect(refit)
    combo._pt2vhf_refit = _RefitOnFont(combo, min_text)
    combo.installEventFilter(combo._pt2vhf_refit)
    fit_combo_to_current(combo, min_text)
