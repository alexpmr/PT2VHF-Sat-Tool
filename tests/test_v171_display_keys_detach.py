"""v1.7.1: teclas TIPO/LUZ no display, menu de contexto e display destacável para outro monitor."""
import os
import subprocess
import sys
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_next_in_and_aspect_helpers():
    from sat_tool.lcd import next_in, MODELS, THEME_ORDER, THEMES, DISPLAY_KEYS
    assert next_in(MODELS, "matriz") == "led7" and next_in(MODELS, "classico") == "matriz"
    assert next_in(THEME_ORDER, "laranja") == "âmbar" and next_in(THEME_ORDER, "???") == "âmbar"
    assert set(THEME_ORDER) == set(THEMES) and len(THEME_ORDER) >= 6
    assert {k for k, _ in DISPLAY_KEYS} == {"rxonly", "swap", "type", "light"}
    from sat_tool.display_window import fit_aspect
    assert fit_aspect(1500, 400, 7.5) == (0, 100, 1500, 200)
    assert fit_aspect(3000, 200, 7.5) == (750, 0, 1500, 200)


def test_saved_screen_falls_back_to_primary():
    from sat_tool.display_window import screen_for

    class G:
        def __init__(s, x, y, w, h): s._r = (x, y, w, h)
        def x(s): return s._r[0]
        def y(s): return s._r[1]
        def width(s): return s._r[2]
        def height(s): return s._r[3]

    class S:
        def __init__(s, name, g): s._n, s._g = name, g
        def name(s): return s._n
        def geometry(s): return s._g

    a, b = S("DP-1", G(0, 0, 1920, 1080)), S("HDMI-1", G(1920, 0, 1920, 1080))
    assert screen_for("HDMI-1", None, [a, b], a) is b
    assert screen_for("gone", [2000, 100, 800, 120], [a, b], a) is b
    assert screen_for("gone", [9000, 100, 800, 120], [a, b], a) is a


def test_all_models_render_all_keys_at_any_width():
    source = textwrap.dedent(r'''
        from sat_tool.qt_compat import QApplication
        app = QApplication([])
        from sat_tool.lcd import LcdDisplay, MODELS, THEME_ORDER
        lcd = LcdDisplay()
        lcd.set_state(rx_hz=436_795_120, tx_hz=145_850_340, rx_mode="FM", tx_mode="FM", sat_on=True, los_s=200)
        for model in MODELS:
            for theme in THEME_ORDER:
                lcd.set_model(model); lcd.set_theme(theme)
                for w, h, dpr in ((900, 132, 1.0), (1300, 150, 2.0), (2400, 320, 1.25)):
                    img, keys = lcd.render_image(w, h, dpr)
                    assert set(keys) == {"rxonly", "swap", "type", "light"}, (model, keys)
                    rects = list(keys.values())
                    for r in rects:
                        assert 0 <= r.x() and r.right() <= w + 1 and r.bottom() <= h + 1
                    for i, r in enumerate(rects):
                        assert not any(r.intersects(o) for o in rects[i + 1:])
        titles = [a.text() for a in lcd.context_menu().actions()]
        assert any("Tipo de display" in t for t in titles) and any("Destacar" in t for t in titles)
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr


def test_window_cycles_keys_and_detaches_display():
    source = textwrap.dedent(r'''
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
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.show(); app.processEvents()
            w.lcd.type_clicked.emit()
            assert w.lcd.model=="led7" and w.config.values["display_model"]=="led7"
            w.lcd.light_clicked.emit()
            assert w.lcd.theme=="verde" and w.display_preview.theme=="verde"
            w.lcd.model_chosen.emit("digital"); assert w.lcd.model=="digital"
            parent=w.lcd.parent()
            w.lcd.detach_requested.emit(); app.processEvents()
            assert w.display_window is not None and w.lcd.window() is w.display_window
            assert w.display_placeholder.isVisible() and w.config.values["display_detached"] is True
            w.display_window.resize(1500,400); app.processEvents()
            assert abs(w.lcd.width()/w.lcd.height()-7.5)<0.1 and w.lcd.height()>170
            w.lcd.light_clicked.emit(); assert w.lcd.theme=="azul"   # continua funcional destacado
            w.display_window.close(); app.processEvents()
            assert w.display_window is None and w.lcd.parent() is parent and w.lcd.maximumHeight()==170
            assert w.config.values["display_detached"] is False and w.config.values.get("display_window_rect")
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
