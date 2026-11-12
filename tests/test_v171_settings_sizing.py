"""v1.7.1: menus e campos das Configurações do tamanho do conteúdo (janela construída em processo próprio)."""
import subprocess
import sys
import textwrap


def test_settings_controls_are_sized_by_content():
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
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.resize(1920,1080); w.show(); app.processEvents()
            w.open_settings("Estação"); app.processEvents()
            assert w.callsign.maxLength()==12 and w.grid_locator.maxLength()==10
            assert w.callsign.width()<200, w.callsign.width()
            assert w.lat.width()<200 and w.min_el.width()<160
            w.open_settings("Aparência"); app.processEvents()
            fm=w.display_model.fontMetrics()
            longest=max(fm.horizontalAdvance(w.display_model.itemText(i)) for i in range(w.display_model.count()))
            assert longest < w.display_model.width() < longest+120
            w.open_settings("Rotor"); app.processEvents()
            assert w.rotor_az_max.width()<160 and w.rotor_port.width()<320
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
