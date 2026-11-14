"""v1.8.1: tradução dos textos dinâmicos da interface (backlog 13/11/2026: "muitas coisas estão em idioma errado").

Antes só os textos fixos da criação da janela eram traduzidos; tudo o que o programa escrevia depois (linhas de
estado, tooltips, avisos, tabelas, janelas abertas mais tarde) ficava em português. Aqui os métodos do Qt que põem
texto na tela (setText, setToolTip, setTitle, QMessageBox…) passam pelo catálogo do idioma escolhido:

* texto exato do catálogo (``locales/*.json`` e ``locales/dynamic/*.json``);
* modelos com partes variáveis (``"{} satélites · OMM/TLE"``), cujas partes também são traduzidas;
* pedaços separados por " · ", quebras de linha e afins, cada um traduzido à parte;
* HTML: só o texto entre as tags.

O texto original (português) fica guardado no próprio widget, para trocar de idioma na hora sem reiniciar.
Nada muda em pt-BR. Textos de equipamento (frequências, modos, comandos CAT) não estão no catálogo e passam iguais.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from . import i18n

_STATE = {"locale": "pt-BR", "installed": False}
_TEMPLATES: dict = {}          # locale -> list[(regex, translated_template)]
_UPPER: dict = {}              # locale -> {TEXTO EM MAIÚSCULAS: TRADUÇÃO EM MAIÚSCULAS}
_SPLITTERS = ("\n", " · ", " • ", " — ", " | ", "; ", " – ")
_PROP = "_i18n_src_"           # propriedade Qt com o texto original de cada atributo
_ROLE = 0x0100 + 77            # Qt.UserRole + 77: original de itens de menus/tabelas


def _load_dynamic():
    """Catálogo dos textos dinâmicos: locales/dynamic/source.pt-BR.json + <idioma>.json alinhados por posição."""
    folder = Path(__file__).with_name("locales") / "dynamic"
    try:
        source = json.loads((folder / "source.pt-BR.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    for code in i18n.LANGUAGES:
        if code == "pt-BR":
            continue
        try:
            values = json.loads((folder / f"{code}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if len(values) == len(source):
            table = i18n.TRANSLATIONS.setdefault(code, {})
            for src, dst in zip(source, values):
                table.setdefault(src, dst)
    return source


DYNAMIC_STRINGS = _load_dynamic()


def _templates(locale):
    if locale not in _TEMPLATES:
        rows = []
        for src, dst in i18n.TRANSLATIONS.get(locale, {}).items():
            if "{}" not in src or src.count("{}") != dst.count("{}"):
                continue
            if len(re.findall(r"[^\W\d_]", src.replace("{}", ""))) < 3:
                continue   # modelo sem palavras (ex.: "{} MHz") não traduz nada
            literal = re.escape(src.replace("{{", "\0").replace("}}", "\1")).replace(r"\{\}", "(.+?)")
            literal = literal.replace("\0", r"\{").replace("\1", r"\}")
            rows.append((re.compile(literal + r"\Z", re.S), dst, len(src)))
        rows.sort(key=lambda r: -r[2])   # o modelo mais específico (mais longo) primeiro
        _TEMPLATES[locale] = [(rx, dst) for rx, dst, _ in rows]
    return _TEMPLATES[locale]


def _fill(template, parts):
    out, it = [], iter(parts)
    pieces = template.replace("{{", "\0").replace("}}", "\1").split("{}")
    for k, piece in enumerate(pieces):
        out.append(piece)
        if k < len(pieces) - 1:
            out.append(next(it, ""))
    return "".join(out).replace("\0", "{").replace("\1", "}")


@lru_cache(maxsize=8192)
def tr(text, locale=None):
    """Texto no idioma da interface (ou o próprio texto, quando não há tradução)."""
    locale = locale or _STATE["locale"]
    if not text or locale == "pt-BR" or not isinstance(text, str):
        return text
    table = i18n.TRANSLATIONS.get(locale, {})
    if text in table:
        return table[text]
    if "<" in text and ">" in text:
        return re.sub(r"(^|>)([^<>]+)(?=<|$)",
                      lambda m: m.group(1) + _keep_space(m.group(2), locale), text)
    stripped = text.strip()
    if stripped != text and stripped:
        return text.replace(stripped, tr(stripped, locale), 1)
    for sep in _SPLITTERS:   # primeiro os pedaços ("A · B" → cada um traduzido)
        if sep in text:
            parts = text.split(sep)
            new = [tr(p, locale) for p in parts]
            if new != parts:
                return sep.join(new)
    for rx, dst in _templates(locale):
        m = rx.match(text)
        if m:
            return _fill(dst, [tr(g, locale) for g in m.groups()])
    if text.isupper():   # títulos em CAIXA ALTA: procura a forma normal no catálogo
        upper = _upper_table(locale)
        if text in upper:
            return upper[text]
    head, colon, tail = text.partition(": ")
    if colon and tail:   # "Rótulo: valor" → rótulo e valor traduzidos separadamente
        if head + ":" in table:
            return table[head + ":"] + " " + tr(tail, locale)
        new_head, new_tail = tr(head, locale), tr(tail, locale)
        if (new_head, new_tail) != (head, tail):
            return new_head + ": " + new_tail
    if text.endswith((":", "…", ".")) and len(text) > 1 and text[:-1] in table:
        return table[text[:-1]] + text[-1]
    return text


def _upper_table(locale):
    if locale not in _UPPER:
        _UPPER[locale] = {src.upper(): dst.upper() for src, dst in i18n.TRANSLATIONS.get(locale, {}).items()}
    return _UPPER[locale]


def _keep_space(chunk, locale):
    core = chunk.strip()
    return chunk.replace(core, tr(core, locale), 1) if core else chunk


# textos fixos do mapa (map.html), trocados pela tradução ao carregar a página
MAP_TEXTS = ("Aguardando efemérides e estação configurada.", "Clique no mapa ou arraste o marcador",
             "geolocalização não disponível nesta origem/edição do navegador",
             "permissão negada ou localização indisponível", "━ Passado reconstruído", "╌ Futuro previsto",
             "● Satélite", "APRS via satélite", "Afastar mapa", "Aproximar mapa", "Sem dados orbitais",
             "MARCAR ESTAÇÃO", "NOVA ESTAÇÃO", "Depois confirme", "\"Estação\"", "\"Fechar\"", "\"Mostrar mundo\"")


def translate_page(html, texts=MAP_TEXTS, locale=None):
    """Página HTML/JS com os textos conhecidos no idioma da interface (aspas trocadas por tipográficas)."""
    for text in texts:
        quoted = text.startswith('"')
        core = text.strip('"')
        new = tr(core, locale).replace("'", "\u2019").replace('"', "\u201d").replace("<", "‹").replace(">", "›")
        html = html.replace(text, f'"{new}"' if quoted else new)
    return html


def set_locale(locale):
    _STATE["locale"] = locale if locale in i18n.LANGUAGES else "pt-BR"


def locale():
    return _STATE["locale"]


# ---------------------------------------------------------------- ganchos nos métodos do Qt
def _wrap_text_setter(cls, name, getter):
    real = getattr(cls, name)
    prop = _PROP + getter

    def setter(self, text, *rest):
        if isinstance(text, str):
            try:
                self.setProperty(prop, text)
            except (RuntimeError, AttributeError):
                pass
            text = tr(text)
        return real(self, text, *rest)
    setter.__wrapped_i18n__ = real
    setattr(cls, name, setter)


def _original(widget, getter):
    try:
        value = widget.property(_PROP + getter)
    except (RuntimeError, AttributeError):
        return None
    return value if isinstance(value, str) else None


def _wrap_messagebox(QMessageBox):
    for name in ("information", "warning", "critical", "question", "about"):
        real = getattr(QMessageBox, name)

        def make(real):
            def call(*args, **kwargs):
                args = [tr(a) if isinstance(a, str) else a for a in args]
                kwargs = {k: tr(v) if isinstance(v, str) else v for k, v in kwargs.items()}
                return real(*args, **kwargs)
            return staticmethod(call)
        setattr(QMessageBox, name, make(real))


def _wrap_combo(QComboBox):
    real_add, real_insert, real_set = QComboBox.addItem, QComboBox.insertItem, QComboBox.setItemText

    def has_data(args, text_pos):
        return len(args) > text_pos + 1   # menu com itemData (mesmo None): o código não compara o texto

    def add(self, *args, **kwargs):
        pos = 0 if args and isinstance(args[0], str) else 1
        if len(args) > pos and isinstance(args[pos], str) and (has_data(args, pos) or "userData" in kwargs):
            original = args[pos]
            args = list(args); args[pos] = tr(original)
            real_add(self, *args, **kwargs)
            self.setItemData(self.count() - 1, original, _ROLE)
            return None
        return real_add(self, *args, **kwargs)

    def insert(self, index, *args, **kwargs):
        pos = 0 if args and isinstance(args[0], str) else 1
        if len(args) > pos and isinstance(args[pos], str) and (has_data(args, pos) or "userData" in kwargs):
            original = args[pos]
            args = list(args); args[pos] = tr(original)
            real_insert(self, index, *args, **kwargs)
            self.setItemData(index if index >= 0 else self.count() - 1, original, _ROLE)
            return None
        return real_insert(self, index, *args, **kwargs)

    def set_text(self, index, text):
        if isinstance(text, str) and (self.itemData(index) is not None or self.itemData(index, _ROLE) is not None):
            self.setItemData(index, text, _ROLE)
            text = tr(text)
        return real_set(self, index, text)
    QComboBox.addItem, QComboBox.insertItem, QComboBox.setItemText = add, insert, set_text


def _translate_item(item):
    if item is None:
        return
    for role, getter, setter in ((_ROLE, "text", "setText"), (_ROLE + 1, "toolTip", "setToolTip")):
        current = getattr(item, getter)()
        if not current:
            continue
        original = item.data(role)
        if not isinstance(original, str):
            original = current
            item.setData(role, original)
        new = tr(original)
        if new != current:
            getattr(item, setter)(new)


def _wrap_table(QTableWidget):
    real = QTableWidget.setItem

    def set_item(self, row, column, item):
        _translate_item(item)
        return real(self, row, column, item)
    QTableWidget.setItem = set_item


def install(qt):
    """Liga a tradução dinâmica (uma vez). ``qt`` é o módulo qt_compat."""
    if _STATE["installed"]:
        return
    _STATE["installed"] = True
    from .qt_compat import QT_BINDING
    if QT_BINDING == "PySide6":
        from PySide6.QtWidgets import QAbstractButton, QWidget, QGroupBox, QLineEdit, QLabel, QProgressDialog, QTabWidget
        from PySide6.QtGui import QAction
    else:  # pragma: no cover
        from PySide2.QtWidgets import QAbstractButton, QWidget, QGroupBox, QLineEdit, QLabel, QProgressDialog, QTabWidget, QAction
    _wrap_text_setter(QLabel, "setText", "text")
    _wrap_text_setter(QAbstractButton, "setText", "text")
    _wrap_text_setter(QWidget, "setToolTip", "toolTip")
    _wrap_text_setter(QWidget, "setWindowTitle", "windowTitle")
    _wrap_text_setter(QGroupBox, "setTitle", "title")
    _wrap_text_setter(QLineEdit, "setPlaceholderText", "placeholderText")
    _wrap_text_setter(QProgressDialog, "setLabelText", "labelText")
    _wrap_text_setter(qt.QMessageBox, "setText", "text")
    _wrap_text_setter(qt.QMessageBox, "setInformativeText", "informativeText")
    _wrap_text_setter(QAction, "setText", "text")
    _wrap_text_setter(QAction, "setToolTip", "toolTip")
    real_tab = QTabWidget.setTabText
    QTabWidget.setTabText = lambda self, i, text: real_tab(self, i, tr(text) if isinstance(text, str) else text)
    _wrap_messagebox(qt.QMessageBox)
    _wrap_combo(qt.QComboBox)
    _wrap_table(qt.QTableWidget)


_ATTRS = (("text", "setText"), ("toolTip", "setToolTip"), ("windowTitle", "setWindowTitle"),
          ("title", "setTitle"), ("placeholderText", "setPlaceholderText"))


def translate_widget(widget, *, adopt=True):
    """Traduz um widget criado com texto no construtor (ou retraduz ao trocar de idioma).
    adopt=True: um texto sem original guardado é tratado como original (português, vindo do código)."""
    for getter, setter in _ATTRS:
        get = getattr(widget, getter, None)
        if get is None or not hasattr(widget, setter):
            continue
        if getter == "text" and not hasattr(widget, "setText"):
            continue
        try:
            current = get()
        except (RuntimeError, TypeError):
            continue
        if not isinstance(current, str):
            continue
        original = _original(widget, getter)
        if original is None:
            if not current or not adopt:
                continue
            original = current
        if tr(original) != current or original != current:
            getattr(widget, setter)(original)   # o setter com gancho guarda o original e traduz
    combo_items(widget)
    table_items(widget)


def combo_items(widget):
    if not (hasattr(widget, "itemData") and hasattr(widget, "count") and hasattr(widget, "setItemText")):
        return
    for i in range(widget.count()):
        if widget.itemData(i) is None:
            continue
        original = widget.itemData(i, _ROLE)
        if isinstance(original, str):
            widget.setItemText(i, original)


def table_items(widget):
    if not (hasattr(widget, "rowCount") and hasattr(widget, "columnCount") and hasattr(widget, "item")):
        return
    for r in range(widget.rowCount()):
        for c in range(widget.columnCount()):
            _translate_item(widget.item(r, c))


def retranslate_all(app, adopt=False):
    """Troca de idioma: todos os widgets abertos voltam ao original e são traduzidos de novo.
    adopt=True (saindo do português): textos de construtor ainda sem original guardado também são traduzidos."""
    tr.cache_clear()
    from .qt_compat import QWidget
    for top in app.topLevelWidgets():
        for widget in [top] + top.findChildren(QWidget):
            translate_widget(widget, adopt=adopt)


class PolishTranslator:
    """Filtro de eventos do app: ao "polir" (antes de mostrar) cada widget novo, traduz os textos do construtor."""

    def __init__(self, app):
        from .qt_compat import QObject

        class _Filter(QObject):
            def eventFilter(inner, obj, event):
                try:
                    if event.type() == _POLISH and _STATE["locale"] != "pt-BR":
                        translate_widget(obj)
                except Exception:
                    pass
                return False
        try:
            from PySide6.QtCore import QEvent
        except ImportError:  # pragma: no cover
            from PySide2.QtCore import QEvent
        global _POLISH
        _POLISH = QEvent.Polish
        self.filter = _Filter()
        app.installEventFilter(self.filter)


_POLISH = None
