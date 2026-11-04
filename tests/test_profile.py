"""Deterministic station-mode and frequency-band recommendation rules."""
from sat_tool.profile import capability, choose_satellites, normalize_modes, row_modes


def test_normalized_modes_and_transponders():
    assert normalize_modes(["FM","CW","AM"])==["CW","FM"]
    assert row_modes({"mode":"USB"})=={"SSB"}
    assert row_modes({"mode":"CW","description":"Beacon"})=={"CW"}


def test_matching_respects_bands_and_rx_only():
    rx=[{"mode":"FM","status":"active","alive":True,"downlink_low":145825000}]
    out=capability("99999",rx,["FM"],["VHF","UHF"])
    assert out["suggested"] and out["rx_only"] and out["channels"][0]["downlink"]==145825000
    assert not capability("99999",rx,["SSB"],["VHF","UHF"])["suggested"]
    assert not capability("99999",rx,["FM"],["UHF"])["suggested"]


def test_unknown_satellite_not_marked_operational():
    out=capability("99999",[],["FM"],["VHF","UHF"])
    assert not out["suggested"]
    assert out["confirmed"] is False


def test_default_hints_are_not_operational_confirmations():
    out=capability("44909",[],["SSB"],["VHF","UHF"])
    assert out["suggested"] and not out["confirmed"]
    assert out["source"].startswith("histórico")


def test_user_selection_overrides_auto_and_is_stable():
    sat={"44909":{"OBJECT_NAME":"RS-44"},"99999":{"OBJECT_NAME":"Test"}}
    assert choose_satellites(sat,{},["SSB"],["VHF","UHF"])==["44909"]
    assert choose_satellites(sat,{},["FM"],["VHF","UHF"],["99999"])==["99999"]
    assert choose_satellites(sat,{},["FM"],["VHF","UHF"],[])==[]


def test_v1316_default_satellites(tmp_path):
    from sat_tool.config import Config, DEFAULT_SATELLITES
    assert DEFAULT_SATELLITES == ("25544", "27607", "40931", "7530", "24278", "44909", "59112")
    assert Config(tmp_path).values["satellite_selection"] == list(DEFAULT_SATELLITES)


def test_v1316_existing_selection_gains_defaults_once(tmp_path):
    import json
    from sat_tool.config import Config, DEFAULT_SATELLITES
    (tmp_path / "settings.json").write_text(json.dumps({"satellite_selection": ["43017", "25544"]}))
    cfg = Config(tmp_path)
    assert cfg.values["satellite_selection"][:2] == ["43017", "25544"]
    assert set(DEFAULT_SATELLITES) <= set(cfg.values["satellite_selection"])
    cfg.values["satellite_selection"] = ["43017"]  # operador desmarca depois
    cfg.save()
    assert Config(tmp_path).values["satellite_selection"] == ["43017"]


def test_v1316_auto_selection_is_preserved(tmp_path):
    import json
    from sat_tool.config import Config
    (tmp_path / "settings.json").write_text(json.dumps({"satellite_selection": None}))
    assert Config(tmp_path).values["satellite_selection"] is None
