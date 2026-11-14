"""v1.9.0: ICOM CI-V, Kenwood CAT texto, servidor DDE do Orbitron (WiSpDDE) e PREVER."""
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone

import pytest

from sat_tool import dde_server, rigs


class FakeCiv:
    """Barramento CI-V: devolve o eco do quadro e a resposta do rádio (endereço 56h, IC-746)."""

    def __init__(self, address=0x56, freq=145_800_000, mode=0x05, transmitting=None):
        self.address, self.freq, self.mode, self.tx = address, freq, mode, transmitting
        self.out, self.written = b"", []

    def reset_input_buffer(self):
        self.out = b""

    def write(self, frame):
        self.written.append(bytes(frame))
        self.out += bytes(frame)   # eco
        if frame[2] != self.address:
            return
        cmd, payload = frame[4], frame[5:-1]
        head = bytes([0xFE, 0xFE, 0xE0, self.address])
        if cmd == 0x03:
            self.out += head + b"\x03" + rigs.civ_frequency(self.freq) + b"\xFD"
        elif cmd == 0x04:
            self.out += head + bytes([0x04, self.mode, 0x01]) + b"\xFD"
        elif cmd == 0x05:
            self.freq = rigs.parse_civ_frequency(payload)
            self.out += head + b"\xFB\xFD"
        elif cmd == 0x1C:
            if self.tx is None:
                self.out += head + b"\xFA\xFD"
            else:
                self.out += head + bytes([0x1C, 0x00, 1 if self.tx else 0]) + b"\xFD"
        else:
            self.out += head + b"\xFB\xFD"

    def read(self, n):
        data, self.out = self.out[:n], self.out[n:]
        return data

    def close(self):
        pass


def test_civ_frequency_matches_the_ic746_line_from_pu2mus():
    # "IC746 50.950 USB - FEFExxE00500009550FD": BCD com o byte menos significativo primeiro
    frame = rigs.civ_frame(0x56, 0x05, rigs.civ_frequency(50_950_000))
    assert frame.hex().upper() == "FEFE56E0050000955000FD"
    assert rigs.parse_civ_frequency(rigs.civ_frequency(435_123_450)) == 435_123_450
    assert rigs.ICOM_ADDRESSES["IC-746"] == 0x56 and rigs.ICOM_ADDRESSES["IC-9700"] == 0xA2
    assert "ICOM" in rigs.RIG_MODELS and "KENWOOD" in rigs.RIG_MODELS


def test_icom_driver_tunes_skips_echo_and_never_keys_ptt():
    bus = FakeCiv()
    rig = rigs.Icom(address=0x56)
    rig.connect("COM9", 9600, serial_factory=lambda: bus)
    assert rig.read_frequency() == (145_800_000, "FM")
    assert rig.is_transmitting() is None          # IC-746 recusa 1C 00: não bloqueia
    assert rig.set_rx(50_950_000, "USB") is True and bus.freq == 50_950_000
    assert any(f[4] == 0x06 and f[5] == 0x01 for f in bus.written)   # USB
    assert rig.set_tx(145_990_000, "FM", same_rig_rx=True) is True
    cmds = [f[4] for f in bus.written]
    assert 0x0F in cmds and cmds.count(0x07) >= 2   # split + VFO B e volta ao A
    assert not any(f[4] == 0x1C and f[5:7] == b"\x00\x01" for f in bus.written)   # nunca PTT
    bus.tx = True
    assert rig.set_rx(145_800_000, "FM") is False    # não mexe durante a transmissão
    rig.disconnect()


def test_icom_wrong_address_times_out():
    rig = rigs.Icom(address=0x60)
    with pytest.raises(TimeoutError):
        rig.connect("COM9", 9600, serial_factory=lambda: FakeCiv(address=0x56))
    assert not rig.connected


class FakeKenwood:
    def __init__(self):
        self.out, self.written, self.fa = b"", [], 14_250_000

    def reset_input_buffer(self):
        self.out = b""

    def write(self, data):
        text = data.decode()
        self.written.append(text)
        for cmd in filter(None, text.split(";")):
            if cmd == "ID":
                self.out += b"ID021;"
            elif cmd == "FA":
                self.out += f"FA{self.fa:011d};".encode()
            elif cmd.startswith("FA") and len(cmd) == 13:
                self.fa = int(cmd[2:])
            elif cmd == "MD":
                self.out += b"MD2;"
            elif cmd == "IF":
                self.out += ("IF" + f"{self.fa:011d}" + " " * 5 + "+0000" + "000" + "00" + "0" + "0" + "2" + "0" * 9 + ";").encode()

    def read(self, n):
        data, self.out = self.out[:n], self.out[n:]
        return data

    def close(self):
        pass


def test_kenwood_text_driver_split_without_ptt():
    port = FakeKenwood()
    rig = rigs.KenwoodText()
    rig.connect("COM3", 9600, serial_factory=lambda: port)
    assert rig.model == "TS-590S" and rig.read_frequency() == (14_250_000, "USB")
    assert rig.is_transmitting() is False
    assert rig.set_rx(145_800_000, "FM") and port.fa == 145_800_000
    assert rig.set_tx(435_000_000, "FM", same_rig_rx=True)
    sent = "".join(port.written)
    assert "FR0;FT1;" in sent and "FB00435000000;" in sent
    assert "TX;" not in sent and "TX0;" not in sent and "TX1;" not in sent


