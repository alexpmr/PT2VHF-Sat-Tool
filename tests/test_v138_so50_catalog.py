"""Regression for user-reported false 'same band' on valid SO-50 V/U CAT."""
from pathlib import Path

from sat_tool.transponder import (
    SO50_VOICE, cat_band, cat_pair_diagnostic, prioritized_transponders
)
from sat_tool.core import transponder_options
from sat_tool.frequency import parse_mhz_input

ROOT = Path(__file__).resolve().parents[1]


def test_so50_145850_436795_is_crossband_not_same_band():
    rx=parse_mhz_input("436.795000")
    tx=parse_mhz_input("145.850000")
    assert rx==436795000 and tx==145850000
    assert cat_band(rx)=="70 cm"
    assert cat_band(tx)=="2 m"
    ok,report=cat_pair_diagnostic(tx,rx)
    assert ok and "crossband válido" in report


def test_telemetry_or_same_band_entry_cannot_preempt_so50_voice():
    source=[
        {"name":"TLM", "downlink":145_960_000,"uplink":145_990_000,
         "mode":"FM","uuid":"legacy-invalid", "receive_only":False},
        {"name":"Telemetry RX only", "downlink":436_805_000,"uplink":None,
         "mode":"CW","uuid":"rx-only", "receive_only":True},
    ]
    sorted_profiles=prioritized_transponders("27607",source)
    assert sorted_profiles[0]["name"].startswith("SO-50")
    assert sorted_profiles[0]["downlink"]==436_795_000
    assert sorted_profiles[0]["uplink"]==145_850_000
    assert sorted_profiles[0]["mode"]=="FM"
    assert len(sorted_profiles)==3  # keep other transponders accessible


def test_duplicate_satnogs_145850_436795_is_not_double_listed():
    duplicate={"name":"Mode V/U", "downlink":436795000,"uplink":145850000,
               "uuid":"snogs", "mode":"FM", "receive_only":False}
    modes=prioritized_transponders(27607,[duplicate])
    assert len(modes)==1
    assert modes[0]["uuid"]==SO50_VOICE["uuid"]


def test_other_satellites_prefer_crossband_not_telemetry():
    options=[
        {"downlink":145825000,"uplink":None,"uuid":"telemetry"},
        {"downlink":436800000,"uplink":436900000,"uuid":"bad-same-band"},
        {"downlink":435800000,"uplink":145990000,"uuid":"good"},
    ]
    chosen=prioritized_transponders("25544",options)
    assert chosen[0]["uuid"]=="good"
    assert len(chosen)==3
    ok,same=cat_pair_diagnostic(436900000,436800000)
    assert not ok and "mesma banda" in same
    ok,rxonly=cat_pair_diagnostic(None,145825000)
    assert not ok and "somente RX" in rxonly
    ok,unknown=cat_pair_diagnostic(52_000_000,145_825_000)
    assert not ok and "não reconhecida" in unknown


def test_satnogs_transmitter_rows_can_be_telemetry_first():
    fake=[
        {"status":"active","description":"Telemetry","downlink_low":145_850_000,
         "uplink_low":145_920_000,"mode":"FM"},
        {"status":"active","description":"V/U repeater","downlink_low":436_795_000,
         "uplink_low":145_850_000,"mode":"FM"},
    ]
    normalized=transponder_options(fake)
    options=prioritized_transponders("27607",normalized)
    assert options[0]["uplink"]==145_850_000
    assert options[0]["downlink"]==436_795_000


def test_automated_cat_does_not_bypass_invalid_band_guard():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    tuner=app.split("    def auto_tune_selected_satellite(",1)[1].split("    def pair_linear(",1)[0]
    tracker=app.split("    def track_cat_frequencies(",1)[1].split("    def diagnose_cat(",1)[0]
    assert "safe,reason=self.selected_cat_pair_info(ul,dl)" in tuner
    assert "safe,reason=self.selected_cat_pair_info(ul,dl)" in tracker
    assert "if not safe:" in tuner and "if not safe:" in tracker
    assert "self.radio.set_frequencies(ul,dl)" in tracker
    assert "self.radio.set_satellite_channel(dl_new,ul_new,mode)" in tuner
    assert "self.options=prioritized_transponders" in app
    assert "TX=" in app and "RX=" in app
