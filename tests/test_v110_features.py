"""v1.1.0 regression: radio frequency parsing, i18n and CAT read-only telemetry."""
import pytest
from pathlib import Path
from sat_tool.frequency import format_frequency,parse_mhz_input,frequency_label
from sat_tool.i18n import LANGUAGES,TRANSLATIONS,translated
from sat_tool.cat import parse_smeter,parse_power_setting,parse_meter

ROOT=Path(__file__).resolve().parents[1]

def test_radio10_requested_format_and_full_hz_display():
    hz=426252120
    assert format_frequency(hz)=="426.252.12"
    assert format_frequency(hz,"radio1")=="426.252.120"
    assert format_frequency(hz,"decimal")=="426,252120"
    assert frequency_label(hz)=="426.252.12 MHz"
    assert format_frequency(145825001,"radio1")=="145.825.001"

@pytest.mark.parametrize("value,hz",[
    ("426.252.12",426252120),("426.252.120",426252120),
    ("426,252120",426252120),("426.252120",426252120),
    ("145.825000",145825000),("145.825.00 MHz",145825000),
    ("1296.000.00",1296000000),
])
def test_display_entry_roundtrip(value,hz):
    assert parse_mhz_input(value)==hz

@pytest.mark.parametrize("bad",["426.252.1","abc","426.252.1234",
                                "145.82.5", "nan", "1,000.000",
                                "1500.000000","", "0.010000"])
def test_reject_ambiguous_frequency_inputs(bad):
    with pytest.raises(ValueError):parse_mhz_input(bad)

def test_cat_telemetry_strict_parsers():
    assert parse_smeter("SM00018;",0)==18
    assert parse_smeter("SM10008;",1)==8
    assert parse_power_setting("PC025;")==25
    assert parse_meter("RM30014;")==("ALC",14)
    with pytest.raises(ValueError):parse_smeter("SM00099;",0)
    with pytest.raises(ValueError):parse_smeter("SM10020;",1)
    with pytest.raises(ValueError):parse_power_setting("PC999;")
    with pytest.raises(ValueError):parse_meter("RM60031;")

def test_six_languages_have_core_satellite_controls():
    assert set(LANGUAGES)=={"pt-BR","en","es","fr","de","it"}
    for code in ("en","es","fr","de","it"):
        assert translated("Satélites",code)!="Satélites" or code=="es"
        assert translated("Marcar todos",code)!="Marcar todos"
        assert len(TRANSLATIONS[code])>=60
    assert translated("NORAD ID", "de")=="NORAD ID"

def test_source_keeps_cat_write_permission_and_nominal_frequencies():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "def preview_doppler(self)" in app
    assert "self.preview_doppler()" in app
    assert "self.suspend_cat_doppler(" in app
    assert "self.saved_station()" in app
    assert "def bulk_catalog_selection(self,select)" in app
    assert "def refresh_catalog_transmitters(self)" in app
    assert "self.freq_update_cancel" in app
    assert "self.language_combo" in app
    assert "self.freq_style_combo" in app
    assert "self.cat_telemetry" in app
    cat=(ROOT/"sat_tool"/"cat.py").read_text(encoding="utf-8")
    assert '_exchange("SM0;",' not in cat or '"SM0;"' in cat
    assert "self._exchange(frequency_command" in cat
    assert '_exchange("TX;"' not in cat and '_exchange("RX;"' not in cat

def test_transponder_frequency_cache_is_written_only_after_full_valid_response(tmp_path,monkeypatch):
    from sat_tool import catalog
    calls=[]
    class Response:
        def __init__(self,payload):self.payload=payload
        def raise_for_status(self):pass
        def json(self):return self.payload
    def get(url,params=None,headers=None,timeout=None):
        calls.append(url)
        if len(calls)==1:return Response({"results":[{"uuid":"a","downlink_low":145825000}],"next":"?page=2"})
        return Response({"results":[{"uuid":"a","downlink_low":145825000},
                                    {"uuid":"b","downlink_low":435000000}],"next":None})
    monkeypatch.setattr(catalog.requests,"get",get)
    data=catalog.refresh_transmitters(tmp_path,25544)
    assert len(data)==2 and len(calls)==2
    assert len(catalog.load_transmitters(tmp_path,25544))==2

def test_satnogs_failed_second_page_preserves_prior_cache(tmp_path,monkeypatch):
    from sat_tool import catalog
    file=tmp_path/"tx_25544.json"
    file.write_text('[{"uuid":"old"}]',encoding="utf-8")
    class Response:
        def raise_for_status(self):pass
        def json(self):return {"results":[{"uuid":"new"}],"next":"https://evil.example/page2"}
    monkeypatch.setattr(catalog.requests,"get",lambda *a,**k:Response())
    with pytest.raises(ValueError):
        catalog.refresh_transmitters(tmp_path,25544)
    assert catalog.load_transmitters(tmp_path,25544)==[{"uuid":"old"}]
