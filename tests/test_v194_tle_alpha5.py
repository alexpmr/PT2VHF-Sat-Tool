"""v1.9.4: TLE com catálogo Alpha-5 (acima de 99999) não derruba mais a fonte R4UAB; LUČA-1 aparece."""
from sat_tool.catalog import parse_tle, tle_catalog_number, tle_to_omm

# trecho real do satonline.txt da R4UAB (20/11/2026)
FEED = """LUCA-1 (RS90S)
1 67287U 25313AR  26324.47409572  .00008934  00000-0  33990-3 0  9990
2 67287  97.3802  37.5434 0009551 155.6271 204.5421 15.26948262 49808
RASSVET-3 18
1 A0084U 26045A   26324.50000000  .00001000  00000-0  50000-4 0  9991
2 A0084  97.6000 100.0000 0001000  90.0000 270.0000 15.10000000  1234
LIXO
1 #0001U 26045B   26324.50000000  .00001000  00000-0  50000-4 0  9991
2 #0001  97.6000 100.0000 0001000  90.0000 270.0000 15.10000000  1234
"""


def test_alpha5_catalog_numbers():
    assert tle_catalog_number("25544") == 25544
    assert tle_catalog_number("A0084") == 100084
    assert tle_catalog_number("J0001") == 180001     # I é pulado no Alpha-5
    assert tle_catalog_number("Z9999") == 339999
    assert tle_catalog_number("I0001") is None and tle_catalog_number("#0001") is None


def test_r4uab_feed_with_alpha5_keeps_luca1_and_propagates():
    rows = parse_tle(FEED)
    assert [r["NORAD_CAT_ID"] for r in rows] == [67287, 100084]   # linha inválida pulada, sem exceção
    luca = tle_to_omm(rows[0])
    assert luca["OBJECT_NAME"] == "LUCA-1 (RS90S)" and luca["OBJECT_ID"] == "2025-313AR"
    from sat_tool.core import make_satellite
    for row in rows:
        sat = make_satellite(tle_to_omm(row))
        assert sat.model.satnum == row["NORAD_CAT_ID"]
        assert 300 < sat.at(sat.epoch).subpoint().elevation.km < 700   # órbita baixa plausível
