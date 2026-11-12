"""v1.7.2 (backlog 12/11/2026): botão ROTOR no topo liga/desliga o controlador, como CAT e SDR; "Painel SDR" → "SDR"."""
import os
import subprocess
import sys
import textwrap


def test_rotor_top_button_connects_and_disconnects():
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
            assert w.sdr_toggle.text()=="SDR" and w.cat_indicator.text()=="CAT" and w.rotor_top_btn.text()=="ROTOR"
            # mesma linha do topo, nesta ordem
            xs=[b.mapTo(w,b.rect().topLeft()).x() for b in (w.cat_indicator,w.sdr_toggle,w.rotor_top_btn)]
            assert xs==sorted(xs) and w.rotor_top_btn.width()==w.cat_indicator.width()==w.sdr_toggle.width()
            assert w.rotor_top_btn.toolTip().startswith("Rotor desligado") and "#783437" in w.rotor_top_btn.styleSheet()
            class R:
                connected=False; position=None; failures=0; last_command_at=0.0
                def stop(self):pass
                def close(self):pass
            w.rotor=R()
            sent=[]
            w.background=lambda key,fn:sent.append(key)
            w.rotor_port.setCurrentText("COM9")
            assert not w.rotor_cfg("rotor_enabled")
            w.rotor_top_btn.click(); app.processEvents()
            assert sent==["rotor-connect"] and w.config.values["rotor_enabled"]   # ligar ativa o rotor
            assert not w.rotor_top_btn.isEnabled() and "#755225" in w.rotor_top_btn.styleSheet()
            w.rotor.connected=True
            w.rotor_result("rotor-connect",(10.0,5.0))
            assert w.rotor_top_btn.isEnabled() and "#12533f" in w.rotor_top_btn.styleSheet()
            assert w.rotor_top_btn.toolTip().startswith("Rotor conectado · COM9")
            w.rotor_top_btn.click(); app.processEvents()
            assert sent[-1]=="rotor-close"
            w.rotor.connected=False
            w.rotor_result("rotor-close",None)
            assert "#783437" in w.rotor_top_btn.styleSheet() and w.rotor_top_btn.toolTip().startswith("Rotor desligado")
            # falha ao conectar volta ao vermelho
            w.rotor_top_btn.click(); w.rotor_failed("rotor-connect","porta ocupada")
            assert w.rotor_top_btn.isEnabled() and "#783437" in w.rotor_top_btn.styleSheet()
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stdout + result.stderr


def test_connect_with_rotor_disabled_keeps_port_open_and_updates_bar():
    """Bug 12/11/2026: conectado em COM17 a faixa ficava DESCONECTADO e os gauges parados."""
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
        gui.MainWindow.check_for_updates=lambda self:None
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            gui.MainWindow.background=lambda self,key,fn:None
            w=gui.MainWindow(); w.show(); app.processEvents()
            class R:
                connected=False; position=None; failures=0; last_command_at=0.0
                def stop(self):pass
                def close(self):pass
                def read_position(self):return self.position
            w.rotor=R()
            sent=[]
            w.background=lambda key,fn:sent.append(key)
            w.rotor_port.setCurrentText("COM17")
            assert not w.rotor_enable.isChecked()
            w.rotor_toggle_connection()      # botão Conectar de Configurações → Rotores
            assert sent==["rotor-connect"], sent          # antes: também agendava rotor-close
            assert w.rotor_cfg("rotor_enabled") and w.rotor_enable.isChecked()
            w.rotor.connected=True; w.rotor.position=(140.0,175.0)
            w.rotor_result("rotor-connect",(140.0,175.0))
            assert "PARADO" in w.rotor_state_chip.text()
            # número grande = direção da antena (igual aos gauges); leitura crua no tooltip
            assert w.rotor_pos_label.text()=="AZ 320°  EL 5°" and "AZ 140°  EL 175°" in w.rotor_pos_label.toolTip()
            assert w.rotor_compass.real==(320.0,5.0)
            w.rotor_last_read=0
            w.rotor_tick(gui.now_utc())
            assert "rotor-read" in sent                   # posição continua sendo lida a cada segundo
            w.rotor_result("rotor-read",(150.0,170.0))
            assert w.rotor_compass.real==(330.0,10.0)
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stdout + result.stderr
