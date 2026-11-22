"""v1.9.5 (backlog 22/11/2026): rotor via Hamlib rotctld por TCP (qualquer rotor suportado pelo Hamlib)."""
import os
import socket
import subprocess
import sys
import textwrap
import threading

import pytest

from sat_tool.rotor import RotctldRotor, RotorProfile, make_rotor, parse_address, probe_rotctld, GS232Rotor

FAKE_SERVER = r'''
import socket, threading
class FakeRotctld:
    """rotctld mínimo: p, P az el, S, com o protocolo de linhas do Hamlib."""
    def __init__(self):
        self.srv = socket.socket(); self.srv.bind(("127.0.0.1", 0)); self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        self.az, self.el, self.cmds = 123.4, 45.0, []
        threading.Thread(target=self.loop, daemon=True).start()
    def loop(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self.client, args=(c,), daemon=True).start()
    def client(self, c):
        f = c.makefile("rwb")
        for raw in f:
            line = raw.decode().strip()
            self.cmds.append(line)
            if line == "p":
                f.write(f"{self.az:.6f}\n{self.el:.6f}\n".encode())
            elif line.startswith("P "):
                _, a, e = line.split()
                if float(e) > 90:
                    f.write(b"RPRT -1\n")
                else:
                    self.az, self.el = float(a), float(e); f.write(b"RPRT 0\n")
            elif line == "S":
                f.write(b"RPRT 0\n")
            else:
                f.write(b"RPRT -4\n")
            f.flush()
'''
exec(FAKE_SERVER)


def test_parse_address():
    assert parse_address("") == ("127.0.0.1", 4533)
    assert parse_address("192.168.0.10:4534") == ("192.168.0.10", 4534)
    assert parse_address("localhost") == ("localhost", 4533)
    assert parse_address(":4600") == ("127.0.0.1", 4600)
    with pytest.raises(ValueError):
        parse_address("host:abc")


def test_rotctld_read_move_stop_and_errors():
    srv = FakeRotctld()
    logs = []
    rotor = RotctldRotor(logs.append)
    assert not rotor.connected
    assert rotor.connect(f"127.0.0.1:{srv.port}") == (123.4, 45.0)
    assert rotor.connected
    prof = RotorProfile(az_max=450, el_max=180)
    assert rotor.move(200.04, 30.0, prof) == (200.04, 30.0)
    assert srv.cmds[-1] == "P 200.0 30.0"
    assert rotor.read_position() == (200.0, 30.0)
    rotor.stop()
    assert srv.cmds[-1] == "S"
    assert rotor.park(RotorProfile(park_az=0, park_el=0)) == (0.0, 0.0)
    with pytest.raises(ConnectionError):          # rotctld recusa (RPRT -1) → erro visível
        rotor.move(10, 120, prof)
    assert any("Rotor TX P" in line for line in logs)
    rotor.close()
    assert not rotor.connected
    with pytest.raises(ConnectionError):
        rotor.read_position()
    assert probe_rotctld(f"127.0.0.1:{srv.port}") == (0.0, 0.0)
    srv.srv.close()
    # sem rotctld rodando: não conecta e o teste só leitura devolve None
    free = socket.socket(); free.bind(("127.0.0.1", 0)); port = free.getsockname()[1]; free.close()
    assert probe_rotctld(f"127.0.0.1:{port}") is None
    assert isinstance(make_rotor("rotctld"), RotctldRotor) and type(make_rotor("gs232")) is GS232Rotor


def test_settings_switch_to_rotctld_and_connect():
    source = textwrap.dedent(r'''
        import tempfile
        from pathlib import Path
        from sat_tool import app as gui
        from sat_tool.config import Config
        from sat_tool.rotor import RotctldRotor, RotorProfile
    ''') + FAKE_SERVER + textwrap.dedent(r'''
        class FakeWeb(gui.QWidget):
            def setHtml(self,*a,**k):pass
            def page(self):return self
            def runJavaScript(self,*a,**k):pass
            def reload(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda d:[]
        gui.MainWindow.check_for_updates=lambda self:None
        srv=FakeRotctld()
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); app.processEvents()
            results=[]
            def bg(key,fn):
                try:
                    data=fn(); results.append(key); w.rotor_result(key,data)
                except Exception as exc:
                    results.append((key,str(exc)))
            w.background=bg
            assert w.config.values["rotor_protocol"]=="gs232" and not w.rotor_rotctld_addr.isEnabled()
            w.rotor_protocol.setCurrentIndex(w.rotor_protocol.findData("rotctld"))
            assert w.rotor_rotctld_addr.isEnabled() and not w.rotor_port.isEnabled() and w.rotor_detect.text()=="Testar rotctld"
            w.rotor_rotctld_addr.setText(f"127.0.0.1:{srv.port}")
            w.rotor_save()
            assert w.config.values["rotor_protocol"]=="rotctld" and w.config.values["rotor_rotctld"]==f"127.0.0.1:{srv.port}"
            w.rotor_toggle_connection()
            assert isinstance(w.rotor,RotctldRotor) and w.rotor.connected, results
            assert "rotctld 127.0.0.1" in w.rotor_where()
            assert "rotctld 127.0.0.1" in w.rotor_label.text() and "AZ 123" in w.rotor_settings_status.text()
            w.rotor_autodetect()
            assert "respondeu" in w.rotor_settings_status.text(), w.rotor_settings_status.text()
            w.rotor.move(90,10,RotorProfile())
            assert srv.cmds[-1]=="P 90.0 10.0", srv.cmds
            w.rotor.close()
            # reabrir: protocolo e endereço lembrados
            w2=gui.MainWindow(); app.processEvents()
            assert w2.rotor_protocol.currentData()=="rotctld" and isinstance(w2.rotor,RotctldRotor)
            assert w2.rotor_rotctld_addr.text()==f"127.0.0.1:{srv.port}"
        print("OK")
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr
