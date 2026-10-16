"""v1.3.8 online CAT, selected-satellite passes, and no manual pass recalc."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace

from sat_tool.operations import select_selected_satellite_pass
from sat_tool.cat import TS2000,RadioState
from test_v131_cat_connect import rig_with_sim

ROOT=Path(__file__).resolve().parents[1]


def pass_item(ident,now,minutes,el=55):
    aos=now+timedelta(minutes=minutes)
    return dict(id=str(ident),name="SO-50" if str(ident)=="27607" else "OTHER",
                aos=aos,tca=aos+timedelta(minutes=5),
                los=aos+timedelta(minutes=10),max_el=el)


def test_selected_satellite_pass_ignores_earlier_other_satellite():
    now=datetime(2026,10,16,12,tzinfo=timezone.utc)
    entries=[pass_item("999",now,1),pass_item("27607",now,7),
             pass_item("27607",now,25)]
    channel=dict(downlink_hz=436795000,uplink_hz=145850000,
                 mode="FM",rx_only=False)
    event=select_selected_satellite_pass(entries,"27607",channel,now)
    assert event["id"]=="27607"
    assert event["aos"]==entries[1]["aos"]
    assert event["channel"] is channel
    assert event["in_progress"] is False
    assert select_selected_satellite_pass(entries,"25544",channel,now) is None


def test_current_selected_pass_precedes_future_while_visible():
    now=datetime(2026,10,16,12,tzinfo=timezone.utc)
    active=pass_item("27607",now,-3)
    future=pass_item("27607",now,20)
    event=select_selected_satellite_pass([future,active],"27607",
            dict(mode="FM",downlink_hz=436795000),now)
    assert event["in_progress"] is True
    assert event["aos"]==active["aos"]


def test_fast_radio_poll_only_reads_sa_fa_fb_no_optional_meters_or_fc():
    radio,sim=rig_with_sim()
    radio.poll_tracking()
    assert sim.writes==["SA;","FA;","FB;"]
    assert radio.state.uplink==145950000
    assert radio.state.downlink==435847500


def test_live_doppler_write_reads_compact_state_and_never_keys_ptt():
    radio,sim=rig_with_sim()
    state=radio.set_frequencies(145850000,436795000)
    assert state.uplink==145850000
    assert state.downlink==436795000
    assert sim.writes==["SA;","FA00436795000;","FB00145850000;",
                        "SA;","FA;","FB;"]
    assert not any(x.startswith(("TX","RX","FC","MD")) for x in sim.writes)


def test_cat_scheduler_decoupled_from_gis_and_fast_readback_visible():
    source=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "self.cat_live_timer.start(250)" in source
    assert "self.cat_live_timer.timeout.connect(self.cat_live_tick)" in source
    assert 'self.background("cat-poll",self.radio.poll_telemetry if active else self.radio.poll)' in source
    assert "self.update_cat_sync_status(state)" in source
    assert "CAT SYNC" in source and "DIVERGENTE" in source
    assert "self.last_cat_track_completed=time.monotonic()" in source
    assert "self.track_cat_frequencies(now)" not in source.split("    def tick(self):",1)[1].split("    def background_result(",1)[0]


def test_selected_pass_ui_no_manual_recalculate_button_and_periodic_refresh():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "Recalcular passagens" not in app
    assert "refresh_passes_btn" not in app
    assert 'group("PASSAGENS DO SATÉLITE SELECIONADO · 36 H")' in app
    assert "nextpass.setMinimumWidth(520)" in app
    assert "self.pass_table.setWordWrap(False)" in app
    # AOS/TCA/LOS/elevação recebem só a largura necessária; o espaço
    # restante fica dividido entre nome do satélite e modos.
    assert "for col in (1,2,3,4):" in app
    assert "pass_header.setSectionResizeMode(col,QHeaderView.ResizeToContents)" in app
    assert "for col in (0,5):" in app
    assert "pass_header.setSectionResizeMode(col,QHeaderView.Stretch)" in app
    assert "cell.setToolTip(value)" in app
    assert "cell.setTextAlignment(" in app
    assert "self.refresh_passes()" in app.split("    def choose_satellite(self):",1)[1].split("    def refresh_modes(",1)[0]
    assert "time.monotonic()-self._pass_refresh_last>=300" in app
    assert "select_selected_satellite_pass(self.passes,selected,channel,now)" in app


def test_radio_driver_blocks_sat_off_even_fast_tracking():
    radio,sim=rig_with_sim(sat=False)
    from pytest import raises
    with raises(RuntimeError,match="SAT"):
        radio.set_frequencies(145850000,436795000)
    assert sim.writes==["SA;"]