def test_orbitron_tracking_text_for_wispdde():
    snap = {"name": "ISS (ZARYA)", "azimuth": 182.06, "elevation": 36.33, "rx_hz": 145_800_000,
            "tx_hz": 145_990_000, "rx_mode": "FM", "tx_mode": "FM"}
    assert dde_server.tracking_text(snap) == \
        "SNISS_(ZARYA) AZ182.1 EL36.3 DN145800000 UP145990000 DMFM-N UMFM-N"
    assert dde_server.tracking_text({**snap, "tx_hz": None, "rx_mode": "USB", "tx_mode": "",
                                     "azimuth": 360.0, "elevation": -12.0}) == \
        "SNISS_(ZARYA) AZ0.0 EL-12.0 DN145800000 DMUSB"
    assert dde_server.tracking_text(None) == ""
    assert (dde_server.SERVICE, dde_server.TOPIC, dde_server.ITEM) == ("Orbitron", "Tracking", "TrackingData")


@pytest.mark.skipif(sys.platform != "win32", reason="DDE só existe no Windows")
def test_dde_server_answers_a_real_dde_client():
    import ctypes
    from ctypes import wintypes
    server = dde_server.DdeServer()
    server.start()
    server.update("SNSO-50 AZ10.0 EL20.0 DN436795000 UP145850000 DMFM-N UMFM-N")
    client = textwrap.dedent(r'''
        import ctypes, sys
        from ctypes import wintypes
        u = ctypes.windll.user32
        CB = ctypes.WINFUNCTYPE(ctypes.c_void_p, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t)
        cb = CB(lambda *a: 0)
        u.DdeInitializeW.argtypes = [ctypes.POINTER(wintypes.DWORD), CB, wintypes.DWORD, wintypes.DWORD]
        u.DdeCreateStringHandleW.restype = ctypes.c_void_p
        u.DdeCreateStringHandleW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, ctypes.c_int]
        u.DdeConnect.restype = ctypes.c_void_p
        u.DdeConnect.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        u.DdeClientTransaction.restype = ctypes.c_void_p
        u.DdeClientTransaction.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p,
                                           wintypes.UINT, wintypes.UINT, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        u.DdeGetData.argtypes = [ctypes.c_void_p, ctypes.c_char_p, wintypes.DWORD, wintypes.DWORD]
        inst = wintypes.DWORD(0)
        assert u.DdeInitializeW(ctypes.byref(inst), cb, 0x00000010, 0) == 0   # APPCMD_CLIENTONLY
        hs = lambda s: u.DdeCreateStringHandleW(inst.value, s, 1200)
        conv = u.DdeConnect(inst.value, hs("Orbitron"), hs("Tracking"), None)
        assert conv, "sem conversa DDE"
        res = wintypes.DWORD(0)
        data = u.DdeClientTransaction(None, 0, conv, hs("TrackingData"), 1, 0x20B0, 5000, ctypes.byref(res))
        assert data, "sem dados"
        buf = ctypes.create_string_buffer(512)
        u.DdeGetData(data, buf, 512, 0)
        print(buf.value.decode())
    ''')
    proc = subprocess.Popen([sys.executable, "-c", client], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    msg = wintypes.MSG()
    deadline = time.monotonic() + 20
    while proc.poll() is None and time.monotonic() < deadline:
        while ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.01)
    out, err = proc.communicate(timeout=5)
    server.stop()
    assert proc.returncode == 0, err
    assert out.strip() == "SNSO-50 AZ10.0 EL20.0 DN436795000 UP145850000 DMFM-N UMFM-N"


def test_forecast_lists_every_selected_satellite_sorted_and_filtered():
    from skyfield.api import load
    from sat_tool.core import Station
    from sat_tool.forecast import forecast_passes, write_csv, duration_text
    ts = load.timescale(builtin=True)
    now = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
    iss = {"OBJECT_NAME": "ISS", "TLE_LINE1": "1 25544U 98067A   26317.50000000  .00016717  00000-0  10270-3 0  9990",
           "TLE_LINE2": "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.50377579 12345"}
    so50 = {"OBJECT_NAME": "SO-50", "TLE_LINE1": "1 27607U 02058C   26317.50000000  .00000500  00000-0  65432-4 0  9993",
            "TLE_LINE2": "2 27607  64.5500 200.0000 0060000  10.0000 350.0000 14.80000000 10001"}
    station = Station("PT2VHF", -15.8, -47.9, 1100, 0.0)
    rows = forecast_passes({"25544": iss, "27607": so50}, ["25544", "27607", "99999"], station,
                           hours=24, min_elevation=0, now=now, ts=ts)
    assert {r["id"] for r in rows} == {"25544", "27607"}
    assert [r["aos"] for r in rows] == sorted(r["aos"] for r in rows)
    assert all(now - timedelta(minutes=20) < r["aos"] < now + timedelta(hours=24) for r in rows)
    high = forecast_passes({"25544": iss, "27607": so50}, ["25544", "27607"], station,
                           hours=24, min_elevation=40, now=now, ts=ts)
    assert len(high) < len(rows) and all(r["max_el"] >= 40 for r in high)
    assert duration_text(605) == "10:05"


def test_forecast_window_opens_from_the_main_window():
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
        gui.MainWindow.show_official_site_notice=lambda self:None
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.show(); app.processEvents()
            assert w.forecast_button.text()=="PREVER"
            dlg=w.open_forecast(); app.processEvents()
            assert dlg.isVisible() and dlg.table.columnCount()==6
            assert dlg.status_label.text()  # sem estação ou sem satélites: avisa em vez de travar
            assert w.open_forecast() is dlg   # uma janela só
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
