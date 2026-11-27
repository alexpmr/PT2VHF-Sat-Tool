"""v1.9.8: correções dos achados da análise Reversa (_reversa_sdd/gaps.md, A1–A8)."""
import json

from sat_tool import config as config_module
from sat_tool.config import Config, DEFAULTS


def test_a4_settings_corrompido_abre_com_padroes(tmp_path):
    (tmp_path / "settings.json").write_text('{"station_lat": -15.8, ', encoding="utf-8")
    cfg = Config(tmp_path)
    assert cfg.values["update_interval_s"] == DEFAULTS["update_interval_s"]
    assert cfg.recovered_from is not None and cfg.recovered_from.name.startswith("settings.corrompido-")
    assert cfg.recovered_from.read_text(encoding="utf-8") == '{"station_lat": -15.8, '
    assert not (tmp_path / "settings.json").exists()
    assert any(bad == cfg.recovered_from for bad, _ in config_module.RECOVERIES)
    cfg.save()
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))


def test_a4_settings_que_nao_e_objeto(tmp_path):
    (tmp_path / "settings.json").write_text("[1, 2, 3]", encoding="utf-8")
    cfg = Config(tmp_path)
    assert cfg.recovered_from is not None
    assert cfg.values["update_interval_s"] == DEFAULTS["update_interval_s"]


def test_a4_settings_valido_nao_e_tocado(tmp_path):
    cfg = Config(tmp_path)
    cfg.values["update_interval_s"] = 3
    cfg.save()
    again = Config(tmp_path)
    assert again.recovered_from is None
    assert again.values["update_interval_s"] == 3


# --- A1: gravação do SDR -------------------------------------------------------------
import threading
import time

import numpy as np

from sat_tool import sdr


def test_a1_parar_gravacao_durante_recepcao_nao_derruba_o_sdr(tmp_path):
    source = sdr.SimulatedSource(signal_hz=435_000_000)
    rx = sdr.SdrReceiver(lambda: source)
    rx.tune(435_000_000)
    rx.start()
    try:
        for i in range(15):
            rx.start_recording(tmp_path, f"p{i}")
            time.sleep(0.02)
            rx.stop_recording()
        time.sleep(0.3)
        assert rx.status.running
        assert rx._thread is not None and rx._thread.is_alive()
    finally:
        rx.stop()


def test_a1_erro_de_disco_encerra_so_a_gravacao(tmp_path):
    rx = sdr.SdrReceiver(lambda: None)

    class Broken:
        closed = False

        def write(self, audio, channel):
            raise OSError("disco cheio")

        def close(self):
            Broken.closed = True

    rx._recorder = Broken()
    rx.status.recording = "x.wav"
    rx._record(np.zeros(10, dtype=np.float32), None)
    assert rx._recorder is None and rx.status.recording == ""
    assert "disco cheio" in rx.status.error and Broken.closed


# --- A2/A3: CAT FT-817 e rigctld ----------------------------------------------------
import socket

import pytest

from sat_tool import rigs


class SilentSerial:
    closed = False

    def reset_input_buffer(self): pass
    def write(self, data): pass
    def read(self, n): return b""
    def close(self): SilentSerial.closed = True


def test_a2_ft817_sem_resposta_fecha_a_porta():
    rig = rigs.FT817()
    with pytest.raises(TimeoutError):
        rig.connect("COM9", serial_factory=SilentSerial)
    assert SilentSerial.closed and rig.ser is None and not rig.connected


