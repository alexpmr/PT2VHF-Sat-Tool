"""Auto CAT must retune continuously even below the horizon (TS-2000 simulated).

No PTT or serial hardware is accessed by these regression tests.
"""
import json
from types import SimpleNamespace

from sat_tool.app import MainWindow
from sat_tool.config import Config
from test_v137_live_auto_cat import Indicator, live_window


def test_legacy_out_of_view_false_is_migrated_to_always_on(tmp_path):
    config=Config(tmp_path)
    values=dict(config.values)
    values["cat_doppler_out_of_view"]=False
    (tmp_path/"settings.json").write_text(json.dumps(values),encoding="utf-8")
    newer=Config(tmp_path)
    assert newer.values["cat_doppler_out_of_view"] is True
    assert json.loads((tmp_path/"settings.json").read_text(encoding="utf-8"))["cat_doppler_out_of_view"] is True


def test_below_horizon_keeps_tuning_even_with_legacy_false(monkeypatch):
    import sat_tool.app as gui
    clock=[100.0]
    monkeypatch.setattr(gui.time,"monotonic",lambda:clock[0])
    win,radio,sent=live_window()
    win.config.values["cat_doppler_out_of_view"]=False
    win.last_pos={"visible":False,"elevation":-38.5}
    MainWindow.track_cat_frequencies(win,None)
    assert radio.tunes==[(145850012,436800030)]
    assert sent[0][0]=="cat-track"
    win.last_freqs=radio.state.uplink,radio.state.downlink
    win.corrected=lambda:(145850025,436800080)
    clock[0]=101.5
    MainWindow.track_cat_frequencies(win,None)
    assert radio.tunes==[(145850012,436800030),(145850025,436800080)]
    assert len(sent)==2


def test_crosses_aos_los_without_interrupting_auto_cat(monkeypatch):
    import sat_tool.app as gui
    clock=[100.0]
    monkeypatch.setattr(gui.time,"monotonic",lambda:clock[0])
    win,radio,sent=live_window()
    win.config.values["cat_doppler_out_of_view"]=False
    for step,(visible,elevation,up,down) in enumerate([
        (False,-12.0,145850012,436800030),
        (True,15.0,145850016,436800040),
        (True,2.0,145850020,436800051),
        (False,-7.0,145850025,436800068),
    ]):
        win.last_pos={"visible":visible,"elevation":elevation}
        win.corrected=lambda u=up,d=down:(u,d)
        clock[0]=100.0+step*1.5
        MainWindow.track_cat_frequencies(win,None)
        assert radio.tunes[-1]==(up,down)
        win.last_freqs=up,down
    assert len(radio.tunes)==4
    assert win.cat_tracking_armed


def test_horizon_independent_prediction_and_readback_scheduler(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    monkeypatch.setattr(gui,"position",lambda *a,**k:{"radial_m_s":-205.0,"visible":False,"elevation":-24.0})
    preview=[]
    calls=[]
    win=SimpleNamespace(
        cat_tracking_armed=True,
        config=SimpleNamespace(values={"cat_auto_select":True,"cat_doppler_out_of_view":False}),
        radio=SimpleNamespace(connected=True,poll_tracking=lambda:"readback"),
        sat=object(),ts=object(),saved_station=lambda:object(),
        last_freqs=(145850000,436800000),last_cat_frequency_readback=100.0,
        pending_jobs=set(),
        preview_doppler=lambda **kw:preview.append(kw),
        background=lambda key,task:calls.append((key,task())),
        track_cat_frequencies=lambda now:calls.append(("track",now)),
        cat_sync_status=Indicator(),
    )
    MainWindow.cat_live_tick(win)
    assert preview[-1]["pos"]["visible"] is False
    assert calls[0][0]=="track"
    win.last_cat_frequency_readback=0.0
    MainWindow.cat_live_tick(win)
    assert calls[-1]==("cat-readback","readback")


def test_disabled_and_sat_off_do_not_write_outside_horizon(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    win,radio,sent=live_window()
    win.config.values["cat_doppler_out_of_view"]=False
    win.cat_tracking_armed=False
    MainWindow.track_cat_frequencies(win,None)
    assert not sent
    win.cat_tracking_armed=True
    radio.state.sat=False
    MainWindow.track_cat_frequencies(win,None)
    assert not sent


def test_no_visibility_gate_or_obsolete_setting_in_active_cat():
    from pathlib import Path
    app=(Path(__file__).resolve().parents[1]/"sat_tool"/"app.py").read_text(encoding="utf-8")
    loop=app.split("    def track_cat_frequencies(self,now):",1)[1].split("    def cat_live_tick(self):",1)[0]
    assert "cat_doppler_allowed" not in loop
    assert "cat_doppler_out_of_view" not in loop
    assert "self.cat_outside" not in app
    assert "self.cat_live_timer.start(250)" in app
    assert "self.track_cat_frequencies(now)" in app
