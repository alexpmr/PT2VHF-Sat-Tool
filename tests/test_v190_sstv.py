"""v1.9.0: SSTV — VIS, modos, inclinação (relógio), desvio de tom, ruído, imagem salva e transmissão."""
import os
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from sat_tool import sstv

RATE = 48000


def picture(h=256, w=320):
    yy, xx = np.mgrid[0:h, 0:w]
    img = np.stack([xx * 255 // w, yy * 255 // h, (xx + yy) % 256], -1).astype(np.uint8)
    img[40:90, 40:140] = [255, 0, 0]
    img[150:220, 180:300] = [0, 0, 255]
    return img


def shift_tone(audio, hz):
    """Desloca todas as frequências do áudio (rádio fora de sintonia / Doppler residual em SSB)."""
    n = len(audio)
    spec = np.fft.fft(audio.astype(np.float64))
    h = np.zeros(n); h[0] = 1; h[1:n // 2] = 2
    return np.real(np.fft.ifft(spec * h) * np.exp(2j * np.pi * hz * np.arange(n) / RATE)).astype(np.float32)


def impair(audio, ppm=0.0, noise=0.0, offset_hz=0.0, lead_s=0.4, seed=1):
    if offset_hz:
        audio = shift_tone(audio, offset_hz)
    audio = np.concatenate([np.zeros(int(lead_s * RATE), np.float32), audio])
    if ppm:
        n = len(audio)
        audio = np.interp(np.arange(0, n, 1 + ppm * 1e-6), np.arange(n), audio).astype(np.float32)
    if noise:
        audio = audio + np.random.default_rng(seed).normal(0, noise, len(audio)).astype(np.float32)
    return audio


def error(image):
    return np.abs(image.pixels.astype(float) - sstv.fit_image(picture(), image.mode).astype(float))


@pytest.mark.parametrize("name", ["Robot 36", "Martin M2", "Scottie S2", "PD 50"])
def test_round_trip_with_vis_and_clock_error(name):
    images = sstv.decode_audio(impair(sstv.encode(picture(), name, RATE), ppm=-150), RATE)
    assert len(images) == 1 and images[0].mode.name == name
    assert np.median(error(images[0])) <= 3
    assert abs(images[0].slant_ppm - 150) < 25   # a inclinação medida bate com o relógio do "transmissor"


def test_tone_offset_is_measured_in_the_vis_and_removed():
    images = sstv.decode_audio(impair(sstv.encode(picture(), "Martin M2", RATE), offset_hz=80), RATE)
    assert abs(images[0].offset_hz - 80) < 3 and error(images[0]).mean() < 4


def test_noisy_signal_still_decodes_recognisable_picture():
    images = sstv.decode_audio(impair(sstv.encode(picture(), "Robot 36", RATE), noise=0.25, ppm=80), RATE)
    assert images and images[0].mode.name == "Robot 36"
    red = images[0].pixels[45:85, 45:135].mean(axis=(0, 1))
    assert red[0] > 170 and red[1] < 90 and red[2] < 90


def test_streaming_in_small_blocks_and_two_pictures_in_a_row():
    one = sstv.encode(picture(), "Robot 36", RATE)
    audio = impair(np.concatenate([one, np.zeros(RATE, np.float32), one]))
    dec, done, starts = sstv.Decoder(RATE), [], 0
    for i in range(0, len(audio), 1000):
        for ev in dec.feed(audio[i:i + 1000]):
            starts += ev[0] == "start"
            if ev[0] == "done":
                done.append(ev[1].pixels.copy())
    for ev in dec.feed(np.zeros(RATE, np.float32)):
        if ev[0] == "done":
            done.append(ev[1].pixels.copy())
    assert starts == 2 and len(done) == 2
    assert len(dec.freq) < RATE * 2   # o buffer não cresce sem limite


def test_every_mode_has_a_unique_vis_and_sane_timing():
    assert len(sstv.MODES) == 14 and len(sstv.BY_VIS) == 14
    assert round(sstv.MODES["Martin M1"].line_ms, 3) == 446.446
    assert round(sstv.MODES["Scottie S1"].line_ms, 2) == 428.22
    assert round(sstv.MODES["PD 120"].duration_s) == 126 and sstv.MODES["Robot 36"].line_ms == 150.0


def test_wav_round_trip(tmp_path):
    audio = sstv.encode(picture(), "Robot 36", RATE)
    sstv.write_wav(tmp_path / "a.wav", audio, RATE)
    data, rate = sstv.read_wav(tmp_path / "a.wav")
    assert rate == RATE and len(data) == len(audio)
    assert sstv.decode_audio(data, rate)[0].mode.name == "Robot 36"


def test_sstv_tab_saves_received_picture_and_prepares_transmission():
    source = textwrap.dedent(r'''
        import tempfile, time
        from pathlib import Path
        import numpy as np
        from sat_tool import app as gui, sstv
        from sat_tool.config import Config
        from sat_tool.sstv_panel import qimage_from_rgb, rgb_from_qimage
        class FakeWeb(gui.QWidget):
            def setHtml(self,*a,**k):pass
            def page(self):return self
            def runJavaScript(self,*a,**k):pass
            def reload(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda d:[]
        gui.MainWindow.background=lambda self,key,fn:None
        gui.MainWindow.check_for_updates=lambda self:None
        gui.MainWindow.show_official_site_notice=lambda self:None
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.show(); app.processEvents()
            panel=w.sdr_panel.sstv
            img=np.zeros((240,320,3),np.uint8); img[:, :160]=[255,255,0]
            assert (rgb_from_qimage(qimage_from_rgb(img))==img).all()
            # recepção: áudio do "RTL-SDR" entra pela mesma porta do receptor
            panel.rx_button.setChecked(True); app.processEvents()
            audio=np.concatenate([np.zeros(9600,np.float32), sstv.encode(img,"Robot 36",48000), np.zeros(48000,np.float32)])
            for i in range(0,len(audio),4800):
                w.sdr_panel._on_audio(audio[i:i+4800])
            end=time.monotonic()+60
            while time.monotonic()<end and not list((Path(d)/"sstv").glob("*.png")):
                app.processEvents(); time.sleep(0.05)
            saved=list((Path(d)/"sstv").glob("*.png"))
            assert saved and "Robot36" in saved[0].name, panel.rx_status.text()
            assert panel.save_button.isEnabled()
            panel.rx_button.setChecked(False)
            # transmissão: imagem → modo → áudio (sem PTT)
            path=Path(d)/"tx.png"; qimage_from_rgb(img).save(str(path))
            assert panel.load_tx_image(path)
            panel.tx_mode.setCurrentIndex(panel.tx_mode.findData("Martin M1")); app.processEvents()
            assert panel.tx_rgb.shape==(256,320,3) and panel.tx_button.isEnabled()
            assert abs(len(panel.tx_audio)/48000-(sstv.MODES["Martin M1"].duration_s+0.91))<0.1
            assert "PTT" in panel.tx_status.text()
            w.sdr_panel.shutdown()
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=180,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
