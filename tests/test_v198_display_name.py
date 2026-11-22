"""v1.9.8 (22/11/2026): IO-86 aparecia só como "LAPAN-A2" nas listas; agora "IO-86 (LAPAN-A2)"."""
import os
import subprocess
import sys
import textwrap

from sat_tool.catalog import display_name


def test_display_name_adds_oscar_designation():
    assert display_name("40931", {"OBJECT_NAME": "LAPAN-A2"}) == "IO-86 (LAPAN-A2)"
    assert display_name("40931", {"OBJECT_NAME": "IO-86"}) == "IO-86"
    assert display_name("27607", {"OBJECT_NAME": "SAUDISAT 1C (SO-50)"}) == "SAUDISAT 1C (SO-50)"
    assert display_name("25544", {"OBJECT_NAME": "ISS (ZARYA)"}) == "ISS (ZARYA)"
    assert display_name("12345", {"OBJECT_NAME": "FOO", "ALT_NAMES": ["XW-3"]}) == "XW-3 (FOO)"
    assert display_name("12345", {"OBJECT_NAME": "FOO", "ALT_NAMES": ["FOO-BAR SAT"]}) == "FOO"


def test_operation_list_shows_io86():
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
        gui.MainWindow.check_for_updates=lambda self:None
        L1="1 40931U 15052B   26325.50000000  .00000500  00000-0  20000-4 0  9990"
        L2="2 40931   6.0000 100.0000 0013000 200.0000 160.0000 14.76000000123456"
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); app.processEvents()
            w.background=lambda key,fn:None
            from sat_tool.catalog import tle_to_omm
            obj=tle_to_omm({"NORAD_CAT_ID":40931,"OBJECT_NAME":"LAPAN-A2","TLE_LINE1":L1,"TLE_LINE2":L2})
            obj["CATEGORIES"]=["defaults"]
            w.populate_catalog([obj])
            texts=[w.sat_combo.itemText(i) for i in range(w.sat_combo.count())]
            assert any(t.startswith("IO-86 (LAPAN-A2)") for t in texts), texts
            w.refresh_satellite_table()
            assert w.catalog_table.item(0,0).text()=="IO-86 (LAPAN-A2)"
        print("OK")
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr
