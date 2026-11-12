"""v1.8.0 (backlog 12/11/2026): menus da tela principal do tamanho do texto; CAT/SDR/ROTOR do mesmo tamanho."""
import os
import subprocess
import sys
import textwrap


def test_combos_fit_text_and_top_buttons_match():
    source = textwrap.dedent(r'''
        import tempfile
        from pathlib import Path
        from sat_tool import app as gui
        from sat_tool.config import Config
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
        gui.MainWindow.startup_refresh_catalog=lambda self:None
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.resize(1600,900); w.show()
            for _ in range(20): app.processEvents()
            c=w.sat_combo
            c.blockSignals(True); c.addItem("SAUDISAT 1C (SO-50)  ·  27607","27607"); c.setCurrentIndex(0); c.blockSignals(False)
            for _ in range(5): app.processEvents()
            text=c.fontMetrics().horizontalAdvance(c.currentText())
            assert text < c.width() < text + 80, (text, c.width())
            c.addItem("X"*80,"1")
            for _ in range(5): app.processEvents()
            assert c.width() < text + 80 and c.view().minimumWidth() > c.width()   # a lista mostra a opção longa
            sizes={(b.width(),b.height()) for b in (w.cat_indicator,w.sdr_toggle,w.rotor_top_btn)}
            assert len(sizes)==1, sizes
            h=w.cat_indicator.height()
            assert w.language_menu_button.height()==h and w.utc.height()==h
            w.apply_appearance()
            for _ in range(5): app.processEvents()
            assert len({(b.width(),b.height()) for b in (w.cat_indicator,w.sdr_toggle,w.rotor_top_btn)})==1
            assert w.catalog_search.maximumWidth() < 1000
    ''')
    r = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert r.returncode == 0, r.stdout + r.stderr
