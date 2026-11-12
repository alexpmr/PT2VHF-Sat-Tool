"""v1.7.2 (bug 12/11/2026): tecla RX ONLY do display parecia sempre ligada; agora mostra o estado."""
import os
import subprocess
import sys
import textwrap


def test_rx_only_key_shows_state_and_toggles():
    source = textwrap.dedent(r'''
        import tempfile
        from pathlib import Path
        from sat_tool import app as gui, lcd
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
            w=gui.MainWindow(); w.show(); app.processEvents()
            assert not w.config.values.get("rx_only",False) and not w.lcd.state.rx_only
            w.lcd.rx_only_clicked.emit()
            assert w.config.values["rx_only"] and w.lcd.state.rx_only
            w.lcd.rx_only_clicked.emit()
            assert not w.config.values["rx_only"] and not w.lcd.state.rx_only
        # a tecla só fica "acesa" (preenchida) com RX ONLY ligado, em todos os modelos
        seen = {}
        for model in ("matriz", "led7", "lcd7", "digital", "classico", "ic706", "ic7100", "ft897", "ic910", "ft991", "ic9700"):
            for on in (False, True):
                disp = lcd.LcdDisplay(model=model)
                disp.set_state(rx_hz=436795100, tx_hz=None if on else 145850000, rx_only=on)
                captured = []
                for cls in {lcd._Style, lcd._Matrix}:
                    orig = cls.key
                    def spy(self, x, y, s, _o=orig):
                        captured.append((s, s in getattr(self, "active_keys", set())))
                        return _o(self, x, y, s)
                    cls.key = spy
                disp.render_image(1000, 150, 1.0)
                import importlib
                rx = [a for s, a in captured if s == "RX ONLY"]
                assert rx and rx[0] is on, (model, on, captured)
                importlib.reload(lcd)   # desfaz o espião
    ''')
    r = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert r.returncode == 0, r.stdout + r.stderr
