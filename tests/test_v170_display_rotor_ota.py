"""v1.7.0: modelos de display, contagem LOS/AOS, A/B MAIN↔SUB, km/h, rotor GS-232, OTA automático,
Configurações em abas e tabela de passagens sem rolagem horizontal."""
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ----------------------------------------------------------------- display
def test_countdown_and_indicator_priority():
    from sat_tool.lcd import LcdState, countdown_text, indicator_tags, smeter_text
    assert countdown_text(342) == "5:42" and countdown_text(28) == "0:28" and countdown_text(3900) == "1H05"
    assert smeter_text(15) == "S9" and smeter_text(18) == "S9+12" and smeter_text(5) == "S3"
    st = LcdState(visible=True, los_s=25, sat_on=True, link="CAT", auto=True, doppler_hz=-6800, elevation=12)
    tags = indicator_tags(st)
    assert tags[0] == ("LOS 0:25", True)                 # contagem primeiro e piscando nos últimos 30 s
    st = LcdState(visible=False, aos_s=754)
    assert indicator_tags(st)[0] == ("AOS 12:34", False)
    assert all(not t[0].startswith(("LOS", "AOS")) for t in indicator_tags(LcdState()))


def test_sides_follow_ts2000_layout_and_rx_only():
    from sat_tool.lcd import LcdState, sides
    st = LcdState(rx_hz=436_795_120, tx_hz=145_850_340)
    main, sub = sides(st)
    assert (main["name"], main["role"], main["hz"]) == ("MAIN", "RX", 436_795_120)
    assert (sub["name"], sub["role"], sub["hz"]) == ("SUB", "TX", 145_850_340)
    st.swapped = True
    main, sub = sides(st)
    assert main["role"] == "TX" and main["hz"] == 145_850_340 and sub["role"] == "RX"
    st.swapped, st.rx_only = False, True
    assert sides(st)[1]["off"] is True


def test_every_model_renders_with_clickable_keys():
    """Roda em processo próprio: outros testes criam QCoreApplication (QWidget exige QApplication)."""
    source = textwrap.dedent(r'''
        from sat_tool.qt_compat import QApplication
        from sat_tool.lcd import LcdDisplay, MODELS
        app = QApplication([])
        for model in MODELS:
            for (w, h), dpr in (((780, 132), 1.0), ((560, 132), 1.25), ((900, 150), 2.0)):
                d = LcdDisplay(model=model, font="negrito")
                d.set_state(rx_hz=436_795_120, tx_hz=145_850_340, rx_mode="FM", tx_mode="FM", signal=18, power_w=25,
                            swr=1.2, sat_on=True, link="CAT", auto=True, doppler_hz=-6800, visible=True, elevation=38,
                            los_s=342)
                img, keys = d.render_image(w, h, dpr)
                assert img.width() == round(w * dpr) and img.height() == round(h * dpr), model
                assert set(keys) == {"swap", "rxonly", "type", "light"}  # v1.7.1: TIPO e LUZ, model
                for rect in keys.values():
                    assert 0 <= rect.left() and rect.right() <= w and 0 <= rect.top() and rect.bottom() <= h, (model, rect)
                d._keys = keys
                assert d.key_at(keys["swap"].center()) == "swap" and d.key_at(keys["rxonly"].center()) == "rxonly"
        print("OK")
    ''')
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-c", source], cwd=ROOT, capture_output=True, text=True, timeout=120, env=env)
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr


def test_dot_matrix_dots_always_on_integer_pixels():
    """Causa dos 'pixels defeituosos' da v1.6.0: pontos em coordenadas fracionárias."""
    from sat_tool.lcd import _Matrix

    class Rec:
        calls = []

        def fillRect(self, *args):
            self.calls.append(args)
    rec = Rec()
    m = _Matrix(rec, 975, 165, 165 / 132, "âmbar", bold=True)
    m.digits(12.7, 35.4, "436.795.1", 6)
    digit_calls = list(rec.calls)
    m.tag(10.3, 8.8, "MAIN")
    assert rec.calls and all(isinstance(v, int) for call in rec.calls for v in call[:4])
    sizes = {(c[2], c[3]) for c in digit_calls}
    assert sizes == {(5, 5)}                      # pitch 6, grade de 1 px: todos os pontos iguais


def test_display_settings_defaults_and_app_wiring():
    from sat_tool.config import DEFAULTS
    assert DEFAULTS["display_model"] == "matriz" and DEFAULTS["display_font"] == "normal"
    assert DEFAULTS["cat_details_visible"] is False and DEFAULTS["auto_update"] is True
    app = (ROOT / "sat_tool" / "app.py").read_text(encoding="utf-8")
    for page in ('settings_page("Aparência")', 'settings_page("Estação")', 'settings_page("Rádio")',
                 'settings_page("Rotores")'):
        assert page in app
    assert "self.lcd.set_state(los_s=(event[\"los\"]-now).total_seconds(),aos_s=None)" in app
    assert "'radial_m_s':radial_kmh_text(pos['radial_m_s'])" in app


