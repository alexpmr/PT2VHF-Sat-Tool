"""v1.7.1: Configurações → Rotores (calibração, ajuste manual, preferências, log) e faixa ROTOR na Operação."""
import os
import subprocess
import sys
import textwrap


def test_calibration_jog_preference_and_antenna_line():
    from sat_tool.rotor import (RotorProfile, calibrated_north_offset, jog_target, plan_pass, antenna_line)
    assert calibrated_north_offset(12, 0, 0) == 12 and calibrated_north_offset(350, 10, 0) == -20
    prof = RotorProfile(az_max=450, el_max=180)
    assert jog_target((445, 179), 10, 10, prof) == (450, 180) and jog_target(None, 5, 0, prof) is None
    track = [(i, 100 + i, 10 + i) for i in range(10)]
    assert plan_pass(track, prof)["mode"] == "normal"
    assert plan_pass(track, prof, "flip")["mode"] == "flip"
    assert plan_pass(track, RotorProfile(az_max=360, el_max=90), "flip")["mode"] == "normal"
    line = antenna_line(-22.9, -43.2, 90.0, km=1000, steps=4)
    assert line[0] == [-22.9, -43.2] and line[-1][1] > -43.2 and len(line) == 5


def test_compass_pointing_handles_flip_and_overlap():
    from sat_tool.rotor_widgets import RotorCompass
    assert RotorCompass.pointing(400, 30) == (40, 30)
    assert RotorCompass.pointing(10, 150) == (190, 30)


def test_rotor_settings_and_bar_in_window():
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
            w=gui.MainWindow(); w.show(); app.processEvents()
            names=[w.settings_tabs.tabText(i) for i in range(w.settings_tabs.count())]
            assert "Rotores" in names and "Rotor" not in names
            w.open_settings("Rotor"); assert w.settings_tabs.tabText(w.settings_tabs.currentIndex())=="Rotores"
            assert w.rotor_bar.isHidden() and not any(sc.isEnabled() for sc in w.rotor_shortcuts)
            w.rotor_enable.setChecked(True); app.processEvents()
            assert not w.rotor_bar.isHidden() and all(sc.isEnabled() for sc in w.rotor_shortcuts)
            op=w.rotor_bar.parentWidget().layout()
            # faixa logo depois do painel do display
            panel_index=[i for i in range(op.count()) if op.itemAt(i).widget() is not None and
                         op.itemAt(i).widget().isAncestorOf(w.lcd)][0]
            assert op.indexOf(w.rotor_bar)==panel_index+1
            w.rotor_pref.setCurrentIndex(w.rotor_pref.findData("flip")); w.rotor_min_el.setValue(5); w.rotor_save()
            assert w.config.values["rotor_preference"]=="flip" and w.rotor_profile().min_el==5
            sent=[]
            w.background=lambda key,fn:sent.append(key)
            class R:
                connected=True; position=(100.0,20.0); failures=0; last_command_at=0.0
                def stop(self):pass
                def close(self):pass
            w.rotor=R()
            w.rotor_true_az.setValue(90); w.rotor_calibrate()
            assert w.config.values["rotor_north_offset"]==10
            w.rotor_jog(1,0); assert sent[-1]=="rotor-move"
            w.rotor_shortcut_stop(); assert "rotor-stop" in sent
            w.rotor_log("Rotor TX C2"); assert "Rotor TX C2" in w.rotor_log_view.toPlainText()
            w.rotor_show_position((400.0,150.0))
            assert w.rotor_compass.real==(210.0,30.0)   # 400−10 → 390 → flip
            assert w.rotor_map_payload(type("S",(),{"lat":-22.9,"lon":-43.2})())["az"]==90.0
            w.rotor_config_btn.click(); assert w.tabs.currentIndex()==2
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
