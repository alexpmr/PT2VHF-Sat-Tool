"""v1.7.1 (bug relatado em 11/11/2026): painel SDR fechado voltava a aparecer segundos depois.

A detecção do RTL-SDR (a cada 5 s) reabria o painel enquanto houvesse dongle conectado."""
import os
import subprocess
import sys
import textwrap


def test_sdr_dock_does_not_reopen_after_operator_hides_it():
    source = textwrap.dedent(r'''
        import tempfile
        from pathlib import Path
        from sat_tool import app as gui, sdr
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
        sdr.detect_devices=lambda:([sdr.SdrDevice(0,"RTL2838 (teste)")],"ok")
        gui.QMessageBox.question=staticmethod(lambda *a,**k:gui.QMessageBox.No)
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.show(); app.processEvents()
            panel=w.sdr_panel
            # cenário do operador: RTL-SDR escolhido para RX (sem pergunta), receptor desligado por ele
            w.config.values.update(rx_device="SDR",sdr_user_stopped=True)
            panel.detect(); app.processEvents()
            assert w.sdr_dock.isVisible()                 # primeira detecção mostra o painel
            w.toggle_sdr_dock(); app.processEvents()      # operador desliga o painel
            assert not w.sdr_dock.isVisible()
            for _ in range(5):                            # detecções seguintes (antes: reabria)
                panel.detect(); app.processEvents()
            assert not w.sdr_dock.isVisible() and w.config.values["sdr_dock_user_hidden"] is True
            w.toggle_sdr_dock(); app.processEvents()
            assert w.sdr_dock.isVisible() and w.config.values["sdr_dock_user_hidden"] is False
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
