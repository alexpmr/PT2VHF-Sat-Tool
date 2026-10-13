"""Geolocation safety and accuracy regressions, independent of Windows hardware."""
import pytest
from sat_tool.geolocation import (GeoFix,lookup_approximate_ip,parse_nmea_position,
                                  nmea_checksum_valid,read_gps_serial,IP_ENDPOINT)


def _sentence(payload):
    check=0
    for c in payload:check ^= ord(c)
    return "$"+payload+"*%02X"%check


def test_rmc_nmea_validated_hemisphere_and_crc():
    payload="GPRMC,123519,A,1530.000,S,04745.000,W,0.0,0.0,131026,,,A"
    txt=_sentence(payload)
    assert nmea_checksum_valid(txt)
    fix=parse_nmea_position(txt)
    assert fix.latitude==-15.5
    assert fix.longitude==-47.75
    assert fix.altitude_m is None
    assert parse_nmea_position(txt[:-2]+"00") is None
    assert parse_nmea_position(_sentence(payload.replace(",A,1530",",V,1530"))) is None


def test_gga_rejects_unfixed_and_keeps_altitude():
    payload="GNGGA,123519,1530.000,S,04745.000,W,1,09,0.9,1130.4,M,0.0,M,,"
    fix=parse_nmea_position(_sentence(payload))
    assert fix.latitude==-15.5 and fix.longitude==-47.75
    assert fix.altitude_m==1130.4
    assert parse_nmea_position(_sentence(payload.replace(",1,09",",0,09"))) is None


def test_ip_source_is_optional_and_explicit_function():
    calls=[]
    class Response:
        url="https://ipwho.is/"
        def raise_for_status(self):pass
        def json(self):
            return {"success":True,"latitude":-15.75,"longitude":-47.9,
                    "city":"Brasilia","region":"Distrito Federal","country":"Brazil"}
    def get(url,**kw):
        calls.append((url,kw))
        return Response()
    assert not calls
    fix=lookup_approximate_ip(http_get=get)
    assert len(calls)==1 and calls[0][0]==IP_ENDPOINT
    assert calls[0][1]["timeout"]<=10
    assert fix.approximate and fix.altitude_m is None and fix.accuracy_m is None
    assert "Brasilia" in fix.description


def test_ip_rejects_error_and_insecure_redirect():
    class Response:
        url="https://ipwho.is/"
        def raise_for_status(self):pass
        def json(self):return {"success":False,"message":"Unavailable"}
    with pytest.raises(ValueError):lookup_approximate_ip(http_get=lambda *a,**k:Response())
    class Redirect(Response):
        url="http://insecure.example/"
    with pytest.raises(ValueError):lookup_approximate_ip(http_get=lambda *a,**k:Redirect())


def test_geofix_checks_bounds_non_finite_and_optional_altitude():
    assert GeoFix(0,0,"manual").validate().altitude_m is None
    for lat,lon in [(91,0),(-91,0),(0,181),(float("nan"),0)]:
        with pytest.raises(ValueError):GeoFix(lat,lon,"test").validate()
    with pytest.raises(ValueError):GeoFix(0,0,"test",altitude_m=float("nan")).validate()
    with pytest.raises(ValueError):GeoFix(0,0,"test",accuracy_m=-1).validate()


def test_gps_serial_never_writes(monkeypatch):
    import serial
    payload=_sentence("GPRMC,123519,A,1530.000,S,04745.000,W,0.0,0.0,131026,,,A").encode("ascii")
    class Port:
        def __init__(self,**args):
            assert args["port"]=="COM24" and args["baudrate"]==9600
            self.calls=0
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def readline(self):
            self.calls+=1
            return payload if self.calls==1 else b""
        def write(self,*args):raise AssertionError("GPS must be read-only")
    monkeypatch.setattr(serial,"Serial",Port)
    result=read_gps_serial("COM24",baud=9600,timeout_s=3)
    assert result.source=="GPS NMEA serial" and result.latitude==-15.5


def test_app_requires_user_consent_and_never_auto_saves_geo_result():
    from pathlib import Path
    code=(Path(__file__).resolve().parents[1]/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert 'QMessageBox.question(self,"Localização aproximada por IP"' in code
    assert 'self.background("geo-ip",lookup_approximate_ip)' in code
    assert 'self.background("geo-gps"' in code
    start=code.index("    def apply_location_fix(")
    end=code.index("    def update_ports(",start)
    assert "self.config.save()" not in code[start:end]
    assert "self.lat.setText(" in code[start:end]
    assert "self.lon.setText(" in code[start:end]
