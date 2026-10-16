"""v1.3.11: real CAT FA/FB readback must drive online Doppler reconciliation."""
from pathlib import Path
from types import SimpleNamespace
import time

from sat_tool.app import MainWindow
from test_v137_live_auto_cat import Indicator,live_window

ROOT=Path(__file__).resolve().parents[1]


def test_real_radio_dial_change_is_corrected_even_if_prediction_did_not_change(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    win,radio,sent=live_window()
    win.last_freqs=(145850012,436800030)
    win.corrected=lambda: (145850012,436800030)
    radio.state.uplink=145875000
    radio.state.downlink=436825000
    MainWindow.track_cat_frequencies(win,None)
    assert radio.tunes==[(145850012,436800030)]
    assert sent[0][0]=="cat-track"
    assert win.cat_tracking_armed


def test_matching_readback_does_not_repeat_unnecessary_cat_writes(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    win,radio,sent=live_window()
    win.last_freqs=(145850012,436800030)
    win.corrected=lambda: (145850012,436800030)
    radio.state.uplink=145850012
    radio.state.downlink=436800030
    MainWindow.track_cat_frequencies(win,None)
    assert radio.tunes==[]
    assert sent==[]


def test_cat_sync_uses_current_predicted_vs_readback_not_old_requested(monkeypatch):
    import sat_tool.app as gui
    clock=100.0
    monkeypatch.setattr(gui.time,"monotonic",lambda:clock)
    status,top=Indicator(),Indicator()
    win=SimpleNamespace(
        corrected=lambda: (145850125,436795900),
        cat_sync_status=status,pred_cat_status=top,
        cat_last_requested=(145850000,436795000),
        cat_last_roundtrip_ms=18,
        last_cat_frequency_readback=100.0,
        threshold=SimpleNamespace(value=lambda:1),
    )
    actual=SimpleNamespace(sat=True,uplink=145850000,downlink=436795000)
    MainWindow.update_cat_sync_status(win,actual)
    assert "DIVERGENTE" in status.message
    assert "RX +900 Hz" in top.message
    assert "TX +125 Hz" in top.message
    actual.uplink=145850125
    actual.downlink=436795900
    MainWindow.update_cat_sync_status(win,actual)
    assert "SINCRONIZADO" in status.message


def test_fast_cat_scheduler_polls_actual_radio_frequencies_independently(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    monkeypatch.setattr(gui,"position",lambda *a,**k:{"radial_m_s":130.0,"visible":True})
    requests=[]
    pos=[]
    win=SimpleNamespace(
        cat_tracking_armed=True,
        config=SimpleNamespace(values={"cat_auto_select":True}),
        radio=SimpleNamespace(connected=True,poll_tracking=lambda:"radio-readback"),
        sat=object(), ts=object(),saved_station=lambda:object(),
        last_freqs=(145850000,436795000),
        last_cat_frequency_readback=95.0,
        pending_jobs=set(),
        preview_doppler=lambda **kw: pos.append(kw),
        background=lambda key,task:requests.append((key,task())),
        track_cat_frequencies=lambda now:requests.append(("track",now)),
        cat_sync_status=Indicator(),
    )
    MainWindow.cat_live_tick(win)
    assert len(pos)==1 and pos[0]["pos"]["radial_m_s"]==130
    assert requests==[("cat-readback","radio-readback")]
    win.last_cat_frequency_readback=100.0
    MainWindow.cat_live_tick(win)
    assert requests[1][0]=="track"


def test_radio_prediction_comparison_is_visible_near_top_cards():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert 'self.pred_cat_status=label("CAT · sem leitura recente FA/FB")' in app
    assert "ov.addWidget(self.pred_cat_status)" in app
    assert '"cat-readback" in self.pending_jobs' in app
    assert 'self.background("cat-readback",self.radio.poll_tracking)' in app
    assert 'if key=="cat-readback":' in app
    assert 'self.update_cat_sync_status(data)' in app
    assert 'observed=self.radio.state' in app
    assert 'last_request_delta<threshold' in app
    assert 'observed_delta is not None and observed_delta<threshold' in app
    assert '"cat-readback","cat-diagnostic"' in app
    assert "Sintonizar agora" not in app


def test_catsync_never_claims_success_with_stale_radio_reads(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:105.0)
    win=SimpleNamespace(
        corrected=lambda:(145850000,436795000),
        cat_sync_status=Indicator(),pred_cat_status=Indicator(),
        cat_last_roundtrip_ms=20,last_cat_frequency_readback=100.0,
        threshold=SimpleNamespace(value=lambda:1)
    )
    current=SimpleNamespace(sat=True,uplink=145850000,downlink=436795000)
    MainWindow.update_cat_sync_status(win,current)
    assert "AGUARDANDO READBACK" in win.cat_sync_status.message
    assert "SINCRONIZADO" not in win.pred_cat_status.message
