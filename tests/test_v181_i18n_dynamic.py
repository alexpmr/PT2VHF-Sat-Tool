"""v1.8.1: textos escritos em tempo de execução (estados, dicas, mensagens, tabelas, mapa) no idioma escolhido."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from sat_tool import i18n_runtime
from sat_tool.i18n import LANGUAGES, TRANSLATIONS

DYNAMIC = Path(__file__).resolve().parents[1] / "sat_tool" / "locales" / "dynamic"


def test_dynamic_catalog_is_aligned_in_every_language():
    source = json.loads((DYNAMIC / "source.pt-BR.json").read_text(encoding="utf-8"))
    assert len(source) > 700 and len(set(source)) == len(source)
    for code in LANGUAGES:
        if code == "pt-BR":
            continue
        values = json.loads((DYNAMIC / f"{code}.json").read_text(encoding="utf-8"))
        assert len(values) == len(source), code
        for src, dst in zip(source, values):
            assert isinstance(dst, str) and dst.strip(), (code, src)
            assert src.count("{}") == dst.count("{}"), (code, src, dst)
        # todo trecho do catálogo dinâmico chega à tabela do idioma (o catálogo estático tem prioridade)
        assert all(s in TRANSLATIONS[code] for s in source), code


def test_every_language_has_the_same_keys():
    keys = set().union(*(set(TRANSLATIONS[c]) for c in LANGUAGES if c != "pt-BR"))
    for code in LANGUAGES:
        if code != "pt-BR":
            assert not keys - set(TRANSLATIONS[code]), (code, sorted(keys - set(TRANSLATIONS[code]))[:5])


def test_tr_handles_templates_pieces_html_and_capitals():
    tr = i18n_runtime.tr
    assert tr("Posição anterior: {}", "en") == "Previous position: {}"
    assert tr("ISS · elevação 12.3° · alcance 1500 km · órbita TLE/OMM", "en") == \
        "ISS · elevation 12.3° · range 1500 km · TLE/OMM orbit"
    assert tr("RTL-SDR: Nenhum RTL-SDR conectado", "en") == "RTL-SDR: No RTL-SDR connected"
    assert tr("ROTOR · Yaesu G-5400B via sem porta", "en") == "ROTOR · Yaesu G-5400B via no port"
    assert tr("<br><b>Próxima passagem:</b> 12:00", "en") == "<br><b>Next pass:</b> 12:00"
    assert tr("Buscando informações…<br>", "de") == "Informationen werden abgerufen…<br>"
    assert tr("PRÓXIMA PASSAGEM DO SATÉLITE SELECIONADO · CONTAGEM REGRESSIVA", "en") == \
        "NEXT PASS OF THE SELECTED SATELLITE · COUNTDOWN"
    assert tr("Última passagem", "ja") != "Última passagem"
    assert tr("Texto que não existe", "en") == "Texto que não existe"
    assert tr("Operação", "pt-BR") == "Operação"


def test_map_page_and_rotor_compass_follow_the_language():
    html = (Path(i18n_runtime.__file__).with_name("map.html")).read_text(encoding="utf-8")
    page = i18n_runtime.translate_page(html, locale="fr")
    assert not [t for t in i18n_runtime.MAP_TEXTS if t.strip('"') in page]
    assert "Dézoomer" in page and "MARQUER LA STATION" in page
    assert i18n_runtime.translate_page(html, locale="pt-BR") == html
    from sat_tool import rotor_widgets
    i18n_runtime.set_locale("en")
    try:
        assert [rotor_widgets.cardinal(lab) for lab, _ in rotor_widgets.CARDINALS] == ["N", "E", "S", "W"]
        i18n_runtime.set_locale("de")
        assert rotor_widgets.cardinal("L") == "O" and rotor_widgets.cardinal("O") == "W"
    finally:
        i18n_runtime.set_locale("pt-BR")
    assert [rotor_widgets.cardinal(lab) for lab, _ in rotor_widgets.CARDINALS] == ["N", "L", "S", "O"]


def test_window_in_english_shows_no_catalogued_portuguese_and_switches_back():
    source = textwrap.dedent(r'''
        import tempfile, re
        from pathlib import Path
        from sat_tool import app as gui, i18n_runtime
        from sat_tool.config import Config
        from sat_tool.i18n import TRANSLATIONS
        from PySide6.QtWidgets import QAbstractButton, QLabel, QGroupBox, QComboBox, QLineEdit, QWidget
        class FakeWeb(gui.QWidget):
            def setHtml(self,*a,**k):pass
            def page(self):return self
            def runJavaScript(self,*a,**k):pass
            def reload(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda d:[]
        gui.MainWindow.background=lambda self,key,fn:None
        gui.MainWindow.check_for_updates=lambda self:None
        gui.MainWindow.show_official_site_notice=lambda self:None
        def texts(w):
            out=[w.toolTip(),w.windowTitle()]
            if isinstance(w,(QAbstractButton,QLabel)):out.append(w.text())
            if isinstance(w,QGroupBox):out.append(w.title())
            if isinstance(w,QLineEdit):out.append(w.placeholderText())
            if isinstance(w,QComboBox):out+=[w.itemText(i) for i in range(w.count())]
            return [t for t in out if t]
        def portuguese(win,code):
            table=TRANSLATIONS[code]; bad=set()
            for w in [win]+win.findChildren(QWidget):
                for t in texts(w):
                    for piece in re.split(r"\n| · ",re.sub("<[^>]+>","\n",t)):
                        piece=piece.strip()
                        if piece in table and table[piece]!=piece:bad.add(piece)
            return bad
        with tempfile.TemporaryDirectory() as d:
            cfg=Config(Path(d)); cfg.values["language"]="en"; cfg.save()
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.show(); app.processEvents()
            assert i18n_runtime.locale()=="en"
            bad=portuguese(w,"en")
            assert not bad, sorted(bad)[:10]
            # texto escrito depois da abertura também sai traduzido, e volta ao português na troca
            w.trail_period.setCurrentIndex(w.trail_period.findData("Personalizado")); app.processEvents()
            assert w.trail_period.currentText()=="Custom" and not w.trail_custom.isHidden()
            w.set_language("pt-BR"); app.processEvents()
            assert w.trail_period.currentText()=="Personalizado" and w.trail_period.currentData()=="Personalizado"
            assert not [t for t in [w.tabs.tabText(0)] if t!="Operação"]
            w.set_language("ja"); app.processEvents()
            bad=portuguese(w,"ja")
            assert not bad, sorted(bad)[:10]
            assert w.trail_period.currentData()=="Personalizado"
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=180,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stdout + result.stderr
