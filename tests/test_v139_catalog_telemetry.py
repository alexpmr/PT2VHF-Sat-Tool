"""v1.3.9 regression: entire catalog updates, row favorite color, CAT telemetry."""
from pathlib import Path

from sat_tool.selection import transmitter_batch_ids
from test_v131_cat_connect import rig_with_sim

ROOT=Path(__file__).resolve().parents[1]


def test_full_frequency_update_includes_unselected_and_unfiltered_satellites():
    orbits={str(i):{"OBJECT_NAME":"SAT-"+str(i)} for i in range(1,25)}
    result=transmitter_batch_ids(3,None,["1"],["2"],orbits)
    assert len(result)==len(orbits)
    assert "3" in result and "24" in result
    assert len(set(result))==len(orbits)


def test_live_read_only_telemetry_queries_cat_mode_and_meters():
    radio,sim=rig_with_sim()
    radio._last_optional_poll=0
    state=radio.poll_telemetry()
    assert state.sat
    assert state.mode=="USB"
    assert state.sub_receiver==435450000
    assert state.signal_main==12 and state.signal_sub==4
    assert state.power_set_w==25
    assert state.meter_type=="ALC" and state.meter_value==11
    assert sim.writes==["SA;","MD;","FC;","SM0;","SM1;","PC;","RM;"]
    assert not any(x.startswith(("TX","RX","FA00","FB00","SA1")) for x in sim.writes)


def test_telemetry_quick_refresh_skips_slower_optional_power_meter():
    radio,sim=rig_with_sim()
    state=radio.poll_telemetry()
    assert state.signal_main==12 and state.signal_sub==4
    assert sim.writes==["SA;","MD;","FC;","SM0;","SM1;"]


def test_catalog_ui_uses_7_columns_yellow_black_rows_click_toggle():
    source=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "self.catalog_table=QTableWidget(0, 7)" in source
    assert '"Selecionado", "Satélite"' not in source
    assert 'self.catalog_table.cellClicked.connect(self.queue_catalog_single_click)' in source
    assert 'self.catalog_table.cellDoubleClicked.connect(self.select_catalog_satellite)' in source
    assert 'self.catalog_click_timer.timeout.connect(self.commit_catalog_single_click)' in source
    assert 'self.catalog_table.cellDoubleClicked.connect(self.select_catalog_satellite)' in source
    assert 'self.catalog_table.itemChanged.connect(self.catalog_satellite_checked)' not in source
    assert 'QColor("#ffe36a")' in source
    assert 'QColor("#111111")' in source
    assert 'self.catalog_table.setSortingEnabled(False)' in source
    assert "self._catalog_filtered_ids=ids" in source
    assert "ids=transmitter_batch_ids(3,None,[],[],self.omm)" in source
    assert "catalog_refresh_scope" not in source


def test_frequency_cards_only_show_mode_and_corrected_frequency():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    view=app.split("    def preview_doppler(",1)[1].split("    def nominal_hz(",1)[0]
    assert 'f"RX / DOWNLINK · {rx_mode}\\n{self.radio_freq(calc[\'rx_hz\'])}"' in view
    assert 'f"TX / UPLINK · {tx_mode}\\n{self.radio_freq(calc[\'tx_hz\'])}"' in view
    assert "Doppler {calc[" not in view
    assert "self.pred_rx.setToolTip" in view


def test_radio_extra_information_is_real_readback_not_predicted():
    source=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "self.cat_operating_detail=label(" in source
    assert "current['ctrl_sub']" in source
    assert "current['trace']" in source
    assert "current['memory_mode']" in source
    assert "decode_satellite_status(st.sat_raw)" in source
    assert "self.radio.poll_telemetry if active else self.radio.poll" in source
    assert "self.last_cat_telemetry=now_utc()" in source
    assert "interval=2.0 if active" in source
