"""v1.3.7: online 1-second CAT tracking (no one-shot tune button).

These tests simulate the Kenwood VFOs; they do not key a real transmitter.
"""
from pathlib import Path
from types import SimpleNamespace
import json

from sat_tool.config import Config
from sat_tool.app import MainWindow

ROOT = Path(__file__).resolve().parents[1]


class Value:
    def __init__(self, number):
        self.number = number

    def value(self):
        return self.number


class Indicator:
    def __init__(self):
        self.message = ""

    def setText(self, message):
        self.message = message


class MockCAT:
    def __init__(self):
        self.connected = True
        self.state = SimpleNamespace(sat=True, uplink=145850000, downlink=436800000)
        self.tunes = []

    def set_frequencies(self, up, down):
        self.tunes.append((up, down))
        self.state.uplink = up
        self.state.downlink = down
        return self.state


def live_window():
    cat = MockCAT()
    sent = []
    window = SimpleNamespace(
        cat_tracking_armed=True,
        config=SimpleNamespace(values={"cat_auto_select": True, "cat_doppler_out_of_view": True}),
        radio=cat,
        sat=object(),
        last_pos={"visible": False},
        omm_fresh=lambda: True,
        cat_tune_status=Indicator(),
        mode_combo=SimpleNamespace(currentData=lambda: 0),
        down_edit=SimpleNamespace(text=lambda: "436.8"),
        pending_jobs=set(),
        last_freqs=(145850000, 436800000),
        cat_autotune_requested_generation=42,
        cat_selection_generation=42,
        threshold=Value(1),
        interval=Value(1),
        last_tracking_write=0.0,
        corrected=lambda: (145850012, 436800030),
        is_safe_crossband=lambda up,down: True,
        selected_cat_pair_info=lambda up,down: (True,"crossband válido"),
        auto_tune_selected_satellite=lambda: (_ for _ in ()).throw(AssertionError("unexpected reinitialization")),
        log=lambda message: None,
    )
    def background(key, task):
        sent.append((key, task()))
    window.background = background
    return window, cat, sent


def test_online_loop_writes_corrected_fa_fb_without_reinitialize(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    window,cat,sent=live_window()
    MainWindow.track_cat_frequencies(window,None)
    assert cat.tunes == [(145850012, 436800030)]
    assert len(sent) == 1 and sent[0][0] == "cat-track"
    assert sent[0][1][2:] == (145850012, 436800030)
    # At the same instant no second radio write is allowed.
    MainWindow.track_cat_frequencies(window,None)
    assert len(cat.tunes) == 1


def test_continuous_loop_keeps_correcting_on_later_seconds(monkeypatch):
    import sat_tool.app as gui
    clock = [100.0]
    monkeypatch.setattr(gui.time,"monotonic",lambda:clock[0])
    window,cat,sent=live_window()
    MainWindow.track_cat_frequencies(window,None)
    window.last_freqs = (145850012, 436800030)
    window.corrected = lambda: (145850015, 436800045)
    clock[0] = 101.0
    MainWindow.track_cat_frequencies(window,None)
    assert cat.tunes == [(145850012, 436800030), (145850015, 436800045)]
    assert len(sent) == 2


def test_no_cat_writes_when_disabled_or_moving_radio_dial(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    window,cat,sent=live_window()
    window.cat_tracking_armed = False
    MainWindow.track_cat_frequencies(window,None)
    assert cat.tunes == []
    window.cat_tracking_armed = True
    cat.state.uplink = 145860000  # operator manually changed the dial
    MainWindow.track_cat_frequencies(window,None)
    assert window.cat_tracking_armed is False
    assert cat.tunes == []
    assert "PAUSADO" in window.cat_tune_status.message


def test_inflight_cat_worker_does_not_trigger_false_manual_adjustment(monkeypatch):
    import sat_tool.app as gui
    monkeypatch.setattr(gui.time,"monotonic",lambda:100.0)
    window,cat,sent=live_window()
    window.pending_jobs.add("cat-track")
    cat.state.uplink = 145861000
    MainWindow.track_cat_frequencies(window,None)
    assert window.cat_tracking_armed is True and cat.tunes == []


def test_old_defaults_migrate_to_one_second_one_hz_and_custom_values_survive(tmp_path):
    config = Config(tmp_path)
    assert config.values["update_interval_s"] == 1
    assert config.values["tune_threshold_hz"] == 1
    assert config.values["cat_auto_select"] is True
    settings = tmp_path / "settings.json"
    older = dict(config.values)
    older.pop("cat_live_v137_migrated")
    older.update({"update_interval_s": 2, "tune_threshold_hz": 20, "cat_auto_select": False})
    settings.write_text(json.dumps(older),encoding="utf-8")
    migrated = Config(tmp_path)
    assert migrated.values["update_interval_s"] == 1
    assert migrated.values["tune_threshold_hz"] == 1
    assert migrated.values["cat_auto_select"] is False
    assert Config(tmp_path).values["cat_live_v137_migrated"] is True
    custom = dict(older)
    custom.update({"update_interval_s": 5, "tune_threshold_hz": 100})
    settings.write_text(json.dumps(custom),encoding="utf-8")
    keep = Config(tmp_path)
    assert keep.values["update_interval_s"] == 5
    assert keep.values["tune_threshold_hz"] == 100


def test_single_operator_control_and_autotune_on_cat_connect():
    app = (ROOT / "sat_tool" / "app.py").read_text(encoding="utf-8")
    assert "Sintonizar agora" not in app
    assert "cat_tune_now" not in app
    assert 'self.cat_tracking_armed=bool(self.config.values.get("cat_auto_select",False))' in app
    assert 'self.track_cat_frequencies(now)' in app
    assert 'self.background("cat-track",task)' in app
    assert 'self.threshold.setRange(1,1000)' in app
