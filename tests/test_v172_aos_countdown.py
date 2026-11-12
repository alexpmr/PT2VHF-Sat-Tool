"""v1.7.2 (backlog 12/11/2026): ao se aproximar o AOS, só uma contagem regressiva que fecha sozinha no início."""
import os
import subprocess
import sys
import textwrap


def test_aos_window_is_only_a_countdown_and_closes_at_aos():
    source = textwrap.dedent(r'''
        import tempfile
        from datetime import timedelta
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
            w=gui.MainWindow(); w.show(); app.processEvents()
            sounds=[]
            w.play_aos_sound=lambda critical=False:sounds.append(critical)
            now=gui.now_utc()
            row={"name":"SO-50","id":27607,"aos":now+timedelta(seconds=8.5),"max_el":42}
            w._open_aos_countdown(row,8.5)
            dlg=w.aos_alarm_dialog
            assert dlg is not None and dlg.isVisible()
            assert dlg.findChildren(gui.QPushButton)==[]          # nada a perguntar
            assert w.aos_alarm_count.text()=="0:09" and "SO-50" in w.aos_alarm_title.text()
            w._update_aos_countdown(now+timedelta(seconds=5)); assert w.aos_alarm_count.text()=="0:04"
            w._update_aos_countdown(now+timedelta(seconds=9)); app.processEvents()
            assert w.aos_alarm_dialog is None and not dlg.isVisible()   # fechou no AOS
            assert sounds[-1] is True                                   # som do AOS
            # já em visada: não abre janela
            late={"name":"SO-50","id":27607,"aos":now-timedelta(seconds=2),"max_el":42}
            w._open_aos_countdown(late,-2)
            assert w.aos_alarm_dialog is None
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stdout + result.stderr
