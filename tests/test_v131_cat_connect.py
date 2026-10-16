"""v1.3.1 regression: CAT tune starts on connect/opt-in/SAT, not only dropdown changes.

No radio transmission: simulated serial checks the exact CAT commands allowed.
"""
from pathlib import Path
from sat_tool.cat import RadioState, TS2000

ROOT=Path(__file__).resolve().parents[1]

def test_auto_cat_trigger_paths_and_independent_status():
    text=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    connect=text.split("    def toggle_connection(self):",1)[1].split("    def enable_satellite(self):",1)[0]
    assert 'self.render_radio_state(st)\n            self.auto_tune_selected_satellite()' in connect
    enable=text.split("    def enable_satellite(self):",1)[1].split("    def render_radio_state(",1)[0]
    assert "self.auto_tune_selected_satellite()" in enable
    preference=text.split("    def change_auto_cat(",1)[1].split("    def save_tle_settings(",1)[0]
    assert 'if enabled:\n            self.auto_tune_selected_satellite()' in preference
    assert 'self.cat_tune_now.clicked.connect(self.tune_selected_now)' in text
    assert "self.cat_tune_status=label(" in text
    assert "self.cat_tune_status.setText(" in text
    assert 'if not force and not self.config.values.get("cat_auto_select",False)' in text
    assert 'if not self.radio.state.sat:' in text
    assert 'if "cat-autotune" in self.pending_jobs:' in text


class SerialCAT:
    is_open=True
    def __init__(self,sat=True):
        self.writes=[]
        self.down=435_847_500
        self.up=145_950_000
        self.main_mode="2"
        self.sat=sat
        self.answer=b""
    def reset_input_buffer(self):pass
    def flush(self):pass
    def close(self):self.is_open=False
    def write(self,raw):
        cmd=raw.decode("ascii");self.writes.append(cmd)
        if cmd=="ID;":self.answer=b"ID019;"
        elif cmd=="SA;":self.answer=("SA1010000;" if self.sat else "SA0010000;").encode()
        elif cmd=="FA;":self.answer=f"FA{self.down:011d};".encode()
        elif cmd=="FB;":self.answer=f"FB{self.up:011d};".encode()
        elif cmd=="MD;":self.answer=f"MD{self.main_mode};".encode()
        elif cmd.startswith("FA"):self.down=int(cmd[2:-1]);self.answer=b""
        elif cmd.startswith("FB"):self.up=int(cmd[2:-1]);self.answer=b""
        elif cmd.startswith("MD"):self.main_mode=cmd[2:-1];self.answer=b""
        elif cmd=="SM0;":self.answer=b"SM00012;"
        elif cmd=="SM1;":self.answer=b"SM10004;"
        elif cmd=="PC;":self.answer=b"PC025;"
        elif cmd=="RM;":self.answer=b"RM30011;"
        else:raise AssertionError("Unexpected CAT command: "+cmd)
    def read_until(self,delimiter):return self.answer

def rig_with_sim(sat=True):
    sim=SerialCAT(sat=sat)
    radio=TS2000()
    radio.port=sim
    radio.state=RadioState(True,"Kenwood TS-2000",sat=sat)
    radio._last_optional_poll=10**20
    return radio,sim

def test_satellite_preset_changes_frequencies_and_main_mode_without_ptt():
    radio,sim=rig_with_sim()
    radio.set_satellite_channel(435_847_000,145_951_000,"FM")
    assert sim.down==435_847_000
    assert sim.up==145_951_000
    assert sim.main_mode=="4"
    assert "MD4;" in sim.writes
    assert "FA00435847000;" in sim.writes
    assert "FB00145951000;" in sim.writes
    assert not any(cmd.startswith(("TX","RX","MO","PS","SA1")) for cmd in sim.writes)

def test_rx_only_does_not_tune_tx_sub_frequency():
    radio,sim=rig_with_sim()
    radio.set_satellite_channel(145_825_000,None,"FM")
    assert sim.up==145_950_000
    assert "FB00145950000;" not in sim.writes
    assert "FA00145825000;" in sim.writes

def test_sat_mode_required_before_any_frequency_writes():
    import pytest
    radio,sim=rig_with_sim(sat=False)
    with pytest.raises(RuntimeError,match="SAT"):
        radio.set_satellite_channel(435_847_000,145_951_000,"FM")
    assert not any(s.startswith(("FA00","FB00","MD4")) for s in sim.writes)


def test_read_only_diagnostic_reports_actual_radio_frequency_and_mode():
    from sat_tool.cat import decode_satellite_status
    radio,sim=rig_with_sim()
    sim.down=436_795_000
    sim.up=145_850_000
    sim.main_mode="4"
    result=radio.read_diagnostics()
    assert result["raw"]["ID"]=="ID019;"
    assert result["sat"]["sat"] is True
    assert result["sat"]["main_downlink"] is True
    assert result["frequency_hz"]=={"FA":436_795_000,"FB":145_850_000}
    assert result["main_mode"]=="FM"
    assert result["errors"]=={}
    assert sim.writes==["ID;","SA;","FA;","FB;","MD;"]
    reversed_status=decode_satellite_status("SA1000000;")
    assert reversed_status["sat"] is True
    assert reversed_status["main_downlink"] is False


def test_radio_operation_displays_actual_cat_readback_separate_from_prediction():
    text=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert 'self.cat_live_label=label("RÁDIO REAL (CAT)' in text
    assert 'self.cat_live_label.setText(' in text
    assert "decode_satellite_status(st.sat_raw)" in text
    assert 'self.cat_diagnose.clicked.connect(self.diagnose_cat)' in text
    diag=text.split("    def diagnose_cat(self):",1)[1].split("    def tune_selected_now(self):",1)[0]
    assert 'self.background("cat-diagnostic",self.radio.read_diagnostics)' in diag
    assert '"FA"' in diag and '"FB"' in diag and '"SA"' in diag
