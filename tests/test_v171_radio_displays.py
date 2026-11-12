"""v1.7.1: displays no estilo de rádios reais (IC-706MKIIG, IC-7100, FT-897/857, IC-910H, FT-991A, IC-9700)."""
import os
import subprocess
import sys
import textwrap


def run(source):
    result = subprocess.run([sys.executable, "-c", textwrap.dedent(source)], capture_output=True, text=True,
                            timeout=120, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr


def test_radio_models_render_keys_scope_and_restricted_backlights():
    run(r'''
        from sat_tool.qt_compat import QApplication
        from sat_tool.lcd import LcdDisplay, MODELS, RADIO_MODELS, themes_for, next_in, THEME_ORDER
        from sat_tool.lcd_radios import SCOPE_MODELS
        app = QApplication([])
        assert set(RADIO_MODELS) <= set(MODELS) and list(MODELS)[-1] == "classico"
        assert not any(w in name.lower() for name in RADIO_MODELS.values() for w in ("icom", "yaesu", "kenwood"))
        assert themes_for("ic706") == ("verde", "âmbar") and themes_for("ic7100") == ("branco",)
        assert themes_for("ft897") == THEME_ORDER and next_in(themes_for("ic706"), "âmbar") == "verde"
        state = dict(rx_hz=436795120, rx_mode="FM", tx_hz=145850000, tx_mode="FM", sat_on=True, link="CAT",
                     auto=True, doppler_hz=-8120, elevation=34, visible=True, signal=18, power_w=25, swr=1.2,
                     los_s=25, sat_name="SO-50")
        for model in RADIO_MODELS:
            d = LcdDisplay(model=model, theme="azul")
            d.set_state(**state)
            for w, h in ((1300, 132), (640, 120), (900, 170)):
                for dpr in (1.0, 2.0):
                    img, keys = d.render_image(w, h, dpr)
                    assert img.width() == round(w * dpr), model
                    assert set(keys) == {"swap", "rxonly", "type", "light"}, (model, keys)
                    rects = list(keys.values())
                    for i, r in enumerate(rects):
                        assert 0 <= r.x() and r.right() <= w + 1 and r.bottom() <= h + 1, (model, w, r)
                        assert not any(r.intersects(o) for o in rects[i + 1:]), model
            # sem RTL-SDR: escopo mostra "SDR DESLIGADO" e não é clicável
            d.resize(1300, 132); d.render_image(1300, 132)
            d._scope_rect = d._last_scope
            if model in SCOPE_MODELS:
                assert d._scope_rect is not None, model
                assert d.key_at(d._scope_rect.center()) is None
                d.push_scope([0.1] * 70 + [0.9] * 10 + [0.1] * 80, 50000)
                assert d.key_at(d._scope_rect.center()) == "scope"
                got = []
                d.scope_clicked.connect(got.append)
                from sat_tool.qt_compat import Qt
                from PySide6.QtTest import QTest
                d.show(); app.processEvents()
                QTest.mouseClick(d, Qt.LeftButton, pos=d._scope_rect.center().toPoint())
                assert got and abs(got[0] - 0.5) < 0.05, got
                d.push_scope(None)
                assert d.state.scope is None and d.state.scope_rows == []
            # backlight restrito: tema fora da lista cai no primeiro permitido; menu só oferece os permitidos
            menu = d.context_menu()
            from sat_tool.qt_compat import QMenu
            colors = [m for m in menu.findChildren(QMenu) if "backlight" in m.title()][0]
            assert len(colors.actions()) == len(themes_for(model)), model
        d = LcdDisplay(model="ic9700")
        for k in range(100):
            d.push_scope([k / 100] * 40, 25000)
        assert len(d.state.scope_rows) == 48 and d.state.scope_span_hz == 25000
        print("OK")
    ''')


def test_light_key_cycles_only_allowed_colours_and_sdr_feeds_display_scope():
    run(r'''
        import tempfile
        import numpy as np
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
            w.set_display_choice(model="ic706")
            seen=set()
            for _ in range(5):
                w.cycle_display("theme"); seen.add(w.display_theme.currentData())
            assert seen=={"verde","âmbar"}, seen
            w.set_display_choice(model="ic7100")
            w.cycle_display("theme"); assert w.display_theme.currentData()=="branco"
            w.set_display_choice(model="ic9700")
            # FFT do RTL-SDR → waterfall do painel → escopo do display (mesmos dados)
            panel=w.sdr_panel; wf=panel.waterfall
            wf.channel_hz=436_795_000
            spec=np.full(4096,-120.0); spec[2040:2056]=-60.0
            wf.push(spec,436_795_000)
            panel.feed_display_scope(True)
            sc=w.lcd.state.scope
            assert sc and max(sc)>0.8 and min(sc)<0.3 and w.lcd.state.scope_span_hz==wf.span_hz
            tuned=[]
            wf.on_click=tuned.append
            w.display_scope_tune(0.75)
            assert tuned==[0.5*wf.span_hz]
            panel._scope_t=0.0
            panel.feed_display_scope(False)
            assert w.lcd.state.scope is None
            w.display_scope_tune(0.75)
            assert len(tuned)==1
            print("OK")
    ''')
