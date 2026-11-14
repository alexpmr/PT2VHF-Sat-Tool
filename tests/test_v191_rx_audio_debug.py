"""v1.9.1: debug do áudio RX em arquivo (interrupção periódica do áudio)."""
import sys
import time

import numpy as np

from sat_tool import sdr
from sat_tool.audio_ring import AudioRing
from sat_tool.rx_debug import RxAudioDebug


def busy_gui_routine(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        pass


def test_log_records_summary_underrun_retune_and_gui_stall_with_stack(tmp_path):
    dbg = RxAudioDebug(tmp_path)
    dbg.start("teste")
    ring = AudioRing()
    rx = sdr.SdrReceiver(lambda: sdr.SimulatedSource(fm_tone=1000), on_audio=ring.push)
    rx.debug = dbg
    rx.tune(145_800_000)
    rx.start()
    end = time.monotonic() + 1.6
    while time.monotonic() < end:
        dbg.heartbeat()
        if ring.primed:
            dbg.pull(960, ring.level_ms, False)
            ring.pull(960)
        dbg.second(ring, "ActiveState/NoError")
        time.sleep(0.02)
    dbg.heartbeat()
    busy_gui_routine(0.4)            # interface "travada": o vigia grava a pilha
    dbg.heartbeat()
    before = ring.underruns
    ring.pull(48_000 * 5)            # força falta de áudio
    dbg.pull(48_000 * 5, 10.0, ring.underruns != before)
    rx.stop()
    dbg.stop()
    text = (tmp_path / "rx-audio-debug.log").read_text(encoding="utf-8")
    assert "resumo: blocos=" in text and "saida=ActiveState/NoError" in text
    assert "resintonia: centro" in text
    assert "FALTA DE ÁUDIO" in text
    assert "INTERFACE TRAVADA" in text
    if sys.platform.startswith("linux"):   # no macOS o vigia pode não pegar o GIL a tempo: fica o registro sem pilha
        assert "busy_gui_routine" in text
    assert "desligado" in text.splitlines()[-1]


def test_disabled_debug_writes_nothing(tmp_path):
    dbg = RxAudioDebug(tmp_path)
    dbg.pull(100, 1.0, True); dbg.sdr_block(1.0, 0.1, 1, 1); dbg.retune(1, 2); dbg.heartbeat()
    dbg.second(AudioRing())
    assert not (tmp_path / "rx-audio-debug.log").exists()


def test_ring_counts_drops():
    ring = AudioRing()
    for _ in range(40):
        ring.push(np.zeros(4800, np.float32))
    assert ring.drops >= 1


def test_log_export_includes_rx_debug(tmp_path):
    from sat_tool.log_journal import EventJournal
    import zipfile
    diag = tmp_path / "diag"; diag.mkdir()
    (diag / "rx-audio-debug.log").write_text("x", encoding="utf-8")
    journal = EventJournal(tmp_path / "logs")
    journal.export(tmp_path / "out.zip", diagnostics_dir=diag, version="t")
    names = zipfile.ZipFile(tmp_path / "out.zip").namelist()
    assert any(n.endswith("rx-audio-debug.log") for n in names)


def test_sdr_panel_checkbox_turns_debug_on_and_is_remembered():
    import os, subprocess, sys, textwrap
    source = textwrap.dedent(r'''
        import tempfile, os
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            os.environ["LOCALAPPDATA"] = d
            from sat_tool import app as gui
            from sat_tool.config import Config
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
            gui.Config=lambda:Config(Path(d)/"cfg")
            app=gui.QApplication([])
            w=gui.MainWindow(); app.processEvents()
            panel=w.sdr_panel
            panel.rx_debug_enable.setChecked(True); app.processEvents()
            panel.drain(); panel.rx_debug._second -= 2; panel.drain()
            assert w.config.values["rx_audio_debug"] is True
            log=Path(d)/"PT2VHF"/"SatTool"/"diagnostics"/"rx-audio-debug.log"
            text=log.read_text(encoding="utf-8")
            assert "ligado" in text and "resumo: blocos=" in text, text
            panel.rx_debug_enable.setChecked(False)
            assert "desligado" in log.read_text(encoding="utf-8")
            panel.shutdown()
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr


class FakeDongle:
    """Como o hardware: gera amostras em tempo real; na leitura síncrona perde o que chegou entre chamadas."""

    def __init__(self):
        self.cancel = None
        self.produced = 0

    def read_samples(self, n):
        time.sleep(n / 960_000)
        return np.zeros(n, np.complex64)

    def read_samples_async(self, callback, n):
        import threading
        self.cancel = threading.Event()
        due = time.monotonic()
        while not self.cancel.is_set():
            due += n / 960_000      # prazo absoluto: o sleep do Windows (~15 ms) não atrasa o "dongle"
            time.sleep(max(0.0, due - time.monotonic()))
            self.produced += 1
            callback(np.zeros(n, np.complex64), None)

    def cancel_read_async(self):
        self.cancel.set()

    def close(self):
        pass


def make_source(remote=False):
    src = sdr.RtlSource.__new__(sdr.RtlSource)
    src.sdr = FakeDongle()
    src.streaming = not remote
    src._async_q = src._async_thread = src._async_error = None
    src.dropped_blocks = 0
    return src


def test_streaming_source_keeps_reading_while_demodulation_takes_time():
    """Antes: o dongle só era lido durante read_samples; o tempo de demodulação virava amostras perdidas
    (áudio mais lento que o tempo real, buffer da placa esvaziando a cada ~2,4 s). Agora a leitura USB
    continua durante o processamento e nenhum bloco produzido se perde. Sem depender da velocidade do CI."""
    sync = make_source(remote=True)
    t0, idle = time.monotonic(), 0.0
    for _ in range(8):
        sync.read(sdr.BLOCK)
        t = time.monotonic(); time.sleep(0.03); idle += time.monotonic() - t   # dongle sem leitura: perdido
    assert idle / (time.monotonic() - t0) > 0.15
    src = make_source(remote=False)
    consumed = 0
    for _ in range(8):
        src.read(sdr.BLOCK)
        consumed += 1
        time.sleep(0.03)            # "demodulação"
    time.sleep(0.25)
    produced = src.sdr.produced
    src.close()
    assert src.dropped_blocks == 0
    assert produced >= consumed and produced - consumed <= src._async_q.qsize() + 1


def test_set_decoder_keeps_the_running_afsk_demodulator():
    rx = sdr.SdrReceiver(lambda: None)
    rx.set_decoder("afsk1200"); first = rx.afsk
    rx.set_decoder("afsk1200")
    assert rx.afsk is first
    rx.set_decoder("none")
    assert rx.afsk is None
