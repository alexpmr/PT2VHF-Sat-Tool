"""v1.7.1: Configurações → Aparência (tema, brilho, contraste, destaque, fonte) aplicado na hora."""
import os
import subprocess
import sys
import textwrap

from sat_tool.appearance import (DEFAULTS, PRESETS, contrast_ratio, is_alert, text_contrast, transform,
                                 transform_qss)


def test_default_is_identity_and_presets_stay_readable():
    from sat_tool.app import STYLE
    assert transform_qss(STYLE, DEFAULTS) == STYLE
    for preset in PRESETS:
        assert text_contrast({"theme_preset": preset}) >= 4.5, preset
    light = transform("#0b1526", {"theme_preset": "claro"})
    assert contrast_ratio(light, "#000000") > 10           # fundo claro


def test_alerts_keep_hue_and_low_contrast_is_detected():
    assert is_alert("#a32626") and not is_alert("#0b1526")
    red = transform("#a32626", {"theme_preset": "noturno"})
    assert red[1:3] > red[3:5]                              # continua vermelho
    assert text_contrast({"theme_brightness": 50, "theme_contrast": 50}) < 4.5
    assert "font-size:15px}" in transform_qss("QWidget {font-size:12px}", {"theme_font_px": 15})


def test_theme_applies_live_and_restores():
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
            app.setStyleSheet(gui.STYLE)
            w=gui.MainWindow(); w.show(); app.processEvents()
            stop_qss=w.rotor_stop_btn.styleSheet()
            w.theme_preset.setCurrentIndex(w.theme_preset.findData("claro"))
            assert "#0b1526" not in app.styleSheet() and w.config.values["theme_preset"]=="claro"
            assert w.rotor_stop_btn.styleSheet()!=stop_qss
            w.theme_follow_display.setChecked(True); w.theme_brightness.setValue(60)
            assert w.lcd.dim<1.0 and "OK" not in w.theme_status.text() or w.lcd.dim<1.0
            w.reset_theme()
            assert app.styleSheet()==gui.STYLE and w.rotor_stop_btn.styleSheet()==stop_qss and w.lcd.dim==1.0
            assert w.display_model.count()>=5   # display continua na aba Aparência
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
