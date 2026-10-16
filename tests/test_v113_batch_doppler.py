"""v1.1.3: regression checks for catalog batch updates and out-of-view Doppler."""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sat_tool.selection import change_selection, transmitter_batch_ids, cat_doppler_allowed
from sat_tool.operations import frequency_prediction
from sat_tool.config import Config


def test_bulk_selection_all_without_cached_transponders(tmp_path):
    orbits={"25544":{},"27607":{},"44881":{}}
    selected,affected=change_selection(orbits,["25544"],[],True,False)
    assert selected==["25544","27607","44881"]
    assert len(affected)==3
    remaining,_=change_selection(orbits,["25544"],selected,False,True)
    assert remaining==["27607","44881"]
    empty,_=change_selection(orbits,[],remaining,False,False)
    assert empty==[]


def test_batch_default_habilitados_and_single_or_filtered():
    orbits={"25544":{},"27607":{},"44881":{}}
    enabled=["44881","27607","44881"]
    assert transmitter_batch_ids(1,None,enabled,["25544"],orbits)==["44881","27607"]
    assert transmitter_batch_ids(0,"25544",enabled,[],orbits)==["25544"]
    assert transmitter_batch_ids(2,None,enabled,["25544","99999"],orbits)==["25544"]
    assert transmitter_batch_ids(0,None,enabled,[],orbits)==[]
    with pytest.raises(ValueError):
        transmitter_batch_ids(3,None,enabled,[],orbits)


def test_predicted_doppler_independent_of_visibility_and_cat_protected():
    ch={"downlink_hz":437800000,"uplink_hz":145990000}
    receding=frequency_prediction(ch,6000)
    approaching=frequency_prediction(ch,-6000)
    assert receding["rx_offset_hz"]<0 and receding["tx_offset_hz"]>0
    assert approaching["rx_offset_hz"]>0 and approaching["tx_offset_hz"]<0
    assert approaching["rx_hz"]!=receding["rx_hz"]
    # Frequency math has no line-of-sight gate; CAT does.
    assert not cat_doppler_allowed(False)
    assert cat_doppler_allowed(True)
    assert cat_doppler_allowed(False,True)


def test_cat_out_of_view_setting_defaults_off_and_persists(tmp_path):
    config=Config(tmp_path)
    assert config.values["cat_doppler_out_of_view"] is True
    config.values["cat_doppler_out_of_view"]=True
    config.save()
    assert Config(tmp_path).values["cat_doppler_out_of_view"] is True


def test_gui_wires_batch_checkboxes_and_every_second_preview():
    source=(Path(__file__).resolve().parents[1]/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "self.catalog_refresh_scope.setCurrentIndex(1)" in source
    assert "self.catalog_table.itemChanged.connect(self.catalog_satellite_checked)" in source
    assert "def catalog_satellite_checked(self,item):" in source
    assert "self.preview_doppler(pos=pos,when=now)" in source
    assert "self.track_cat_frequencies(now)" in source
    assert "cat_doppler_allowed(self.last_pos[\"visible\"]" in source
    assert "self.tick_timer.start(1000)" in source
    assert "FORA DA VISADA" in source
