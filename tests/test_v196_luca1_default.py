"""v1.9.6 (backlog 22/11/2026): LUČA-1 (RS90S, NORAD 67287) vem marcado por padrão."""
import json

from sat_tool.config import Config, DEFAULT_SATELLITES, LUCA1_NORAD


def test_new_install_has_luca1(tmp_path):
    assert LUCA1_NORAD == "67287" and LUCA1_NORAD in DEFAULT_SATELLITES
    assert LUCA1_NORAD in Config(tmp_path).values["satellite_selection"]


def test_existing_selection_gains_luca1_once_without_unchecking_anything(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({
        "satellite_selection": ["25544", "43017"], "default_satellites_v1316_migrated": True}))
    cfg = Config(tmp_path)
    assert cfg.values["satellite_selection"] == ["25544", "43017", "67287"]
    cfg.values["satellite_selection"] = ["25544"]          # operador desmarca depois
    cfg.save()
    assert Config(tmp_path).values["satellite_selection"] == ["25544"]


def test_automatic_selection_is_left_alone(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"satellite_selection": None}))
    assert Config(tmp_path).values["satellite_selection"] is None
