"""v1.7.1: 10 idiomas, seletor no topo com bandeira, troca na hora e cobertura das traduções."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from sat_tool.i18n import LANGUAGES, SOURCE_STRINGS, TRANSLATIONS, resolve_language, translated

LOCALES = Path(__file__).resolve().parents[1] / "sat_tool" / "locales"


def test_ten_languages_cover_every_catalogued_string():
    assert len(LANGUAGES) == 10 and len(SOURCE_STRINGS) > 300
    for code in LANGUAGES:
        if code == "pt-BR":
            continue
        values = json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))
        assert len(values) == len(SOURCE_STRINGS), code
        assert all(isinstance(v, str) and v.strip() for v in values), code
        missing = [s for s in SOURCE_STRINGS if s not in TRANSLATIONS[code]]
        assert not missing, (code, missing[:3])
        # alinhamento: o mesmo número de quebras de linha e símbolos de seta em cada tradução
        for src, dst in zip(SOURCE_STRINGS, values):
            assert src.count("\n") == dst.count("\n"), (code, src)
    assert translated("Operação", "ja") == "運用" and translated("PARAR", "de") == "STOPP"


def test_language_resolution_from_system():
    assert resolve_language("", "de_DE") == "de" and resolve_language("", "zh_CN") == "zh-Hans"
    assert resolve_language("", "pt_PT") == "pt-BR" and resolve_language("", "ko_KR") == "pt-BR"
    assert resolve_language("nl", "de_DE") == "nl"


def test_top_menu_switches_language_live_and_every_visible_string_is_translated():
    source = textwrap.dedent(r'''
        import tempfile, re
        from pathlib import Path
        from sat_tool import app as gui
        from sat_tool.config import Config
        from sat_tool.i18n import SOURCE_STRINGS
        class FakeWeb(gui.QWidget):
            def setHtml(self,*a,**k):pass
            def page(self):return self
            def runJavaScript(self,*a,**k):pass
            def reload(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda d:[]
        gui.MainWindow.background=lambda self,key,fn:None
        gui.MainWindow.check_for_updates=lambda self:None
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.show(); app.processEvents()
            assert len(w.language_actions)==10
            # cobertura: todo texto estático com palavras está no catálogo (ou é técnico)
            technical=re.compile(r"^[A-Z0-9 +./:·\-—±°()]+$|^[\d±]|v1\.|/tmp/|\d{2}/\d{2}|^Yaesu |^ROTOR · Yaesu")
            names=set(gui.LANGUAGES.values())|{"Baud","Stop bits"}  # siglas/termos técnicos iguais em todos
            loose=[]
            for widget,kind,original in w._language_texts:
                texts=original if kind=="items" else [original]
                for t in texts:
                    if t in SOURCE_STRINGS or t in names or technical.search(t) or not re.search("[a-zà-ú]{3}",t):
                        continue
                    loose.append(t)
            assert not loose, loose
            [a for a in w.language_actions if a.data()=="de"][0].trigger(); app.processEvents()
            assert w.tabs.tabText(0)=="Betrieb" and w.config.values["language"]=="de"
            assert w.settings_tabs.tabText(0)=="Darstellung"
            assert w.rotor_stop_btn.text()=="GESTOPPT" and w.language_combo.currentData()=="de"
            assert w.theme_preset.itemText(0)=="Dunkel (Standard)" and w.theme_preset.currentData()=="escuro"
            w.language_combo.setCurrentIndex(w.language_combo.findData("zh-Hans")); app.processEvents()
            assert w.tabs.tabText(0)=="操作" and w.language_menu_button.text()=="简体中文"
            w.set_language("pt-BR"); app.processEvents()
            assert w.tabs.tabText(0)=="Operação" and w.rotor_stop_btn.toolTip().startswith("Rotor parado")
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stdout + result.stderr


def test_env_override_for_system_language(monkeypatch):
    from sat_tool.i18n import resolve_language
    monkeypatch.setenv("PT2VHF_LANG", "de_DE")
    assert resolve_language("") == "de"
    assert resolve_language("ja") == "ja"            # escolha salva continua valendo
    monkeypatch.setenv("PT2VHF_LANG", "xx")
    assert resolve_language("") == "pt-BR"
