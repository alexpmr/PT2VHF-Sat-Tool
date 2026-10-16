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
    assert transmitter_batch_ids(3,None,enabled,[],orbits)==["25544","27607","44881"]
    with pytest.raises(ValueError):
        transmitter_batch_ids(4,None,enabled,[],orbits)


def test_predicted_doppler_independent_of_visibility_and_cat_protected():
    ch={"downlink_hz":437800000,"uplink_hz":145990000}
    receding=frequency_prediction(ch,6000)
    approaching=frequency_prediction(ch,-6000)
    assert receding["rx_offset_hz"]<0 and receding["tx_offset_hz"]>0
    assert approaching["rx_offset_hz"]>0 and approaching["tx_offset_hz"]<0
    assert approaching["rx_hz"]!=receding["rx_hz"]
    # Legacy helper supports a visibility gate, but active Auto CAT must not use it.
    assert not cat_doppler_allowed(False)
    assert cat_doppler_allowed(True)
    assert cat_doppler_allowed(False,True)


def test_cat_out_of_view_setting_defaults_on_and_persists(tmp_path):
    config=Config(tmp_path)
    assert config.values["cat_doppler_out_of_view"] is True
    config.values["cat_doppler_out_of_view"]=True
    config.save()
    assert Config(tmp_path).values["cat_doppler_out_of_view"] is True


def test_gui_wires_batch_checkboxes_and_every_second_preview():
    source=(Path(__file__).resolve().parents[1]/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "ids=transmitter_batch_ids(3,None,[],[],self.omm)" in source
    assert "self.catalog_table.cellClicked.connect(self.queue_catalog_single_click)" in source
    assert "def toggle_catalog_satellite_selection(self,row,col):" in source
    assert "self.preview_doppler(pos=pos,when=now)" in source
    assert "self.cat_live_timer.timeout.connect(self.cat_live_tick)" in source
    active=source.split("    def track_cat_frequencies(self,now):",1)[1].split("    def cat_live_tick(self):",1)[0]
    assert "cat_doppler_allowed(" not in active
    assert "self.cat_outside" not in source
    assert "self.tick_timer.start(1000)" in source
    assert "FORA DA VISADA" in source
