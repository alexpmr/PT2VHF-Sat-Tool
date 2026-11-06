"""v1.6.0: display LCD, MAIN↔SUB (SA P3) e Somente RX no TS-2000 simulado — nunca PTT nem uplink."""
from sat_tool import lcd
from test_v131_cat_connect import rig_with_sim


def test_format_radio_hz_and_font_coverage():
    assert lcd.format_radio_hz(435_637_710) == ("435.637.7", "1")
    assert lcd.format_radio_hz(145_800_000) == ("145.800.0", "0")
    for ch in "0123456789.:-+/%°ABCDEFGHIJKLMNOPQRSTUVWXYZ <>=":
        assert ch in lcd.FONT and len(lcd.FONT[ch]) == 7


def test_swap_orientation_writes_fa_fb_inverted_and_reads_back():
    radio, sim = rig_with_sim()
    radio.set_orientation(main_downlink=False)
    assert sim.writes[-2].startswith("SA") and sim.writes[-2][4] == "0"
    sim.writes.clear()
    state = radio.set_frequencies(145_960_000, 435_640_000)
    assert "FB00435640000;" in sim.writes and "FA00145960000;" in sim.writes  # RX na SUB (FB)
    assert state.downlink == 435_640_000 and state.uplink == 145_960_000
    assert not any(w.startswith(("TX", "RX")) for w in sim.writes)
    radio.set_orientation(main_downlink=True)
    assert radio.main_downlink_expected is True


def test_rx_only_writes_only_receive_vfo_even_with_sat_off():
    radio, sim = rig_with_sim()
    sim.sat = False
    sim.writes.clear()
    state = radio.set_rx_only(437_800_710, "FM")
    assert sim.writes[:2] == ["SA;", "FA00437800710;"] and "FB" not in "".join(sim.writes[1:])
    assert state.downlink == 437_800_710
    assert not any(w.startswith(("TX", "RX", "SA1")) for w in sim.writes)
