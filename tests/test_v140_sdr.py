"""v1.4.0: receptor SDR com fonte simulada — Doppler digital, áudio, AFSK, espectro e gravação."""
import time
import wave

import numpy as np

from sat_tool import ax25, dsp, sdr


def _run(receiver, seconds):
    receiver.start()
    end = time.time() + seconds
    while time.time() < end and receiver.status.running is not False or time.time() < end:
        time.sleep(0.05)
        if time.time() >= end:
            break
    receiver.stop()


def test_receiver_tracks_doppler_and_decodes_afsk(tmp_path):
    frame = ax25.build_ui_frame("CQ", "PT2VHF", ["ARISS"], b">teste SDR")
    audio = np.concatenate([ax25.modulate_afsk(frame), np.zeros(4800, dtype=np.float32)])
    downlink = 145_825_000
    source = sdr.SimulatedSource(signal_hz=downlink + 3_000, afsk_audio=audio)  # +3 kHz Doppler
    frames, spectra, chunks = [], [], []
    rx = sdr.SdrReceiver(lambda: source, on_audio=chunks.append,
                         on_spectrum=lambda s, c: spectra.append((s, c)),
                         on_frame=lambda f, src: frames.append(f))
    rx.set_mode("FM")
    rx.set_decoder("afsk1200")
    rx.tune(downlink + 3_000)
    rx.start_recording(tmp_path, "pass1")
    _run(rx, 2.5)
    assert rx.status.error == ""
    assert source.center == downlink + 3_000 - sdr.IF_OFFSET
    assert frame in frames
    assert spectra and spectra[0][0].shape == (4096,)
    with wave.open(str(tmp_path / "pass1.wav")) as w:
        assert w.getframerate() == dsp.AUDIO_RATE and w.getnframes() > dsp.AUDIO_RATE


def test_small_doppler_steps_do_not_retune_center():
    source = sdr.SimulatedSource(signal_hz=435_000_000)
    rx = sdr.SdrReceiver(lambda: source)
    rx.tune(435_000_000)
    rx.start(); time.sleep(0.4)
    first = source.center
    rx.tune(435_009_000)          # +9 kHz: só deslocamento digital
    time.sleep(0.4)
    assert source.center == first
    assert abs(rx.demod.offset_hz - (435_009_000 - first)) < 1
    rx.tune(435_500_000)          # salto grande: reposiciona o centro
    time.sleep(0.4)
    rx.stop()
    assert source.center == 435_500_000 - sdr.IF_OFFSET


def test_detect_devices_without_hardware_is_graceful():
    devices, message = sdr.detect_devices()
    assert isinstance(devices, list)
    assert devices or message


def test_open_error_help_mentions_zadig_on_windows(monkeypatch):
    monkeypatch.setattr(sdr.sys, "platform", "win32")
    assert "Preparar RTL-SDR" in sdr.open_error_help(OSError("usb_claim_interface error -12"))
