from datetime import datetime, timezone
from math import isclose
import pytest
from sat_tool.core import doppler_frequencies, paired_linear_uplink, Station, transponder_options
from sat_tool.cat import frequency_command, parse_frequency, satellite_mode_command


def test_receding_doppler_downlink_lower_uplink_higher():
    up,down=doppler_frequencies(145_900_000, 435_800_000, 7000)
    assert up>145_900_000
    assert down<435_800_000


def test_approaching_doppler_downlink_higher_uplink_lower():
    up,down=doppler_frequencies(145_900_000,435_800_000,-7000)
    assert up<145_900_000
    assert down>435_800_000


def test_doppler_zero():
    assert doppler_frequencies(145_900_000,435_800_000,0)==(145_900_000,435_800_000)


def test_transponder_inverted():
    assert paired_linear_uplink(435_100_000,435_100_000,435_200_000,145_900_000,146_000_000,True)==146_000_000
    assert paired_linear_uplink(435_200_000,435_100_000,435_200_000,145_900_000,146_000_000,True)==145_900_000


def test_cat_frequency_encoding():
    assert frequency_command('FA',435_800_000)=='FA00435800000;'
    assert frequency_command('FB',145_900_000)=='FB00145900000;'
    assert parse_frequency('FA00435800000;', 'FA')==435_800_000


def test_cat_rejects_wrong_channel():
    assert frequency_command('FC',145_900_000)=='FC00145900000;'
    with pytest.raises(ValueError):frequency_command('FX',145_900_000)


def test_cat_sat_mode_keeps_memory_channel():
    assert satellite_mode_command('SA1020111ABCDEFGH;')=='SA1010000;'


def test_station_limits():
    Station('PT2VHF',-15.8,-47.8).validate()
    with pytest.raises(ValueError):Station('X',-100,40).validate()


def test_transponders_filter_and_rx_only():
    rows=[{'description':'FM repeater','downlink_low':435800000,'uplink_low':145900000,'status':'active'},
          {'description':'Beacon','downlink_low':145825000,'uplink_low':None,'status':'active'},
          {'description':'Dead','downlink_low':100000000,'status':'inactive'}]
    opts=transponder_options(rows)
    assert len(opts)==2
    assert opts[1]['receive_only']


def test_tle_parser():
    from sat_tool.catalog import parse_tle
    # Syntactic fixture only; no orbital propagation assumptions.
    text="""0 EXAMPLE
1 25544U 98067A   24001.00000000  .00020000  00000-0  30000-3 0  9991
2 25544  51.6410  70.0000 0004000  20.0000 330.0000 15.50000000000001
"""
    data=parse_tle(text)
    assert len(data)==1
    assert data[0]['NORAD_CAT_ID']==25544
    assert data[0]['OBJECT_NAME']=='EXAMPLE'


def test_cat_writes_only_safe_commands_in_simulation():
    from sat_tool.cat import TS2000, RadioState
    class SerialSimulator:
        is_open=True
        def __init__(self):
            self.writes=[]
            self.fa=435800000
            self.fb=145900000  # legacy VFO B, not satellite SUB
            self.fc=145850000  # actual satellite SUB
            self.sat='SA1010000        ;'
            self.answer=b''
        def reset_input_buffer(self):pass
        def flush(self):pass
        def close(self):self.is_open=False
        def write(self, raw):
            cmd=raw.decode('ascii');self.writes.append(cmd)
            if cmd=='SA;':self.answer=self.sat.encode()
            elif cmd.startswith('SA1'):
                self.sat=cmd[:-1]+'        ;';self.answer=b''
            elif cmd=='FA;':self.answer=f'FA{self.fa:011d};'.encode()
            elif cmd=='FB;':self.answer=f'FB{self.fb:011d};'.encode()
            elif cmd=='FC;':self.answer=f'FC{self.fc:011d};'.encode()
            elif cmd.startswith('FA'):
                self.fa=int(cmd[2:-1]);self.answer=b''
            elif cmd.startswith('FB'):
                self.fb=int(cmd[2:-1]);self.answer=b''
            elif cmd.startswith('FC'):
                self.fc=int(cmd[2:-1]);self.answer=b''
            elif cmd=='MD;':self.answer=b'MD4;'
            elif cmd=='ID;':self.answer=b'ID019;'
            elif cmd=='SM0;':self.answer=b'SM00018;'
            elif cmd=='SM1;':self.answer=b'SM10008;'
            elif cmd=='PC;':self.answer=b'PC025;'
            elif cmd=='RM;':self.answer=b'RM30014;'
            else:raise AssertionError('Unexpected CAT '+cmd)
        def read_until(self, delimiter):return self.answer
    sim=SerialSimulator()
    rig=TS2000()
    rig.port=sim
    rig.state=RadioState(True,'Kenwood TS-2000')
    st=rig.set_frequencies(145902000,435799000)
    assert st.uplink==145902000 and st.downlink==435799000
    assert st.signal_main==18 and st.signal_sub==8
    assert st.power_set_w==25 and st.meter_type=='ALC' and st.meter_value==14
    assert 'FA00435799000;' in sim.writes
    assert 'FB00145902000;' in sim.writes
    assert not any(cmd.startswith('FC0') for cmd in sim.writes)
    assert sim.fb==145902000  # SAT uplink follows FB
    assert sim.fc==145850000  # separate SUB VFO stays untouched
    assert not any(c.startswith(('TX','RX','MO')) for c in sim.writes)
