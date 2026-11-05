"""v1.4.0: AFSK 1200/AX.25 e demodulação FM/SSB/CW com sinais sintéticos."""
import numpy as np

from sat_tool import ax25, dsp


def test_afsk_roundtrip_with_noise_and_stuffing():
    frame = ax25.build_ui_frame("APRS", "PT2VHF-9", ["ARISS"], b"!1554.00S/04756.00W-~~~~~ teste \x7e\x7f")
    audio = ax25.modulate_afsk(frame)
    rng = np.random.default_rng(1)
    audio = np.concatenate([np.zeros(5000), audio, np.zeros(5000)]) + rng.normal(0, 0.05, len(audio) + 10000)
    demod = ax25.AfskDemodulator()
    got = []
    for block in np.array_split(audio.astype(np.float32), 37):  # streaming em blocos
        got += demod.process(block)
    assert got == [frame]
    assert ax25.frame_to_text(frame).startswith("PT2VHF-9>APRS,ARISS:!1554.00S")


def test_kiss_decoder_splits_and_unescapes():
    frame = b"\x82\xa0\xa4\xa6@@\x60" + b"\xc0\xdb abc"
    stream = bytes([0xC0, 0x00]) + ax25.kiss_escape(frame) + bytes([0xC0])
    dec = ax25.KissDecoder()
    assert dec.feed(stream[:5]) == []
    assert dec.feed(stream[5:]) == [frame]


def _tone_iq(freq, seconds=0.2, rate=dsp.SDR_RATE, fm_audio=None):
    t = np.arange(int(rate * seconds)) / rate
    if fm_audio:
        phase = 2 * np.pi * freq * t + 5000 / fm_audio * np.sin(2 * np.pi * fm_audio * t)
    else:
        phase = 2 * np.pi * freq * t
    return np.exp(1j * phase).astype(np.complex64)


def _peak(audio):
    spec = np.abs(np.fft.rfft(audio[len(audio) // 2:]))
    return np.argmax(spec) * dsp.AUDIO_RATE / (len(audio) - len(audio) // 2)


def test_fm_demod_recovers_tone_at_offset():
    d = dsp.Demodulator("FM")
    d.offset_hz = 100_000
    audio = d.process(_tone_iq(100_000, fm_audio=1000))
    assert abs(_peak(audio) - 1000) < 30


def test_usb_lsb_cw_produce_expected_pitch():
    for mode, rf, pitch in (("USB", 1500, 1500), ("LSB", -1500, 1500), ("CW", 0, dsp.CW_PITCH_HZ)):
        d = dsp.Demodulator(mode)
        d.offset_hz = 50_000
        audio = d.process(_tone_iq(50_000 + rf))
        assert abs(_peak(audio) - pitch) < 40, mode
    # banda lateral oposta é rejeitada
    d = dsp.Demodulator("USB")
    wrong = d.process(_tone_iq(-1500))
    right = dsp.Demodulator("USB").process(_tone_iq(1500))
    assert np.std(wrong[4000:]) < 0.2 * np.std(right[4000:]) or np.std(wrong) < 1e-3


def test_spectrum_peak_position():
    spec = dsp.power_spectrum_db(_tone_iq(240_000, 0.05), 4096)
    peak_hz = (np.argmax(spec) - 2048) * dsp.SDR_RATE / 4096
    assert abs(peak_hz - 240_000) < dsp.SDR_RATE / 4096 * 2
