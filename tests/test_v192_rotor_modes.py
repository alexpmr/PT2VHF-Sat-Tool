"""v1.9.2 (backlog 14/11/2026): rotor AUTOMÁTICO / MANUAL / DESLIGADO junto dos gauges; sempre DESLIGADO ao abrir."""
import os
import subprocess
import sys
import textwrap


def test_rotor_modes_manual_arrows_off_and_stop():
    source = textwrap.dedent(r'''
        import tempfile
        from datetime import datetime, timezone
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
            # ao abrir: sempre DESLIGADO
            assert w.rotor_mode=="off" and not w.rotor_auto
            assert w.rotor_mode_btns["off"].isChecked() and not w.rotor_mode_btns["auto"].isChecked()
            assert w.rotor_manual_box.isHidden() and not w.rotor_park_btn.isEnabled()
            assert w.rotor_stop_btn.text()=="PARAR" and "#a32626" in w.rotor_stop_btn.styleSheet()
            class R:
                connected=True; position=(100.0,10.0); failures=0; last_command_at=0.0
                def __init__(self):self.moves=[];self.stops=0
                def stop(self):self.stops+=1
                def move(self,az,el,prof):self.moves.append((az,el));return az,el
                def read_position(self):return self.position
                def close(self):pass
            w.rotor=R()
            jobs=[]
            def bg(key,fn):
                jobs.append(key); fn()
            w.background=bg
            w.config.values["rotor_enabled"]=True
            # DESLIGADO: o tick não move nada
            w.rotor_tick(datetime.now(timezone.utc))
            assert w.rotor.moves==[] and "DESLIGADO" in w.rotor_state_chip.text()
            # MANUAL: setas movem um passo a partir do último alvo
            w.rotor_mode_btns["manual"].click(); app.processEvents()
            assert w.rotor_mode=="manual" and not w.rotor_manual_box.isHidden() and w.rotor_park_btn.isEnabled()
            w.rotor_bar_step.setCurrentIndex(w.rotor_bar_step.findData(10.0))
            assert w.config.values["rotor_jog_step"]==10.0
            w.rotor_bar_jog["right"].click(); w.rotor_bar_jog["right"].click(); w.rotor_bar_jog["up"].click()
            assert w.rotor.moves==[(110.0,10.0),(120.0,10.0),(120.0,20.0)], w.rotor.moves
            w.rotor_bar_jog["down"].click(); w.rotor_bar_jog["down"].click(); w.rotor_bar_jog["down"].click()
            assert w.rotor.moves[-1]==(120.0,0.0)            # respeita o limite mecânico
            w.rotor_tick(datetime.now(timezone.utc))
            assert "MANUAL" in w.rotor_state_chip.text() and len(w.rotor.moves)==6   # tick não move no manual
            # AUTOMÁTICO + PARAR → MANUAL (não volta a mover sozinho)
            w.rotor_mode_btns["auto"].click(); assert w.rotor_mode=="auto" and w.rotor_auto
            w.rotor_stop_btn.click(); assert w.rotor_mode=="manual" and w.rotor.stops>=1
            w.rotor_set_mode("auto"); w.rotor_shortcut_stop(); assert w.rotor_mode=="manual"
            # DESLIGADO: setas e estacionar não enviam movimento
            n=len(w.rotor.moves)
            w.rotor_mode_btns["off"].click(); w.rotor_bar_jog_move(1,0); w.rotor_park()
            assert len(w.rotor.moves)==n and w.rotor_mode=="off"
            # compatibilidade: rede liga/desliga o automático
            w.rotor_set_auto(True); assert w.rotor_mode=="auto"
            w.rotor_set_auto(False,"rede"); assert w.rotor_mode=="manual"
        # ao reabrir, o modo NÃO é lembrado (sempre DESLIGADO); o passo sim
        with tempfile.TemporaryDirectory() as d2:
            cfg=Config(Path(d2)); cfg.values["rotor_jog_step"]=10.0; cfg.save()
            gui.Config=lambda:Config(Path(d2))
            w2=gui.MainWindow(); app.processEvents()
            assert w2.rotor_mode=="off" and w2.rotor_bar_step.currentData()==10.0
        print("OK")
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr


def test_newer_settings_survive_reopening(tmp_path):
    """v1.9.2: rotor, aparência, display destacado e painel SDR eram descartados ao reabrir (fora de DEFAULTS)."""
    from sat_tool.config import Config
    c = Config(tmp_path)
    c.values.update(rotor_enabled=True, rotor_port="COM17", rotor_profile="g5500", rotor_north_offset=-12.0,
                    rotor_jog_step=10.0, theme_preset="noturno", theme_brightness=80, display_detached=True,
                    display_window_rect=[10, 20, 800, 200], sdr_dock_user_hidden=True, display_bezel=True,
                    display_label="TS-2000")
    c.save()
    v = Config(tmp_path).values
    assert (v["rotor_enabled"], v["rotor_port"], v["rotor_profile"], v["rotor_north_offset"], v["rotor_jog_step"]) == \
        (True, "COM17", "g5500", -12.0, 10.0)
    assert v["theme_preset"] == "noturno" and v["theme_brightness"] == 80
    assert v["display_detached"] is True and v["display_window_rect"] == [10, 20, 800, 200]
    assert v["sdr_dock_user_hidden"] is True and v["display_bezel"] is True and v["display_label"] == "TS-2000"
