"""Regression tests for station picking: WGS-84, preview and no unsaved CAT changes."""
import math
import pytest
from pathlib import Path
from sat_tool.location_map import valid_coordinates,parse_coordinate_fields,sanitize_map_pick

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("lat,lon",[
 (-15.8460714,-47.8095589),(0,0),(90,180),(-90,-180),(51.5,179.999999),
])
def test_wgs84_pick_boundaries_and_precision(lat,lon):
    a,b=valid_coordinates(lat,lon)
    assert abs(a-lat)<1e-7 and abs(b-lon)<1e-7


@pytest.mark.parametrize("point",[
 {"lat":float("nan"),"lon":-47.5},
 {"lat":float("inf"),"lon":-47.5},
 {"lat":91,"lon":3},{"lat":0,"lon":-181},
 {"lat":True,"lon":2},{"lat":"-15.5","lon":-47.9},
 {"lat":0,"lon":0,"cat":"TX"},
 [0,0],None,
])
def test_reject_untrusted_or_out_of_range_map_values(point):
    with pytest.raises(ValueError):
        sanitize_map_pick(point)


def test_numeric_edit_accepts_brazilian_decimal_comma():
    assert parse_coordinate_fields("-15,8460714","-47,8095589")==(-15.8460714,-47.8095589)
    with pytest.raises(ValueError):
        parse_coordinate_fields("-15.5","malformed")


def test_map_stays_offline_and_has_explicit_editing_mode():
    html=(ROOT/"sat_tool"/"map.html").read_text(encoding="utf-8")
    for name in ("beginLocationPick","finishLocationPick","takeLocationPick",
                 "setLocationPickPreview","focusLocation","coordFromPointer",
                 "selectionOverlay","pointercancel"):
        assert name in html
    assert "Math.min(rect.width/vb.w,rect.height/vb.h)" in html
    assert "if(selectionMode&&!drag.moved&&!markerDrag)" in html
    assert "window.updateOrbit=function" in html
    assert "tile.openstreetmap.org" not in html
    assert "https://unpkg.com" not in html


def test_operation_uses_saved_station_until_user_presses_save():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert app.count("self.station()")==1  # validation in Save station only
    assert app.count("self.saved_station()")>=6
    assert "def confirm_station_map(self):" in app
    assert "self.tabs.setCurrentIndex(2)" in app
    part=app[app.index("    def confirm_station_map("):app.index("    def save_station(")]
    assert "self.config.save()" not in part
    assert "self.radio" not in part and "PTT" not in part
    assert "self.lat.setText(" in part and "self.lon.setText(" in part
    assert "self.map_pick_active=False" in app
