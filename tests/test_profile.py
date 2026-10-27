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
    out=capability("44881",[],["SSB"],["VHF","UHF"])
    assert out["suggested"] and not out["confirmed"]
    assert out["source"].startswith("histórico")


def test_user_selection_overrides_auto_and_is_stable():
    sat={"44881":{"OBJECT_NAME":"RS-44"},"99999":{"OBJECT_NAME":"Test"}}
    assert choose_satellites(sat,{},["SSB"],["VHF","UHF"])==["44881"]
    assert choose_satellites(sat,{},["FM"],["VHF","UHF"],["99999"])==["99999"]
    assert choose_satellites(sat,{},["FM"],["VHF","UHF"],[])==[]


def test_v1315_default_satellites_iss_io86_so50(tmp_path):
    from sat_tool.config import Config
    cfg = Config(tmp_path)
    assert cfg.values["satellite_selection"] == ["25544", "40931", "27607"]
