"""v1.3.12: Doppler tracking must keep writing after initial manual selection."""
from types import SimpleNamespace
from sat_tool.app import MainWindow
from test_v137_live_auto_cat import live_window,Indicator


def test_long_running_cat_corrections_without_reclick_or_reconnect(monkeypatch):
    import sat_tool.app as gui
    clock=[100.]
    monkeypatch.setattr(gui.time,"monotonic",lambda:clock[0])
    win,radio,sent=live_window()
    # Simulates a TS-2000 remaining connected, with a new orbital prediction
    # every 1.5 seconds during 10 minutes, including before AOS/after LOS.
    for step in range(400):
        clock[0]=100.0+1.5*step
        win.last_pos={"visible":100<step<300,"elevation":-15 if step<100 or step>=300 else 25}
        desired=(145850012+step*2,436800030-step*6)
        win.corrected=lambda target=desired:target
        MainWindow.track_cat_frequencies(win,None)
        win.last_freqs=desired
    assert len(radio.tunes)==400
    assert radio.tunes[0]!=(radio.tunes[-1])
    assert len(sent)==400
    assert radio.connected and win.cat_tracking_armed


def test_cat_live_scheduler_writes_before_readback(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    monkeypatch.setattr(gui,"position",lambda *a,**k:{"radial_m_s":110.,"visible":False})
    jobs=[]
    win=SimpleNamespace(
        cat_tracking_armed=True,
        config=SimpleNamespace(values={"cat_auto_select":True}),
        radio=SimpleNamespace(connected=True,poll_tracking=lambda:"FA/FB"),
        sat=object(),ts=object(),saved_station=lambda:object(),
        last_freqs=(145850000,436800000),last_cat_frequency_readback=0.,
        pending_jobs=set(),preview_doppler=lambda **kw:None,
        track_cat_frequencies=lambda now: jobs.append("track") or False,
        background=lambda key,fn:jobs.append(key),
        cat_sync_status=Indicator(),
    )
    MainWindow.cat_live_tick(win)
    assert jobs==["track","cat-readback"]


def test_long_running_scheduler_does_not_write_with_sat_off(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    win,radio,sent=live_window()
    radio.state.sat=False
    for _ in range(60):
        MainWindow.track_cat_frequencies(win,None)
    assert not radio.tunes
