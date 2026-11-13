"""v1.8.0 (backlog 12/11/2026): medidor de CPU e RAM na barra do topo, como no APRS Client."""
import os
import subprocess
import sys
import textwrap


def test_process_usage_reports_cpu_and_memory():
    from sat_tool.resource_meter import ProcessUsage
    u = ProcessUsage()
    sum(i * i for i in range(200000))
    assert 0.0 <= u.cpu_percent() <= 100.0
    assert u.rss_bytes() > 10 * 1048576
    assert u.total_bytes() > u.rss_bytes()


def test_meter_in_top_bar_with_values():
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
            for _ in range(10): app.processEvents()
            m=w.resource_meter
            assert m.isVisible() and m.timer.isActive()
            assert m.x() < w.cat_indicator.x() and m.parentWidget() is w.cat_indicator.parentWidget()
            m.sample()
            t=m.text()
            assert t.startswith("CPU ") and "% · RAM " in t and t.endswith(" MB") and m.rss > 0, t
            img=m.grab().toImage()
            assert img.width()==m.width() and m.height()>=w.cat_indicator.height()
    ''')
    r = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert r.returncode == 0, r.stdout + r.stderr
