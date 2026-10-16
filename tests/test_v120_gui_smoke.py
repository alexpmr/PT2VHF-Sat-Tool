"""Construct the v1.2.0 window in a fresh process.

The existing thread-safety tests use QCoreApplication. Qt does not allow QWidget
construction using that instance, so the GUI smoke runs in a separate process.
"""
import subprocess
import sys
import textwrap


def test_operator_window_constructs_with_new_layout():
    source=textwrap.dedent(r'''
        import tempfile
        from pathlib import Path
        from sat_tool import app as gui
        from sat_tool.config import Config

        class FakeWeb(gui.QWidget):
            def setHtml(self,*args,**kwargs):pass
            def page(self):return self
            def runJavaScript(self,*args,**kwargs):pass
            def reload(self):pass

        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda directory:[]
        gui.MainWindow.background=lambda self,key,fn:None
        gui.MainWindow.check_for_updates=lambda self:None

        with tempfile.TemporaryDirectory() as directory:
            gui.Config=lambda:Config(Path(directory))
            application=gui.QApplication([])
            window=gui.MainWindow()
            assert window.tabs.count()==5
            assert window.pred_rx.minimumHeight()>=100
            assert window.pred_tx.minimumHeight()>=100
            assert window.mode_combo.parent() is not None
            assert window.ports.parent() is not None
            assert window.cat_rx.parent() is not None
            assert window.tracked_search.parent() is not None
            assert window.connection.text()=="Conectar"
            assert window.cat_tune_now.text()=="Sintonizar agora"
            assert not window.cat_tune_now.isEnabled()
            assert window.cat_tune_status.text().startswith("Auto CAT")
            # A write/readback error must not re-label a responsive CAT link
            # as disconnected; the link is verified with a read-only poll.
            class FakePort:
                is_open=True
                def close(self):self.is_open=False
            window.radio.port=FakePort()
            window.cat_indicator.setText("● TS-2000 CONECTADO · COM1")
            observed_jobs=[]
            window.background=lambda key, fn: observed_jobs.append(key)
            window.background_error("cat-autotune","Rádio não confirmou frequências FA/FC")
            assert "CONECTADO" in window.cat_indicator.text()
            assert "SINTONIA NÃO APLICADA" in window.cat_tune_status.text()
            assert "FA/FC" in window.cat_tune_status.text()
            assert "cat-poll" in observed_jobs
            # A *real* closed port may be marked disconnected.
            window.radio.port=None
            window.background_error("cat-autotune","TS-2000 desconectado")
            assert "DESCONECTADO" in window.cat_indicator.text()
            window.tracked_search.setText("ISS")
            assert window.tracked_search_summary.text().startswith("0 resultados")
            window.tick_timer.stop()
            window.diagnostic_timer.stop()
            window.close()
    ''')
    result=subprocess.run([sys.executable,"-c",source],text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
    assert result.returncode==0, result.stdout+"\n"+result.stderr
