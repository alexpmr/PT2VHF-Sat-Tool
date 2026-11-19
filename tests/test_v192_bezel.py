"""v1.9.2 (backlog): moldura de rádio realista em volta do display, etiqueta livre do operador (sem logotipos)."""
import os
import subprocess
import sys
import textwrap


def _run(source):
    result = subprocess.run([sys.executable, "-c", textwrap.dedent(source)], capture_output=True, text=True,
                            timeout=180, env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stdout + result.stderr


def test_bezel_renders_every_model_and_keys_click():
    _run(r'''
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent
        from sat_tool.lcd import LcdDisplay, MODELS
        app=QApplication([])
        d=LcdDisplay(); d.resize(900,230)
        d.set_state(rx_hz=436_795_120,tx_hz=145_850_340,rx_mode="FM",tx_mode="FM",signal=18,power_w=25,swr=1.2,
                    sat_on=True,link="CAT",auto=True,doppler_hz=-6800,visible=True,elevation=38,los_s=342)
        assert d.docked_heights()==(118,170)
        d.set_bezel(True,"  PT2VHF STATION LONG LABEL XYZ ","sub")
        assert d.bezel and d.bezel_label=="PT2VHF STATION LONG LABE" and d.docked_heights()==(196,250)
        assert d.minimumHeight()==196 and d.maximumHeight()==250
        for model in MODELS:
            d.set_model(model)
            img,keys=d.render_image(900,230,1.0)
            assert not img.isNull() and img.width()==900
            assert {"bz_swap","bz_rxonly","bz_type","bz_light"} <= set(keys), (model,keys)
        got=[]
        for sig,name in ((d.swap_clicked,"swap"),(d.rx_only_clicked,"rx"),(d.type_clicked,"type"),(d.light_clicked,"light")):
            sig.connect(lambda n=name:got.append(n))
        d.set_model("matriz"); img,d._keys=d.render_image(900,230,1.0)
        for key in ("bz_swap","bz_rxonly","bz_type","bz_light"):
            c=d._keys[key].center()
            ev=QMouseEvent(QEvent.MouseButtonPress,QPointF(c),QPointF(c),Qt.LeftButton,Qt.LeftButton,Qt.NoModifier)
            d.mousePressEvent(ev)
        assert got==["swap","rx","type","light"], got
        d.set_bezel(False)
        img,keys=d.render_image(900,230,1.0)
        assert not any(k.startswith("bz_") for k in keys) and d.minimumHeight()==118
    ''')


def test_bezel_settings_apply_live_and_persist():
    _run(r'''
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
            w=gui.MainWindow(); w.show(); app.processEvents()
            assert not w.lcd.bezel and not w.display_label.isEnabled()
            w.display_bezel.setChecked(True)
            w.display_label.setText("PT2VHF"); w.display_sublabel.setText("Estação satélite")
            app.processEvents()
            assert w.lcd.bezel and w.display_preview.bezel and w.lcd.bezel_label=="PT2VHF"
            assert w.lcd.minimumHeight()==196 and w.lcd.maximumHeight()==250
            assert Config(Path(d)).values["display_label"]=="PT2VHF"
            # destacar e devolver mantém a altura da moldura
            w.toggle_display_detached(); app.processEvents()
            w.toggle_display_detached(); app.processEvents()
            assert w.lcd.minimumHeight()==196 and w.lcd.maximumHeight()==250
            w._closing_app=True; w.close(); app.processEvents()
            w2=gui.MainWindow(); app.processEvents()
            assert w2.lcd.bezel and w2.display_bezel.isChecked() and w2.lcd.bezel_sublabel=="Estação satélite"
    ''')
