"""v1.8.1: fontes AMSAT (nasabare.txt) e R4UAB (satonline.txt) como categorias orbitais."""
import json

from sat_tool import catalog
from sat_tool.config import Config

TLE = """LUCA-1
1 99901U 26999A   26317.50000000  .00010000  00000-0  12345-3 0  9991
2 99901  97.5000 120.0000 0010000  90.0000 270.0000 15.20000000   102
SO-50
1 27607U 02058C   26317.90000000  .00000500  00000-0  65432-4 0  9993
2 27607  64.5500 200.0000 0060000  10.0000 350.0000 14.80000000 10001
"""


class Response:
    def __init__(self, text=None, data=None):
        self.text, self.data = text, data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_tle_sources_become_categories_and_merge_with_celestrak(tmp_path, monkeypatch):
    calls = []
    celestrak = [{"NORAD_CAT_ID": 27607, "OBJECT_NAME": "SAUDISAT 1C", "EPOCH": "2026-11-12T00:00:00.000000",
                  "MEAN_MOTION": 14.8, "ECCENTRICITY": 0.006, "INCLINATION": 64.55, "RA_OF_ASC_NODE": 200,
                  "ARG_OF_PERICENTER": 10, "MEAN_ANOMALY": 350, "BSTAR": 0, "MEAN_MOTION_DOT": 0,
                  "MEAN_MOTION_DDOT": 0, "EPHEMERIS_TYPE": 0, "CLASSIFICATION_TYPE": "U",
                  "ELEMENT_SET_NO": 999, "REV_AT_EPOCH": 1, "OBJECT_ID": "2002-058C"}]

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        if url in catalog.TLE_SOURCES.values():
            return Response(text=TLE)
        return Response(data=celestrak)
    monkeypatch.setattr(catalog.requests, "get", fake_get)
    monkeypatch.setattr(catalog, "DEFAULT_SATELLITES", ())
    merged = {str(o["NORAD_CAT_ID"]): o for o in catalog.refresh_multi_omm(tmp_path, ("amateur", "amsat", "r4uab"))}
    assert set(catalog.TLE_SOURCES.values()) <= set(calls)
    # satélite que só existe nas fontes novas aparece, com campos OMM e linhas TLE para a propagação
    luca = merged["99901"]
    assert luca["OBJECT_NAME"] == "LUCA-1" and luca["CATEGORIES"] == ["amsat", "r4uab"]
    assert luca["EPOCH"] == "2026-11-13T12:00:00.000000" and luca["MEAN_MOTION"] == 15.2
    assert abs(luca["BSTAR"] - 1.2345e-4) < 1e-12 and luca["TLE_LINE1"].startswith("1 99901U")
    # TLE mais novo vence nos elementos, mas o nome da CelesTrak fica e o outro vira apelido de busca
    so50 = merged["27607"]
    assert so50["OBJECT_NAME"] == "SAUDISAT 1C" and "SO-50" in so50["ALT_NAMES"]
    assert so50["CATEGORIES"] == ["amateur", "amsat", "r4uab"] and "TLE_LINE1" in so50
    assert "so50" in catalog.satellite_search_text("27607", so50)
    from skyfield.api import load
    from sat_tool.core import make_satellite
    assert make_satellite(luca, load.timescale()).model.satnum == 99901


def test_tle_fields_with_implicit_exponent():
    assert catalog._tle_float(" 12345-3") == 1.2345e-4
    assert catalog._tle_float("-11606-4") == -1.1606e-5
    assert catalog._tle_float(" 00000+0") == 0.0


def test_new_sources_are_on_by_default_and_added_once_to_old_configs(tmp_path):
    assert {"amsat", "r4uab"} <= set(catalog.DEFAULT_GROUPS)
    (tmp_path / "settings.json").write_text(json.dumps({"orbit_groups": ["amateur"],
                                                      "catalog_category_filter": ["amateur", "stations"]}))
    cfg = Config(tmp_path)
    assert cfg.values["orbit_groups"] == ["amateur", "amsat", "r4uab"]
    assert cfg.values["catalog_category_filter"] == ["amateur", "stations", "amsat", "r4uab"]
    cfg.values["orbit_groups"] = ["amateur"]
    cfg.save()
    assert Config(tmp_path).values["orbit_groups"] == ["amateur"]   # desmarcar depois é respeitado
