"""Telemetria: pipelines por protocolo, cliente KISS (SoundModem UZ7HO), decodificação
SatNOGS (satnogs-decoders), log CSV e envio opcional ao SatNOGS DB (protocolo SiDS).

Pipelines (ideia do SatDump): cada transmissor do SatNOGS indica modo e baud; daí se
escolhe voz (FM/SSB/CW), AFSK 1200 interno ou quadros prontos via SoundModem por KISS.
O SoundModem aceita vários clientes: o GetKISS+ do DK3WN pode continuar ligado em paralelo.
"""
from __future__ import annotations

import csv
import json
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import requests

from . import ax25

SATNOGS_SATELLITES = "https://db.satnogs.org/api/satellites/"
SATNOGS_TELEMETRY = "https://db.satnogs.org/api/telemetry/"
HEADERS = {"User-Agent": "PT2VHF-Sat-Tool (radio amateur tracking tool)", "Accept": "application/json"}


def pipeline_for(row: dict) -> str:
    """'voice', 'afsk1200' (decodificado aqui) ou 'kiss' (SoundModem/externo)."""
    mode = str(row.get("mode") or "").upper()
    baud = row.get("baud") or 0
    try:
        baud = float(baud)
    except (TypeError, ValueError):
        baud = 0
    if mode in ("FM", "SSB", "USB", "LSB", "CW", "AM") and baud in (0, 0.0):
        return "voice"
    if "AFSK" in mode and baud in (0, 1200, 1200.0):
        return "afsk1200"
    if mode.startswith("FM") and not baud:
        return "voice"
    return "kiss"


PIPELINE_LABELS = {
    "voice": "Voz (FM/SSB/CW) — áudio do SDR",
    "afsk1200": "AFSK 1200 — decodificador interno",
    "kiss": "Dados (GMSK/BPSK/9k6…) — SoundModem UZ7HO via KISS",
}


class KissTcpClient:
    """Lê quadros de um servidor KISS TCP (SoundModem 8100, Direwolf 8001), com reconexão."""

    def __init__(self, host: str, port: int, on_frame: Callable[[bytes, str], None],
                 on_status: Callable[[str], None] = lambda s: None):
        self.host, self.port = host, int(port)
        self.on_frame, self.on_status = on_frame, on_status
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.connected = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="kiss-tcp", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self):
        while not self._stop.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=3) as sock:
                    sock.settimeout(1)
                    self.connected = True
                    self.on_status(f"KISS conectado a {self.host}:{self.port}")
                    decoder = ax25.KissDecoder()
                    while not self._stop.is_set():
                        try:
                            data = sock.recv(4096)
                        except socket.timeout:
                            continue
                        if not data:
                            break
                        for frame in decoder.feed(data):
                            self.on_frame(frame, f"KISS {self.host}:{self.port}")
            except OSError as exc:
                self.on_status(f"KISS indisponível em {self.host}:{self.port}: {exc}")
            self.connected = False
            self._stop.wait(5)


class TelemetryDecoder:
    """Associa NORAD → decodificador do satnogs-decoders (consulta ao SatNOGS DB com cache)."""

    def __init__(self, data_dir: Path):
        self.cache_file = Path(data_dir) / "satnogs_decoders.json"
        try:
            self.cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except Exception:
            self.cache = {}

    def decoder_names(self, norad: str, fetch: bool = True) -> list[str]:
        norad = str(norad)
        if norad in self.cache:
            return self.cache[norad]
        if not fetch:
            return []
        names: list[str] = []
        try:
            r = requests.get(SATNOGS_SATELLITES, params={"norad_cat_id": norad, "format": "json"},
                             headers=HEADERS, timeout=15)
            r.raise_for_status()
            for sat in r.json():
                names += [t.get("decoder") for t in sat.get("telemetries") or [] if t.get("decoder")]
        except Exception:
            return []
        self.cache[norad] = names
        try:
            self.cache_file.write_text(json.dumps(self.cache), encoding="utf-8")
        except OSError:
            pass
        return names

    @staticmethod
    def decode_with(name: str, frame: bytes) -> dict:
        from satnogsdecoders import decoder
        cls = getattr(decoder, name.capitalize(), None) or getattr(decoder, name, None)
        if cls is None or not hasattr(cls, "from_bytes"):
            return {}
        struct = cls.from_bytes(frame)
        return decoder.get_fields(struct)

    def decode(self, frame: bytes, norad: str, fetch: bool = True) -> tuple[str, dict]:
        for name in self.decoder_names(norad, fetch):
            try:
                fields = self.decode_with(name, frame)
            except Exception:
                continue
            if fields:
                return name, fields
        return "", {}


class TelemetryLog:
    """Log CSV por dia: UTC, NORAD, origem, tamanho, hex, texto AX.25, campos decodificados."""

    COLUMNS = ["utc", "norad", "satellite", "source", "bytes", "hex", "ax25", "decoder", "fields"]

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def append(self, record: dict) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"telemetria_{record['utc'][:10]}.csv"
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.COLUMNS)
            if new:
                writer.writeheader()
            writer.writerow({k: record.get(k, "") for k in self.COLUMNS})
        return path


def make_record(frame: bytes, norad: str, satellite: str, source: str, decoder_name: str = "",
                fields: Optional[dict] = None, when: Optional[datetime] = None) -> dict:
    when = when or datetime.now(timezone.utc)
    try:
        text = ax25.frame_to_text(frame)
    except Exception:
        text = ""
    return {"utc": when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", "norad": str(norad),
            "satellite": satellite, "source": source, "bytes": len(frame), "hex": frame.hex().upper(),
            "ax25": text, "decoder": decoder_name,
            "fields": json.dumps(fields or {}, ensure_ascii=False, default=str)}


def _coord(value: float, pos: str, neg: str) -> str:
    return f"{abs(float(value)):.4f}{pos if float(value) >= 0 else neg}"


def sids_payload(frame: bytes, norad: str, callsign: str, lat: float, lon: float,
                 when: Optional[datetime] = None) -> dict:
    when = when or datetime.now(timezone.utc)
    return {"noradID": str(norad), "source": callsign.upper(),
            "timestamp": when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "frame": frame.hex().upper(), "locator": "longLat",
            "longitude": _coord(lon, "E", "W"), "latitude": _coord(lat, "N", "S")}


def upload_to_satnogs(frame: bytes, norad: str, callsign: str, lat: float, lon: float) -> int:
    """Envia um quadro ao SatNOGS DB (opt-in). Retorna o código HTTP."""
    r = requests.post(SATNOGS_TELEMETRY, data=sids_payload(frame, norad, callsign, lat, lon),
                      headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
    return r.status_code
