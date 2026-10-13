"""Deterministic regression tests: pass compatibility, Doppler, time windows."""
from datetime import datetime,timedelta,timezone
import pytest

from sat_tool.operations import (select_channel,select_next_pass,status_at,clock_text,
                                 frequency_prediction,orbital_age_days)
from sat_tool.core import track_period_bounds

UTC=timezone.utc
T=datetime(2026,10,13,12,0,tzinfo=UTC)
FM={"mode":"FM","downlink_low":145_825_000,"uplink_low":437_800_000,
    "alive":True,"status":"active","description":"FM voice transponder"}
SSB={"mode":"USB","type":"Transceiver","downlink_low":145_960_000,"downlink_high":145_980_000,
     "uplink_low":435_660_000,"uplink_high":435_680_000,"invert":True,"alive":True}
BEACON={"mode":"CW","description":"CW beacon","downlink_low":145_870_000,"uplink_low":None}


def test_fm_ssb_cw_selection_respects_operating_mode():
    assert select_channel([FM,SSB,BEACON],["FM"],["VHF","UHF"])["mode"]=="FM"
    ssb=select_channel([SSB],["SSB"],["VHF","UHF"])
    assert ssb["linear"] and ssb["inverted"] and ssb["uplink_hz"]==435_670_000
    assert select_channel([FM],["CW"],["VHF","UHF"]) is None
    beacon=select_channel([BEACON],["CW"],["VHF","UHF"])
    assert beacon["rx_only"] and beacon["uplink_hz"] is None
    assert select_channel([FM],["FM"],["VHF"]) is None


def test_pass_countdown_precedence_over_future():
    a={"id":"1","name":"current","aos":T-timedelta(minutes=4),
       "tca":T,"los":T+timedelta(minutes=6),"max_el":60}
    b={"id":"2","name":"upcoming","aos":T+timedelta(minutes=15),
       "tca":T+timedelta(minutes=20),"los":T+timedelta(minutes=25),"max_el":90}
    rows={"1":[FM],"2":[FM]}
    active=select_next_pass([b,a],rows,["FM"],["VHF","UHF"],T,["1","2"])
    assert active["id"]=="1" and active["in_progress"]
    assert status_at(active,T)==("EM PASSAGEM","00:06:00")
    assert select_next_pass([a,b],rows,["FM"],["VHF","UHF"],T+timedelta(minutes=7),["1","2"])["id"]=="2"
    assert select_next_pass([a,b],rows,["CW"],["VHF","UHF"],T) is None
    assert select_next_pass([a,b],rows,["FM"],["VHF","UHF"],T,[]) is None


def test_frequencies_are_predictions_and_rx_only_no_fake_tx():
    corrected=frequency_prediction(select_channel([FM],["FM"],["VHF","UHF"]),5000)
    assert corrected["rx_hz"]<145_825_000
    assert corrected["tx_hz"]>437_800_000
    assert corrected["rx_offset_hz"]<0 and corrected["tx_offset_hz"]>0
    cw=frequency_prediction(select_channel([BEACON],["CW"],["VHF"]),-5000)
    assert cw["tx_hz"] is None and cw["tx_offset_hz"] is None
    assert cw["rx_hz"]>145_870_000


def test_formats_boundaries_and_old_orbit_warning():
    assert clock_text(-5)=="00:00:00"
    assert clock_text(3661)=="01:01:01"
    assert clock_text(90001)=="1d 01:00:01"
    assert orbital_age_days(T-timedelta(days=8),T)==8


def test_track_windows_modes_midnight_and_last_pass():
    old,new=track_period_bounds(T,5,"Ambos")
    assert (T-old[0])==timedelta(hours=2.5)
    assert (new[1]-T)==timedelta(hours=2.5)
    assert track_period_bounds(T,10,"Futuro")[0] is None
    assert track_period_bounds(T,2,"Passado")[1] is None
    historic={"aos":T-timedelta(minutes=20),"los":T-timedelta(minutes=7)}
    old,new=track_period_bounds(T,2,"Última passagem",historic)
    assert old==(historic["aos"],historic["los"]) and new is None
    fallback,_=track_period_bounds(T,2,"Última passagem")
    assert fallback[0]==T-timedelta(hours=2)
    with pytest.raises(ValueError):
        track_period_bounds(T,300,"Futuro")
