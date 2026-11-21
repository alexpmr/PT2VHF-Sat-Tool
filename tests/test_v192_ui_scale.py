"""v1.9.2: ajuste proporcional da interface (aba Operação sem rolagem em telas baixas)."""
import os
import subprocess
import sys
import textwrap

from sat_tool import ui_scale


def test_choose_scale_from_screen_manual_and_learned():
    assert ui_scale.choose_scale("auto", 1040, None) == 1.0          # 1920×1080: sem redução
    s = ui_scale.choose_scale("auto", 728, None)                     # 1366×768 com barra de tarefas
    assert 0.8 <= s < 0.85
    assert ui_scale.choose_scale("auto", 600, None) == 0.8           # piso de 80 %
    assert ui_scale.choose_scale(0.9, 600, None) == 0.9              # escolha manual manda
    assert ui_scale.choose_scale(1.0, 600, None) == 1.0
    assert ui_scale.choose_scale("auto", None, {"scale": 0.87, "screen_h": 700}) == 0.87
    assert ui_scale.choose_scale("auto", 1040, {"scale": 0.87, "screen_h": 700}) == 1.0   # outra tela
    assert ui_scale.choose_scale("auto", None, None) == 1.0


def test_apply_sets_qt_scale_factor_and_respects_user_value(monkeypatch):
    monkeypatch.delenv("QT_SCALE_FACTOR", raising=False)
    monkeypatch.setattr(ui_scale, "windows_work_area_height", lambda: 728)
    s = ui_scale.apply_before_qt({"ui_scale": "auto"})
    assert os.environ["QT_SCALE_FACTOR"] == f"{s:.2f}" and s < 1
    monkeypatch.setenv("QT_SCALE_FACTOR", "1.25")
    assert ui_scale.apply_before_qt({"ui_scale": 0.8}) == 1.25
    monkeypatch.delenv("QT_SCALE_FACTOR")
    monkeypatch.setattr(ui_scale, "windows_work_area_height", lambda: 1040)
    assert ui_scale.apply_before_qt({"ui_scale": "auto"}) == 1.0 and "QT_SCALE_FACTOR" not in os.environ


def run_gui(source, scale=None):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    env.pop("QT_SCALE_FACTOR", None)
    if scale:
        env["QT_SCALE_FACTOR"] = f"{scale:.2f}"
    result = subprocess.run([sys.executable, "-c", textwrap.dedent(PRELUDE) + textwrap.dedent(source)],
                            capture_output=True, text=True, timeout=180, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


PRELUDE = r'''
    import tempfile, json
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
    def overflow(w):
        s=w.operation_scroll
        return s.widget().height()-s.viewport().height()
'''


def test_operation_tab_fits_1366x768_laptop_with_proportional_scale():
    """Notebook 1366×768: 728 px úteis (barra de tarefas), 31 de barra de título → 697 px físicos de janela."""
    scale = ui_scale.choose_scale("auto", 728, None)
    run_gui(f'''
    with tempfile.TemporaryDirectory() as d:
        gui.Config=lambda:Config(Path(d))
        app=gui.QApplication([])
        w=gui.MainWindow(); w.show()
        w.resize(int(1366/{scale}), int(697/{scale}))
        for _ in range(20): app.processEvents()
        assert overflow(w) <= 0, overflow(w)
    ''', scale)
    # sem o ajuste, a mesma tela rola
    run_gui('''
    with tempfile.TemporaryDirectory() as d:
        gui.Config=lambda:Config(Path(d))
        app=gui.QApplication([])
        w=gui.MainWindow(); w.show(); w.resize(1366,697)
        for _ in range(20): app.processEvents()
        assert overflow(w) > 50, overflow(w)
    ''')


def test_learns_scale_when_maximized_window_still_scrolls_and_settings_combo():
    run_gui('''
    with tempfile.TemporaryDirectory() as d:
        gui.Config=lambda:Config(Path(d))
        app=gui.QApplication([])
        w=gui.MainWindow(); w.show(); w.resize(1366,697)
        for _ in range(20): app.processEvents()
        w.isMaximized=lambda:True
        w.check_ui_scale()
        learned=w.config.values["ui_scale_learned"]
        assert 0.8 <= learned["scale"] < 0.9, learned
        saved=json.loads((Path(d)/"settings.json").read_text(encoding="utf-8"))
        assert saved["ui_scale_learned"]["scale"]==learned["scale"]
        combo=w.ui_scale_combo
        assert combo.currentData()=="auto"
        combo.setCurrentIndex(combo.findData(0.9))
        assert w.config.values["ui_scale"]==0.9 and w.config.values["ui_scale_learned"]=={}
        assert "reabrir" in w.theme_status.text()
        from sat_tool import ui_scale
        assert ui_scale.apply_before_qt.__name__
        assert ui_scale.choose_scale(Config(Path(d)).values["ui_scale"], 1040, None)==0.9
    ''')
