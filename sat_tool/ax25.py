"""Decodificador AFSK 1200 (Bell 202) → HDLC → AX.25, e utilidades de quadros/KISS.

Usado para APRS e digipeater da ISS direto do áudio do SDR. Outros protocolos
(9k6 GMSK etc.) chegam prontos do SoundModem do UZ7HO por KISS.
"""
from __future__ import annotations

import numpy as np

MARK_HZ = 1200.0
SPACE_HZ = 2200.0
BAUD = 1200.0


def crc_x25(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF


def fcs_ok(frame: bytes) -> bool:
    return len(frame) >= 3 and crc_x25(frame[:-2]) == int.from_bytes(frame[-2:], "little")


class AfskDemodulator:
    """Demodulador não coerente com correlação mark/space e recuperação de relógio por PLL."""

    def __init__(self, rate: int = 48_000):
        self.rate = rate
        self.spb = rate / BAUD
        win = int(round(self.spb))
        t = np.arange(win) / rate
        self.kernels = [np.exp(2j * np.pi * f * t).astype(np.complex64) for f in (MARK_HZ, SPACE_HZ)]
        self.hist = np.zeros(win - 1, dtype=np.float32)
        self.phase = 0.0
        self.last_level = 0
        self.hdlc = HdlcDeframer()

    def process(self, audio: np.ndarray) -> list[bytes]:
        data = np.concatenate([self.hist, audio.astype(np.float32)])
        self.hist = data[-(len(self.kernels[0]) - 1):]
        mark = np.abs(np.convolve(data, self.kernels[0], mode="valid"))
        space = np.abs(np.convolve(data, self.kernels[1], mode="valid"))
        levels = (mark > space).astype(np.int8)
        frames = []
        for level in levels:
            if level != self.last_level:  # transição: puxa a fase para o centro do bit
                self.phase += (0.5 - self.phase) * 0.3
                self.last_level = level
            self.phase += 1.0 / self.spb
            if self.phase >= 1.0:
                self.phase -= 1.0
                frame = self.hdlc.push_level(int(level))
                if frame:
                    frames.append(frame)
        return frames


class HdlcDeframer:
    """NRZI → bits, flags 0x7E, retirada de bit stuffing e verificação de FCS."""

    def __init__(self):
        self.prev_level = 0
        self.ones = 0
        self.bits: list[int] = []
        self.in_frame = False
        self.shift = 0

    def push_level(self, level: int):
        bit = 1 if level == self.prev_level else 0
        self.prev_level = level
        return self.push_bit(bit)

    def push_bit(self, bit: int):
        self.shift = ((self.shift >> 1) | (bit << 7)) & 0xFF
        if self.shift == 0x7E:  # flag
            frame = None
            if self.in_frame and len(self.bits) >= 7 + 8 * 17:
                bits = self.bits[:-7]
                usable = len(bits) - len(bits) % 8
                data = bytes(sum(bits[i + j] << j for j in range(8)) for i in range(0, usable, 8))
                if fcs_ok(data):
                    frame = data[:-2]
            self.bits, self.ones, self.in_frame = [], 0, True
            return frame
        if not self.in_frame:
            return None
        if bit:
            self.ones += 1
            if self.ones > 6:  # abort
                self.in_frame, self.bits = False, []
                return None
        else:
            if self.ones == 5:  # bit de stuffing
                self.ones = 0
                return None
            self.ones = 0
        self.bits.append(bit)
        if len(self.bits) > 8 * 400:
            self.in_frame, self.bits = False, []
        return None


def encode_address(call: str, last: bool = False) -> bytes:
    base, _, ssid = call.upper().partition("-")
    out = bytes((ord(c) << 1) for c in base.ljust(6)[:6])
    return out + bytes([0x60 | ((int(ssid or 0) & 0x0F) << 1) | (1 if last else 0)])


def build_ui_frame(dest: str, source: str, path: list[str], info: bytes) -> bytes:
    calls = [dest, source] + list(path)
    addr = b"".join(encode_address(c, i == len(calls) - 1) for i, c in enumerate(calls))
    return addr + b"\x03\xf0" + info


def decode_address(raw: bytes) -> str:
    call = "".join(chr(b >> 1) for b in raw[:6]).strip()
    ssid = (raw[6] >> 1) & 0x0F
    return f"{call}-{ssid}" if ssid else call


def frame_to_text(frame: bytes) -> str:
    """Formato TNC2 legível: ORIGEM>DESTINO,CAMINHO:info."""
    addrs = []
    i = 0
    while i + 7 <= len(frame):
        addrs.append(decode_address(frame[i:i + 7]) + ("*" if i >= 14 and frame[i + 6] & 0x80 else ""))
        last = frame[i + 6] & 1
        i += 7
        if last:
            break
    if len(addrs) < 2:
        return frame.hex()
    info = frame[i + 2:] if i + 2 <= len(frame) else b""
    head = addrs[1] + ">" + addrs[0] + ("," + ",".join(addrs[2:]) if len(addrs) > 2 else "")
    return head + ":" + info.decode("latin-1", "replace")


def modulate_afsk(frame: bytes, rate: int = 48_000, flags: int = 30) -> np.ndarray:
    """Gera áudio AFSK de um quadro (para testes e autoteste do decodificador)."""
    body = frame + crc_x25(frame).to_bytes(2, "little")
    bits, ones = [], 0
    for byte in body:
        for j in range(8):
            b = (byte >> j) & 1
            bits.append(b)
            ones = ones + 1 if b else 0
            if ones == 5:
                bits.append(0)
                ones = 0
    flag = [0, 1, 1, 1, 1, 1, 1, 0]
    stream = flag * flags + bits + flag * 4
    level, levels = 0, []
    for b in stream:
        if b == 0:
            level ^= 1
        levels.append(level)
    spb = rate / BAUD
    out, phase, acc = [], 0.0, 0.0
    for lv in levels:
        acc += spb
        n = int(acc)
        acc -= n
        f = MARK_HZ if lv else SPACE_HZ
        ph = phase + 2 * np.pi * f / rate * np.arange(1, n + 1)
        out.append(np.sin(ph))
        phase = float(ph[-1]) if n else phase
    return (np.concatenate(out) * 0.5).astype(np.float32)


# KISS (SoundModem UZ7HO, Direwolf, GetKISS+)
FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD


def kiss_unescape(data: bytes) -> bytes:
    out, esc = bytearray(), False
    for b in data:
        if esc:
            out.append(FEND if b == TFEND else FESC if b == TFESC else b)
            esc = False
        elif b == FESC:
            esc = True
        else:
            out.append(b)
    return bytes(out)


def kiss_escape(data: bytes) -> bytes:
    return data.replace(bytes([FESC]), bytes([FESC, TFESC])).replace(bytes([FEND]), bytes([FESC, TFEND]))


class KissDecoder:
    """Separa quadros KISS de um fluxo TCP; devolve apenas quadros de dados (comando 0)."""

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer += data
        frames = []
        while True:
            start = self.buffer.find(FEND)
            if start < 0:
                self.buffer.clear()
                break
            end = self.buffer.find(FEND, start + 1)
            if end < 0:
                del self.buffer[:start]
                break
            raw = kiss_unescape(bytes(self.buffer[start + 1:end]))
            del self.buffer[:end]
            if len(raw) > 1 and raw[0] & 0x0F == 0:
                frames.append(raw[1:])
        return frames