def test_radial_velocity_in_kmh():
    from sat_tool.passfmt import radial_kmh_text
    assert radial_kmh_text(-6800) == "−24.480 km/h"
    assert radial_kmh_text(1234.5) == "+4.444 km/h"
    assert radial_kmh_text(0.05) == "0 km/h"
    assert radial_kmh_text(-6800, "en") == "−24,480 km/h"


# ----------------------------------------------------------------- A/B (MAIN↔SUB) no TS-2000
class SlowSA:
    """Simula o TS-2000 que demora para refletir a nova orientação no SA (ou recusa)."""
    is_open = True

    def __init__(self, delay_reads=2, accept=True):
        self.orientation, self.pending, self.delay, self.accept = "1", None, delay_reads, accept
        self.writes, self.answer = [], b""

    def reset_input_buffer(self): pass
    def flush(self): pass
    def close(self): pass

    def write(self, raw):
        cmd = raw.decode()
        self.writes.append(cmd)
        if cmd == "SA;":
            if self.pending and self.delay <= 0:
                self.orientation, self.pending = self.pending, None
            self.delay -= 1
            self.answer = f"SA10{self.orientation}0000;".encode()
        elif cmd.startswith("SA") and len(cmd) == 10:
            if self.accept:
                self.pending = cmd[4]
            self.answer = b""
        else:
            raise AssertionError(cmd)

    def read_until(self, _):
        return self.answer


def make_radio(sim):
    from sat_tool.cat import RadioState, TS2000
    r = TS2000()
    r.port, r.state = sim, RadioState(True, "Kenwood TS-2000", sat=True)
    return r


def test_ab_swap_waits_for_radio_readback():
    sim = SlowSA(delay_reads=2)
    radio = make_radio(sim)
    radio.set_orientation(main_downlink=False, settle_s=0)
    assert radio.main_downlink_expected is False and sim.orientation == "0"
    assert "SA1000000;" in sim.writes and not any(w.startswith(("TX", "RX")) for w in sim.writes)


def test_ab_swap_refused_explains_panel_fallback():
    radio = make_radio(SlowSA(accept=False))
    with pytest.raises(RuntimeError, match="painel"):
        radio.set_orientation(main_downlink=False, settle_s=0, attempts=3)
    assert radio.main_downlink_expected is True


def test_app_shows_ab_failures_and_follows_radio_orientation():
    app = (ROOT / "sat_tool" / "app.py").read_text(encoding="utf-8")
    err = app.split("    def background_error(self,key,message):", 1)[1]
    assert 'if key=="cat-swap":' in err and 'QMessageBox.warning(self,"Inverter MAIN↔SUB",message)' in err
    assert "a orientação real lida (SA) manda" in app


# ----------------------------------------------------------------- rotor GS-232 (G-5400B + ERC-M)
class FakeRotorSerial:
    is_open = True

    def __init__(self, port=None, baudrate=None, timeout=None, write_timeout=None, reply="AZ=123  EL=045"):
        self.reply, self.writes = reply, []

    def reset_input_buffer(self): pass
    def flush(self): pass
    def close(self): self.is_open = False

    def write(self, raw):
        self.writes.append(raw.decode())

    def read_until(self, _):
        return (self.reply + "\r").encode() if self.writes and self.writes[-1] == "C2\r" else b""


def test_rotor_protocol_and_safety_commands():
    from sat_tool.rotor import GS232Rotor, RotorProfile, move_command, parse_position, probe_port
    assert parse_position("AZ=123  EL=045") == (123.0, 45.0)
    assert parse_position("+0359+0170") == (359.0, 170.0)
    assert move_command(12.4, 5) == "W012 005\r"
    holder = {}

    def opener(**kw):
        holder["s"] = FakeRotorSerial(**kw)
        return holder["s"]
    rotor = GS232Rotor()
    assert rotor.connect("COM7", 9600, opener=opener) == (123.0, 45.0)
    prof = RotorProfile()
    rotor.move(500, 200, prof)                     # limites mecânicos respeitados
    rotor.stop()
    assert holder["s"].writes == ["C2\r", "W450 180\r", "S\r"]
    assert probe_port("COM9", opener=lambda **kw: FakeRotorSerial(reply="garbage")) is None


