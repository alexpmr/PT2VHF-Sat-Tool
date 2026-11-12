"""v1.7.2 (backlog 12/11/2026): ao abrir, TLE/OMM atualizados em segundo plano, sem janela modal."""
import os
import subprocess
import sys
import textwrap


def test_startup_refreshes_tle_in_background_without_dialog():
    source = textwrap.dedent(r'''
        import tempfile, time
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
        jobs=[]
        gui.MainWindow.background=lambda self,key,fn:jobs.append(key)
        gui.MainWindow.check_for_updates=lambda self:None
        gui.MainWindow.show_official_site_notice=lambda self:None
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.show()
            end=time.monotonic()+3
            while "omm" not in jobs and time.monotonic()<end:
                app.processEvents(); time.sleep(0.05)
            assert "omm" in jobs, jobs
            assert w.orbit_progress_dialog is None
            assert gui.QApplication.activeModalWidget() is None
            assert "segundo plano" in w.summary.text(), w.summary.text()
            w.background_result("omm-stage",(3,7,"amateur",40,0))
            assert w.summary.text().endswith("3/7"), w.summary.text()
    ''')
    r = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert r.returncode == 0, r.stdout + r.stderr
