"""CAT autodetectado: varre portas seriais e velocidades e identifica o rádio só com leitura.

TS-2000: envia "ID;" e espera "ID019;". FT-817/818/857/897: lê frequência/modo (0x03) e valida
o BCD. Nada além dos comandos de identificação é enviado; PTT nunca é comandado. Portas de
outros aparelhos (GPS, ESP32 do rotor) não são aceitas sem resposta válida do protocolo.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

TS2000_BAUDS = (57600, 38400, 19200, 9600, 4800)
FT817_BAUDS = (38400, 9600, 4800)


@dataclass
class ScanResult:
    model: str          # "TS-2000" ou "FT-817"
    port: str
    baud: int
    stopbits: int
    detail: str = ""


def _open(factory, port, baud, stopbits):
    if factory is not None:
        return factory(port, baud, stopbits)
    import serial
    return serial.Serial(port, baudrate=baud, bytesize=8, parity="N", stopbits=stopbits,
                         timeout=0.25, write_timeout=0.4)


def probe_ts2000(ser) -> bool:
    ser.reset_input_buffer()
    ser.write(b"ID;")
    deadline, buf = time.monotonic() + 0.6, b""
    while time.monotonic() < deadline and b";" not in buf and len(buf) < 32:
        chunk = ser.read(16)
        if chunk:
            buf += chunk
    return b"ID019;" in buf


FT817_MODE_CODES = {0x00, 0x01, 0x02, 0x03, 0x04, 0x06, 0x08, 0x0A, 0x0C, 0x82, 0x88, 0x8A, 0x8C}
FT817_RANGES = ((100_000, 56_000_000), (76_000_000, 154_000_000), (420_000_000, 470_000_000))


def _ft817_read(ser) -> Optional[int]:
    ser.reset_input_buffer()
    ser.write(b"\x00\x00\x00\x00\x03")
    data = ser.read(5)
    if len(data) != 5 or data[4] not in FT817_MODE_CODES:
        return None
    if ser.read(1):  # resposta do FT-817 tem exatamente 5 bytes
        return None
    digits = [(b >> 4, b & 0x0F) for b in data[:4]]
    if any(d > 9 for pair in digits for d in pair):
        return None
    hz = int("".join(f"{a}{b}" for a, b in digits)) * 10
    return hz if any(lo <= hz <= hi for lo, hi in FT817_RANGES) else None


def probe_ft817(ser) -> Optional[int]:
    """Duas leituras idênticas e válidas: evita confundir GPS/ESP32 com o rádio."""
    first = _ft817_read(ser)
    if not first:
        return None
    return first if _ft817_read(ser) == first else None


def scan(ports: list[str], *, preferred: Optional[tuple[str, int]] = None,
         progress: Callable[[str], None] = lambda s: None,
         cancel: Optional[threading.Event] = None, serial_factory=None) -> tuple[Optional[ScanResult], list[str]]:
    """Retorna (rádio encontrado ou None, relatório de cada tentativa)."""
    report: list[str] = []
    ordered = list(dict.fromkeys(([preferred[0]] if preferred else []) + list(ports)))
    for port in ordered:
        attempts = [("TS-2000", b, 1) for b in TS2000_BAUDS] + [("FT-817", b, 2) for b in FT817_BAUDS]
        if preferred and port == preferred[0]:
            attempts.sort(key=lambda a: a[1] != preferred[1])
        busy = False
        for model, baud, stop in attempts:
            if cancel is not None and cancel.is_set():
                report.append("Varredura cancelada")
                return None, report
            progress(f"{port} · {baud} bps · {model}")
            try:
                ser = _open(serial_factory, port, baud, stop)
            except Exception as exc:
                text = str(exc)
                busy = any(k in text.lower() for k in ("acesso negado", "access is denied", "busy", "permissionerror", "denied"))
                report.append(f"{port}: {'ocupada por outro programa' if busy else 'não abriu'} ({text[:80]})")
                break  # a porta não abre em nenhuma velocidade
            try:
                if model == "TS-2000" and probe_ts2000(ser):
                    return ScanResult(model, port, baud, stop, "ID019"), report
                if model == "FT-817":
                    hz = probe_ft817(ser)
                    if hz:
                        return ScanResult(model, port, baud, stop, f"{hz / 1e6:.5f} MHz"), report
            except Exception as exc:
                report.append(f"{port} {baud}: {exc}")
            finally:
                try:
                    ser.close()
                except Exception:
                    pass
        else:
            report.append(f"{port}: sem resposta de TS-2000/FT-817")
    return None, report
