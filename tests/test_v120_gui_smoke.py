"""Real Qt QWidget construction smoke test for both Win7/PySide2 and Win11/PySide6.

The WebEngine frame is replaced only during this test to avoid Chromium/headless
system dependencies. All other widgets and layout logic are instantiated for real.
"""


def test_window_constructs_with_reorganized_widgets(tmp_path, monkeypatch):
    from sat_tool import app as gui
    from sat_tool.config import Config

    class FakeWeb(gui.QWidget):
        def setHtml(self, *args, **kwargs):
            pass
        def page(self):
            return self
        def runJavaScript(self, *args, **kwargs):
            pass
        def reload(self):
            pass

    monkeypatch.setattr(gui,"QWebEngineView",FakeWeb)
    monkeypatch.setattr(gui,"Config",lambda:Config(tmp_path))
    monkeypatch.setattr(gui,"load_orbits",lambda directory:[])
    monkeypatch.setattr(gui.MainWindow,"background",lambda self,key,fn:None)
    monkeypatch.setattr(gui.MainWindow,"check_for_updates",lambda self:None)

    application=gui.QApplication.instance() or gui.QApplication([])
    window=gui.MainWindow()
    try:
        assert window.tabs.count()==5
        assert window.pred_rx.minimumHeight()>=100
        assert window.pred_tx.minimumHeight()>=100
        assert window.pred_rx.parent() is not None
        assert window.mode_combo.parent() is not None
        assert window.ports.parent() is not None
        assert window.cat_rx.parent() is not None
        assert window.tracked_search.parent() is not None
        assert window.connection.text()=="Conectar"
        window.tracked_search.setText("ISS")
        assert window.tracked_search_summary.text().startswith("0 resultados")
    finally:
        window.tick_timer.stop()
        window.diagnostic_timer.stop()
        window.close()