class ScriptedSocket:
    """rigctld falso: 'lento' faz a próxima resposta chegar só pela metade e depois estourar o tempo."""
    def __init__(self, slow_on=None):
        self.out, self.sent, self.slow_on, self.closed = b"", [], slow_on, False

    def settimeout(self, t): pass

    def sendall(self, data):
        cmd = data.decode().strip()
        self.sent.append(cmd)
        answer = b"145800000\n" if cmd == "f" else b"0\n" if cmd == "t" else b"RPRT 0\n"
        if cmd == self.slow_on:
            self.out += answer[:-1]   # resposta sem o fim de linha
            self.slow_on = "__done__"
            self._timeout_next = True
        else:
            self.out += answer

    def recv(self, n):
        if not self.out and getattr(self, "_timeout_next", False):
            self._timeout_next = False
            raise socket.timeout("timed out")
        out, self.out = self.out[:n], self.out[n:]
        return out

    def close(self): self.closed = True


def test_a3_rigctld_sem_resposta_na_conexao_fecha_o_socket():
    sock = ScriptedSocket(slow_on="f")
    rig = rigs.Rigctld()
    with pytest.raises(ConnectionError):
        rig.connect(sock_factory=lambda: sock)
    assert sock.closed and not rig.connected


def test_a3_rigctld_timeout_nao_desalinha_as_respostas():
    socks = [ScriptedSocket(slow_on="t"), ScriptedSocket()]
    made = []

    def factory():
        made.append(socks[len(made)])
        return made[-1]

    rig = rigs.Rigctld()
    rig.connect(sock_factory=factory)
    assert rig.is_transmitting() is None          # "t" estourou o tempo no meio da resposta
    assert made[0].closed and rig.connected
    assert rig.query("f") == "145800000"          # reabriu e a resposta é a de "f", não o resto da de "t"
    assert len(made) == 2


def test_a3_rigctld_desconectar_nao_reabre():
    sock = ScriptedSocket()
    rig = rigs.Rigctld()
    rig.connect(sock_factory=lambda: sock)
    rig.disconnect()
    with pytest.raises(ConnectionError):
        rig.query("f")


# --- A5: painel web só-localhost confere o Host ------------------------------------------
import http.client

from sat_tool.web_ui import LocalStatusServer, local_host_header


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(port, path, host):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest("GET", path, skip_host=True)
        conn.putheader("Host", host)
        conn.endheaders()
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def test_a5_host_local_aceito_e_rebinding_recusado():
    server = LocalStatusServer(lan=False, port=_free_port())
    server.publish({"satellite": "SO-50"})
    try:
        server.start()
        for host in (f"127.0.0.1:{server.port}", f"localhost:{server.port}", "localhost"):
            assert _get(server.port, "/api/status", host)[0] == 200
        status, _ = _get(server.port, "/api/status", f"atacante.example:{server.port}")
        assert status == 421
    finally:
        server.stop()


def test_a5_local_host_header():
    assert local_host_header("127.0.0.1:8094", 8094)
    assert local_host_header("[::1]:8094", 8094)
    assert not local_host_header("127.0.0.1.nip.io:8094", 8094)
    assert not local_host_header("localhost:9999", 8094)
    assert not local_host_header("", 8094)


# --- A6/A7: User-Agent e telemetria sem rede --------------------------------------------
from sat_tool import __version__, catalog, telemetry


def test_a6_user_agent_com_a_versao_real():
    assert catalog.HEADERS["User-Agent"].startswith(f"PT2VHF-Sat-Tool/{__version__} ")
    assert telemetry.HEADERS["User-Agent"].startswith(f"PT2VHF-Sat-Tool/{__version__} ")
    assert catalog.__doc__ and "Catalog cache" in catalog.__doc__


def test_a7_sem_rede_nao_consulta_a_cada_quadro(tmp_path, monkeypatch):
    calls = []

    def offline(*a, **k):
        calls.append(1)
        raise OSError("sem rede")

    monkeypatch.setattr(telemetry.requests, "get", offline)
    now = [1000.0]
    dec = telemetry.TelemetryDecoder(tmp_path, clock=lambda: now[0])
    for _ in range(20):
        assert dec.decoder_names("43017") == []
    assert len(calls) == 1
    now[0] += telemetry.RETRY_AFTER_S + 1
    dec.decoder_names("43017")
    assert len(calls) == 2