def test_rotor_pass_plan_overlap_flip_and_fallback():
    from sat_tool.rotor import PROFILES, RotorProfile, plan_pass, to_rotor
    track = [(i, (300 + i * 12) % 360, min(i, 10 - i) * 8) for i in range(11)]   # cruza o norte
    g5400 = PROFILES["g5400b"]
    plan = plan_pass(track, g5400)
    assert plan["mode"] == "normal" and plan["track"][-1][0] == 420     # usa a sobreposição de 450°
    assert to_rotor(10, 30, plan, g5400, when=6) == (370.0, 30.0)
    plan = plan_pass(track, RotorProfile(az_max=360))
    assert plan["mode"] == "flip" and plan["track"][0] == (120.0, 180.0)
    assert to_rotor(10, 30, plan, RotorProfile(az_max=360), when=6) == (190.0, 150.0)
    assert plan_pass(track, PROFILES["az360_el90"])["mode"] == "reposiciona"


def test_rotor_never_moves_on_selection_and_stops_on_close():
    ui = (ROOT / "sat_tool" / "rotor_ui.py").read_text(encoding="utf-8")
    app = (ROOT / "sat_tool" / "app.py").read_text(encoding="utf-8")
    assert "if not self.rotor_tracking or self.sat is None:" in ui
    assert "self.rotor_shutdown()" in app.split("    def closeEvent(self,event):", 1)[1][:200]
    assert "self.rotor_stop(\"sem resposta do controlador\")" in ui


# ----------------------------------------------------------------- OTA automático
def _auto_self(busy="", pending=(), auto=True, failed=None):
    calls = []
    s = SimpleNamespace(
        available_update=SimpleNamespace(version="9.9.9"), pending_jobs=set(pending),
        config=SimpleNamespace(values={"auto_update": auto}), AUTO_UPDATE_RETRY_SECONDS=6 * 3600,
        _auto_update_failed=failed, operation_busy=lambda: busy, _auto_update_timer_armed=True,
        version_btn=SimpleNamespace(setText=lambda t: calls.append(("text", t)), setToolTip=lambda t: None),
        log=lambda m: None, show_tray_message=lambda *a: None,
        request_update=lambda **kw: calls.append(("update", kw)))
    s.try_auto_update = lambda data=None: None
    return s, calls


def test_auto_update_installs_without_prompt_when_free():
    from sat_tool.app import MainWindow
    s, calls = _auto_self()
    MainWindow.try_auto_update(s)
    assert ("update", {"manual": True, "silent": True}) in calls


def test_auto_update_defers_during_operation_and_respects_option_and_backoff():
    from sat_tool.app import MainWindow
    s, calls = _auto_self(busy="passagem em curso com Auto CAT")
    MainWindow.try_auto_update(s)
    assert not any(c[0] == "update" for c in calls) and "instala ao ficar livre" in calls[0][1]
    s, calls = _auto_self(auto=False)
    MainWindow.try_auto_update(s)
    assert calls == []
    s, calls = _auto_self(failed={"version": "9.9.9", "at": time.time()})
    MainWindow.try_auto_update(s)
    assert calls == []
    app = (ROOT / "sat_tool" / "app.py").read_text(encoding="utf-8")
    check = app.split("        if key=='update-check':", 1)[1][:900]
    assert "self.try_auto_update(data)" in check and "self.maybe_prompt_update(data)" in check


# ----------------------------------------------------------------- janela (processo separado)
def test_window_settings_tabs_cat_details_and_pass_table():
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
            def stop(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda directory:[]
        gui.MainWindow.background=lambda self,key,fn:None
        gui.MainWindow.check_for_updates=lambda self,force=False:None
        with tempfile.TemporaryDirectory() as directory:
            gui.Config=lambda:Config(Path(directory))
            application=gui.QApplication([])
            w=gui.MainWindow()
            names=[w.settings_tabs.tabText(i) for i in range(w.settings_tabs.count())]
            assert names==["Aparência","Estação","Rádio","Rotores","Geral"],names
            assert not w.cat_details_box.isVisibleTo(w) and not w.cat_details_toggle.isChecked()
            w.cat_details_toggle.setChecked(True)
            assert w.cat_details_box.isVisibleTo(w) and w.config.values["cat_details_visible"] is True
            assert not w.rotor_bar.isVisibleTo(w)               # rotor desabilitado por padrão
            w.display_model.setCurrentIndex(w.display_model.findData("lcd7"))
            assert w.lcd.model=="lcd7" and w.config.values["display_model"]=="lcd7"
            assert not w.display_font.isEnabled()
            w.open_settings("Estação")
            assert w.tabs.currentIndex()==2 and w.settings_tabs.tabText(w.settings_tabs.currentIndex())=="Estação"
            w.fit_pass_columns()
            assert w.pass_table.horizontalScrollBarPolicy()==gui.Qt.ScrollBarAlwaysOff
            assert w.pass_table.minimumWidth()>200
            print("OK")
    ''')
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox")
    result = subprocess.run([sys.executable, "-c", source], cwd=ROOT, capture_output=True, text=True, timeout=120, env=env)
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr
