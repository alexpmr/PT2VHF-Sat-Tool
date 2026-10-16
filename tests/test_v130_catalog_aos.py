"""v1.3.0: broad NORAD catalog, stable aliases, AOS and bounded UI."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sat_tool.alerts import eta_seconds, format_duration, selected_aos_alarm
from sat_tool.catalog import merge_orbits, normalized_satellite_search, satellite_search_text


def test_satellite_alias_normalized_so50():
    record={"OBJECT_NAME":"SAUDISAT 1C","NORAD_CAT_ID":27607}
    needle=satellite_search_text("27607",record)
    for value in ("SO-50","so50","27607","SaudiSat 1C"):
        assert normalized_satellite_search(value) in needle


def test_many_groups_deduplicate_by_norad_and_keep_categories():
    groups={"amateur":[{"NORAD_CAT_ID":27607,"OBJECT_NAME":"SAUDISAT 1C",
                          "EPOCH":"2026-10-15T00:00:00.000000"}],
            "cubesat":[{"NORAD_CAT_ID":27607,"OBJECT_NAME":"SO-50",
                        "EPOCH":"2026-10-14T00:00:00.000000"}],
            "starlink":[{"NORAD_CAT_ID":60000,"OBJECT_NAME":"STARLINK-X"}]}
    rows=merge_orbits(groups)
    assert len(rows)==2
    sat=next(row for row in rows if str(row["NORAD_CAT_ID"])=="27607")
    assert sat["OBJECT_NAME"]=="SAUDISAT 1C"
    assert sat["CATEGORIES"]==["amateur","cubesat"]


def test_eta_requires_samples_and_never_goes_negative():
    assert eta_seconds(0,100,20) is None
    assert eta_seconds(1,100,20) is None
    assert eta_seconds(20,100,40)==160
    assert eta_seconds(100,100,40)==0
    assert format_duration(160)=="02:40"
    assert format_duration(3700)=="01:01:40"


def test_selected_aos_alert_never_fires_for_other_satellites():
    now=datetime(2026,10,15,20,tzinfo=timezone.utc)
    rows=[{"id":"27607","aos":now+timedelta(seconds=23),"name":"SO-50"},
          {"id":"25544","aos":now+timedelta(seconds=29),"name":"ISS"}]
    found=selected_aos_alarm(rows,"27607",now,set())
    assert found is not None
    key,row,remaining=found
    assert row["id"]=="27607"
    assert remaining==23
    assert selected_aos_alarm(rows,"27607",now,{key}) is None
    assert selected_aos_alarm(rows,"27607",now-timedelta(minutes=2),set()) is None
    assert selected_aos_alarm(rows,"27607",now+timedelta(minutes=1),set()) is None


def test_ui_source_limits_large_catalog_and_keeps_cat_opt_in():
    source=(Path(__file__).resolve().parents[1]/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "ids[:350]" in source
    assert "rows=rows[:350]" in source
    assert 'if self._loading_catalog or ident not in self.omm:return' in source
    assert 'self.catalog_table.cellClicked.connect(self.queue_catalog_single_click)' in source
    assert 'self.catalog_table.setItem(row,column,cell)' in source
    assert 'cell.setBackground(QBrush(QColor("#ffe36a")))' in source
    assert 'self.auto_cat=QCheckBox(' in source
    assert 'self.cat_selection_generation+=1' in source
    assert 'self.check_selected_aos_alarm(now)' in source
    assert 'self.cat_indicator.setText(' in source
    assert 'self.orbit_progress_dialog' in source
