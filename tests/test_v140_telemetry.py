"""v1.4.0: pipelines, cliente KISS (SoundModem), log CSV, SiDS e satnogs-decoders."""
import csv
import socket
import threading
import time
from datetime import datetime, timezone

from sat_tool import ax25, telemetry


def test_pipeline_choice_from_satnogs_transmitters():
    assert telemetry.pipeline_for({"mode": "FM", "baud": None}) == "voice"
    assert telemetry.pipeline_for({"mode": "AFSK", "baud": 1200}) == "afsk1200"
    assert telemetry.pipeline_for({"mode": "GMSK", "baud": 9600}) == "kiss"
    assert telemetry.pipeline_for({"mode": "USB"}) == "voice"


def test_kiss_client_receives_soundmodem_frames():
    frame = ax25.build_ui_frame("CQ", "PT2VHF", [], b"kiss")
    server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen(1)
    port = server.getsockname()[1]
    def serve():
        conn, _ = server.accept()
        conn.sendall(b"\xc0\x00" + ax25.kiss_escape(frame) + b"\xc0")
        time.sleep(0.5); conn.close()
    threading.Thread(target=serve, daemon=True).start()
    got = []
    client = telemetry.KissTcpClient("127.0.0.1", port, lambda f, s: got.append(f))
    client.start()
    for _ in range(40):
        if got: break
        time.sleep(0.05)
    client.stop(); server.close()
    assert got == [frame]


def test_log_csv_and_sids_payload(tmp_path):
    frame = ax25.build_ui_frame("CQ", "PT2VHF", [], b"tlm")
    when = datetime(2026, 11, 5, 12, 0, 1, 250000, tzinfo=timezone.utc)
    rec = telemetry.make_record(frame, "25544", "ISS", "SDR", "iss", {"x": 1}, when)
    path = telemetry.TelemetryLog(tmp_path).append(rec)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["norad"] == "25544" and rows[0]["ax25"].startswith("PT2VHF>CQ")
    p = telemetry.sids_payload(frame, "25544", "pt2vhf", -15.79, -47.88, when)
    assert p["timestamp"] == "2026-11-05T12:00:01.250Z"
    assert p["latitude"] == "15.7900S" and p["longitude"] == "47.8800W" and p["source"] == "PT2VHF"


def test_satnogs_decoder_iss_frame_offline(tmp_path):
    dec = telemetry.TelemetryDecoder(tmp_path)
    dec.cache["25544"] = ["iss"]
    frame = ax25.build_ui_frame("APRS", "PT2VHF", ["ARISS"], b"!1554.00S/04756.00W-ola")
    name, fields = dec.decode(frame, "25544", fetch=False)
    assert name == "iss" and fields
