"""Rádios adicionais para RX/TX separados: Yaesu FT-817/818/857/897 e FT-847 (CAT binário), Yaesu CAT texto
(FT-991/991A…), ICOM CI-V, Kenwood CAT texto e Hamlib rigctld.

O TS-2000 continua com o driver dedicado em cat.py (modo SAT). Estes drivers recebem
frequências já corrigidas pelo Doppler. Nenhum deles aciona PTT.
"""
from __future__ import annotations

import socket
import time
from typing import Optional

FT817_MODES = {"LSB": 0x00, "USB": 0x01, "CW": 0x02, "CWR": 0x03, "AM": 0x04,
               "FM": 0x08, "DIG": 0x0A, "PKT": 0x0C}
FT817_MODE_NAMES = {v: k for k, v in FT817_MODES.items()} | {0x88: "FM", 0x82: "CW", 0x8A: "DIG", 0x0C: "PKT"}
HAMLIB_MODES = {"USB": "USB", "LSB": "LSB", "CW": "CW", "FM": "FM", "AM": "AM", "PKT": "PKTUSB", "DIG": "PKTUSB"}

RIG_MODELS = {
    "TS-2000": "Kenwood TS-2000 (modo SAT, CAT atual)",
    "FT-817": "Yaesu FT-817/818/857/897 (CAT 5 bytes)",
    "FT-847": "Yaesu FT-847 (modo SAT, CAT 5 bytes)",
    "YAESU": "Yaesu CAT texto (FT-991/991A, FTDX10, FTDX101, FT-710, FT-891)",
    "ICOM": "ICOM CI-V (IC-9700/910/9100/821 em MAIN/SUB; IC-746, IC-705, IC-7300…)",
    "KENWOOD": "Kenwood CAT texto (TS-480, TS-590, TS-890, TS-990, TS-2000 sem SAT…)",
    "RIGCTLD": "Hamlib rigctld (IC-9700, IC-910, FT-847, SDR++/gqrx…)",
    "SDR": "RTL-SDR embutido (somente RX)",
    "NONE": "Nenhum",
}


def normalize_mode(mode: str) -> str:
    m = (mode or "FM").upper()
    if m.startswith("FM"):
        return "FM"
    if m in ("USB", "LSB", "CW", "AM"):
        return m
    if m in ("SSB",):
        return "USB"
    if any(k in m for k in ("AFSK", "GMSK", "FSK", "BPSK", "PKT", "DATA")):
        return "PKT"
    return "USB" if "SSB" in m else "FM"


def bcd_frequency(hz: int) -> bytes:
    """FT-817: frequência em unidades de 10 Hz, 8 dígitos BCD em 4 bytes (MSB primeiro)."""
    if not 100_000 <= hz <= 470_000_000:
        raise ValueError("Frequência fora da faixa do FT-817")
    digits = f"{int(round(hz / 10)):08d}"
    return bytes(int(digits[i]) << 4 | int(digits[i + 1]) for i in range(0, 8, 2))


def parse_bcd_frequency(data: bytes) -> int:
    return int("".join(f"{b >> 4}{b & 0x0F}" for b in data[:4])) * 10


class FT817:
    """Yaesu FT-817/818 e família 857/897: comandos de 5 bytes, 8N2.

    Modos de uso:
    - RX ou TX isolado: sintoniza o VFO atual.
    - RX e TX no mesmo rádio (sem modo SAT): split com RX no VFO A e TX no VFO B; o VFO B é
      atualizado alternando VFO (0x81) só fora de transmissão.
    """
    name = "FT-817"

    def __init__(self, logger=None):
        self.ser = None
        self.log = logger or (lambda msg: None)
        self.split = False
        self.last_rx: tuple[int, str] | None = None
        self.last_tx: tuple[int, str] | None = None

    @property
    def connected(self) -> bool:
        return self.ser is not None

    def connect(self, port: str, baud: int = 9600, serial_factory=None):
        if serial_factory is None:
            import serial
            serial_factory = lambda: serial.Serial(port, baudrate=int(baud), bytesize=8, parity="N",
                                                   stopbits=2, timeout=0.5, write_timeout=0.5)
        self.ser = serial_factory()
        self.read_frequency()  # valida a comunicação
        self.log(f"FT-817: conectado em {port} {baud} 8N2")

    def disconnect(self):
        if self.ser is not None:
            try:
                if self.split:
                    self._cmd(b"\x00\x00\x00\x00\x82")
            except Exception:
                pass
            self.ser.close()
        self.ser, self.split = None, False

    def _cmd(self, data: bytes, reply: int = 0) -> bytes:
        if self.ser is None:
            raise ConnectionError("FT-817 desconectado")
        self.ser.reset_input_buffer()
        self.ser.write(data)
        if not reply:
            time.sleep(0.02)
            return b""
        answer = self.ser.read(reply)
        if len(answer) != reply:
            raise TimeoutError("FT-817 não respondeu ao CAT")
        return answer

    def read_frequency(self) -> tuple[int, str]:
        data = self._cmd(b"\x00\x00\x00\x00\x03", 5)
        return parse_bcd_frequency(data), FT817_MODE_NAMES.get(data[4], f"0x{data[4]:02X}")

    def is_transmitting(self) -> Optional[bool]:
        try:
            status = self._cmd(b"\x00\x00\x00\x00\xF7", 1)[0]
        except Exception:
            return None
        return (status & 0x80) == 0

    def _set(self, hz: int, mode: str):
        self._cmd(bcd_frequency(hz) + b"\x01")
        code = FT817_MODES.get(normalize_mode(mode), FT817_MODES["FM"])
        self._cmd(bytes([code, 0, 0, 0, 0x07]))

    def set_rx(self, hz: int, mode: str):
        if self.is_transmitting():
            return False
        self._set(hz, mode)
        self.last_rx = (hz, mode)
        return True

    def set_tx(self, hz: int, mode: str, same_rig_rx: bool = False):
        """TX isolado: VFO atual. Com same_rig_rx: split, TX no VFO B."""
        if self.is_transmitting():
            return False  # não muda frequência no meio do câmbio
        if not same_rig_rx:
            self._set(hz, mode)
        else:
            if not self.split:
                self._cmd(b"\x00\x00\x00\x00\x02")  # SPLIT ON
                self.split = True
            self._cmd(b"\x00\x00\x00\x00\x81")      # VFO A/B
            try:
                self._set(hz, mode)
            finally:
                self._cmd(b"\x00\x00\x00\x00\x81")  # volta para o VFO de RX
        self.last_tx = (hz, mode)
        return True


# Endereços CI-V de fábrica (o operador pode trocar em Configurações; xx na linha CAT do manual)
ICOM_ADDRESSES = {
    "IC-746": 0x56, "IC-746PRO": 0x66, "IC-756PRO": 0x5C, "IC-706MKIIG": 0x58, "IC-7000": 0x70,
    "IC-7100": 0x88, "IC-7300": 0x94, "IC-7610": 0x98, "IC-705": 0xA4, "IC-9100": 0x7C,
    "IC-9700": 0xA2, "IC-910": 0x60, "IC-821": 0x4C, "IC-820": 0x42, "IC-275": 0x10,
    "IC-475": 0x14, "IC-970": 0x2E, "IC-R8600": 0x96,
}
# v1.9.4: rádios com duas bandas (MAIN/SUB). RX e TX no mesmo rádio: SUB = RX (downlink), MAIN = TX (uplink),
# como no modo satélite deles. O split VFO A/B não serve: não cruza 145/435 MHz nesses rádios.
ICOM_DUAL_BAND = {"IC-9700", "IC-910", "IC-9100", "IC-820", "IC-821", "IC-970"}
ICOM_SAT_MODE = {"IC-9700", "IC-910", "IC-9100"}      # aceitam ligar o modo satélite por CI-V (16 5A)


def icom_model_for_address(address: int) -> str:
    return next((m for m, a in ICOM_ADDRESSES.items() if a == int(address)), "")


ICOM_MODES = {"LSB": 0x00, "USB": 0x01, "AM": 0x02, "CW": 0x03, "FM": 0x05, "PKT": 0x01}
ICOM_MODE_NAMES = {0x00: "LSB", 0x01: "USB", 0x02: "AM", 0x03: "CW", 0x04: "RTTY", 0x05: "FM", 0x07: "CW-R",
                   0x08: "RTTY-R", 0x17: "DV"}
CIV_CONTROLLER = 0xE0


def civ_frequency(hz: int) -> bytes:
    """CI-V: 10 dígitos BCD, byte menos significativo primeiro (50.950.000 Hz → 00 00 95 50 00)."""
    if not 30_000 <= hz <= 9_999_999_999:
        raise ValueError("Frequência fora da faixa do CI-V")
    digits = f"{int(hz):010d}"
    pairs = [digits[i:i + 2] for i in range(0, 10, 2)][::-1]
    return bytes(int(p[0]) << 4 | int(p[1]) for p in pairs)


def parse_civ_frequency(data: bytes) -> int:
    return int("".join(f"{b >> 4}{b & 0x0F}" for b in reversed(data[:5])))


def civ_frame(address: int, command: int, payload: bytes = b"", controller: int = CIV_CONTROLLER) -> bytes:
    if not 0 <= address <= 0xDF:
        raise ValueError("Endereço CI-V inválido")
    return bytes([0xFE, 0xFE, address, controller, command]) + bytes(payload) + b"\xFD"


class Icom:
    """ICOM CI-V (IC-746 e família). Frequência 0x05, modo 0x06, leitura 0x03/0x04, TX 0x1C 00.

    O barramento CI-V devolve o eco de cada quadro enviado; o eco é descartado. Sem PTT: o programa
    nunca envia 0x1C 00 01. RX e TX no mesmo rádio: split com RX no VFO A e TX no VFO B (como o FT-817).
    """
    name = "ICOM"

    def __init__(self, logger=None, address: int = ICOM_ADDRESSES["IC-746"], model: str = ""):
        self.ser = None
        self.log = logger or (lambda msg: None)
        self.address = int(address)
        self.model = model or icom_model_for_address(address)
        self.split = False
        self.same_rig = False      # RX e TX no mesmo rádio (definido ao conectar)
        self._sat_tried = False
        self._buf = b""

    @property
    def dual_band(self) -> bool:
        return self.model in ICOM_DUAL_BAND

    def use_same_rig(self, on: bool):
        """Chamado pelo painel quando RX e TX são o mesmo ICOM."""
        self.same_rig = bool(on)

    def _band(self, main: bool):
        self._command(0x07, b"\xD0" if main else b"\xD1")   # seleciona MAIN / SUB

    def _ensure_sat_mode(self):
        if self._sat_tried or self.model not in ICOM_SAT_MODE:
            return
        self._sat_tried = True
        try:
            self._command(0x16, b"\x5A\x01")
            self.log(f"ICOM {self.model}: modo satélite ligado (MAIN = TX, SUB = RX)")
        except Exception as exc:   # rádio sem o comando ou recusou: MAIN/SUB continua valendo
            self.log(f"ICOM {self.model}: modo satélite não ligado por CI-V ({exc})")

    @property
    def connected(self) -> bool:
        return self.ser is not None

    def connect(self, port: str, baud: int = 9600, serial_factory=None):
        if serial_factory is None:
            import serial
            serial_factory = lambda: serial.Serial(port, baudrate=int(baud), bytesize=8, parity="N",
                                                   stopbits=1, timeout=0.3, write_timeout=0.5)
        self.ser = serial_factory()
        try:
            self.read_frequency()  # valida endereço e velocidade
        except Exception:
            self.disconnect()
            raise
        self.name = f"ICOM {self.model or 'CI-V'} {self.address:02X}h"
        self.log(f"ICOM: conectado em {port} {baud} 8N1, endereço CI-V {self.address:02X}h")

    def disconnect(self):
        if self.ser is not None:
            try:
                if self.split:
                    self._command(0x0F, b"\x00")
            except Exception:
                pass
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser, self.split, self._buf = None, False, b""

    def _frames(self, deadline):
        while time.monotonic() < deadline:
            if b"\xFD" in self._buf:
                frame, _, self._buf = self._buf.partition(b"\xFD")
                start = frame.find(b"\xFE\xFE")
                if start >= 0:
                    yield frame[start:] + b"\xFD"
                continue
            chunk = self.ser.read(64)
            if chunk:
                self._buf += chunk
                if len(self._buf) > 512:
                    self._buf = self._buf[-128:]

    def _command(self, command: int, payload: bytes = b"", timeout: float = 1.0) -> bytes:
        """Envia e devolve a resposta do rádio (dados ou FB/FA), ignorando o eco do próprio quadro."""
        if self.ser is None:
            raise ConnectionError("ICOM desconectado")
        frame = civ_frame(self.address, command, payload)
        self._buf = b""
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass
        self.ser.write(frame)
        self.log("CI-V TX " + frame.hex(" ").upper())
        for answer in self._frames(time.monotonic() + timeout):
            if answer == frame or len(answer) < 6:
                continue  # eco do barramento
            if answer[2] != CIV_CONTROLLER or answer[3] != self.address:
                continue  # quadro de outro equipamento no barramento
            self.log("CI-V RX " + answer.hex(" ").upper())
            if answer[4] == 0xFA:
                raise RuntimeError(f"ICOM recusou o comando {command:02X}h (NG)")
            return answer[4:-1]
        raise TimeoutError(f"ICOM não respondeu (endereço CI-V {self.address:02X}h)")

    def read_frequency(self) -> tuple[int, str]:
        data = self._command(0x03)
        if data[0] != 0x03 or len(data) < 6:
            raise ValueError("Resposta de frequência CI-V inválida")
        hz = parse_civ_frequency(data[1:6])
        mode = "?"
        try:
            reply = self._command(0x04)
            if reply[0] == 0x04 and len(reply) >= 2:
                mode = ICOM_MODE_NAMES.get(reply[1], f"{reply[1]:02X}h")
        except (TimeoutError, RuntimeError, ValueError):
            pass
        return hz, mode

    def is_transmitting(self) -> Optional[bool]:
        try:
            data = self._command(0x1C, b"\x00", timeout=0.4)
        except Exception:
            return None   # IC-746 e outros mais antigos não têm 1C 00: não bloqueia
        return len(data) >= 3 and data[0] == 0x1C and data[2] == 0x01

    def _set(self, hz: int, mode: str):
        self._command(0x05, civ_frequency(hz))
        self._command(0x06, bytes([ICOM_MODES.get(normalize_mode(mode), ICOM_MODES["FM"])]))

    def set_rx(self, hz: int, mode: str):
        if self.same_rig and self.dual_band:
            # Downlink na SUB: muda também durante o TX (full duplex, o Doppler do RX segue no câmbio)
            self._ensure_sat_mode()
            self._band(main=False)
            self._set(hz, mode)
            return True
        if self.is_transmitting():
            return False
        self._set(hz, mode)
        return True

    def set_tx(self, hz: int, mode: str, same_rig_rx: bool = False):
        if (same_rig_rx or self.same_rig) and self.dual_band:
            self._ensure_sat_mode()
            self._band(main=True)            # uplink na MAIN
            self._set(hz, mode)
            return True
        if self.is_transmitting():
            return False
        if not same_rig_rx:
            self._set(hz, mode)
            return True
        if not self.split:
            self._command(0x0F, b"\x01")   # SPLIT ON
            self.split = True
        self._command(0x07, b"\x01")        # VFO B (TX)
        try:
            self._set(hz, mode)
        finally:
            self._command(0x07, b"\x00")    # volta ao VFO A (RX)
        return True


FT847_MODES = {"LSB": 0x00, "USB": 0x01, "CW": 0x02, "AM": 0x04, "FM": 0x08, "PKT": 0x01, "DIG": 0x01}
FT847_MODE_NAMES = {0x00: "LSB", 0x01: "USB", 0x02: "CW", 0x03: "CWR", 0x04: "AM", 0x08: "FM",
                    0x82: "CW", 0x83: "CWR", 0x84: "AM", 0x88: "FM"}


class FT847:
    """Yaesu FT-847: CAT de 5 bytes (8N2) com modo SAT nativo (RX e TX full duplex em bandas diferentes).

    CAT ON (00) antes de qualquer comando. RX e TX no mesmo rádio: SAT ON (4E), downlink pelos comandos SAT RX
    (11 frequência, 17 modo) e uplink pelos SAT TX (21, 27). Rádio só de RX ou só de TX: VFO principal (01, 07).
    Sem PTT. A frequência do uplink é atualizada também durante o TX (é o que o modo SAT faz).
    """
    name = "FT-847"

    def __init__(self, logger=None):
        self.ser = None
        self.log = logger or (lambda msg: None)
        self.same_rig = False
        self.sat_on = False

    @property
    def connected(self) -> bool:
        return self.ser is not None

    def use_same_rig(self, on: bool):
        self.same_rig = bool(on)

    def connect(self, port: str, baud: int = 57600, serial_factory=None):
        if serial_factory is None:
            import serial
            serial_factory = lambda: serial.Serial(port, baudrate=int(baud), bytesize=8, parity="N",
                                                   stopbits=2, timeout=0.5, write_timeout=0.5)
        self.ser = serial_factory()
        try:
            self._cmd(b"\x00\x00\x00\x00\x00")   # CAT ON
            self.read_frequency()
        except Exception:
            self.disconnect()
            raise
        self.log(f"FT-847: conectado em {port} {baud} 8N2")

    def disconnect(self):
        if self.ser is not None:
            try:
                self._cmd(b"\x00\x00\x00\x00\x80")   # CAT OFF (o modo SAT fica como está)
            except Exception:
                pass
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser, self.sat_on = None, False

    def _cmd(self, data: bytes, reply: int = 0) -> bytes:
        if self.ser is None:
            raise ConnectionError("FT-847 desconectado")
        self.ser.reset_input_buffer()
        self.ser.write(data)
        if not reply:
            time.sleep(0.02)
            return b""
        answer = self.ser.read(reply)
        if len(answer) != reply:
            raise TimeoutError("FT-847 não respondeu ao CAT (CAT ligado no menu? 8N2, 4800/9600/57600)")
        return answer

    def read_frequency(self, op: int = 0x03) -> tuple[int, str]:
        data = self._cmd(bytes([0, 0, 0, 0, op]), 5)
        return parse_bcd_frequency(data), FT847_MODE_NAMES.get(data[4], f"0x{data[4]:02X}")

    def is_transmitting(self) -> Optional[bool]:
        return None   # no modo SAT o uplink acompanha o Doppler durante o TX

    def _set(self, hz: int, mode: str, freq_op: int, mode_op: int):
        self._cmd(bcd_frequency(hz) + bytes([freq_op]))
        code = FT847_MODES.get(normalize_mode(mode), FT847_MODES["FM"])
        self._cmd(bytes([code, 0, 0, 0, mode_op]))

    def _ensure_sat(self):
        if not self.sat_on:
            self._cmd(b"\x00\x00\x00\x00\x4E")   # SAT ON
            self.sat_on = True
            self.log("FT-847: modo SAT ligado (RX = SAT RX, TX = SAT TX)")

    def set_rx(self, hz: int, mode: str):
        if self.same_rig:
            self._ensure_sat()
            self._set(hz, mode, 0x11, 0x17)
        else:
            self._set(hz, mode, 0x01, 0x07)
        return True

    def set_tx(self, hz: int, mode: str, same_rig_rx: bool = False):
        if same_rig_rx or self.same_rig:
            self._ensure_sat()
            self._set(hz, mode, 0x21, 0x27)
        else:
            self._set(hz, mode, 0x01, 0x07)
        return True


# Yaesu CAT texto (FT-991/991A, FTDX10, FTDX101, FT-710, FT-891): FA/FB com 9 dígitos, MD0x, TX;
YAESU_TEXT_MODES = {"LSB": "1", "USB": "2", "CW": "3", "FM": "4", "AM": "5", "PKT": "C", "DIG": "C"}
YAESU_TEXT_MODE_NAMES = {"1": "LSB", "2": "USB", "3": "CW", "4": "FM", "5": "AM", "6": "RTTY", "7": "CW",
                         "8": "DATA-L", "9": "RTTY", "A": "DATA-FM", "B": "FM-N", "C": "DATA-U", "D": "AM-N",
                         "E": "C4FM"}


class YaesuText:
    """Yaesu CAT texto (FT-991/991A e família). Sem PTT.

    RX ou TX isolado: VFO-A (FA, MD0). RX e TX no mesmo rádio: RX no VFO-A e TX no VFO-B (FB); o modo do VFO-B
    é ajustado trocando A/B (SV) só fora de transmissão e só quando o modo muda. O SPLIT é ligado no rádio
    pelo operador (tecla SPLIT): nos rádios desta família o comando de split varia de modelo para modelo.
    """
    name = "Yaesu CAT texto"

    def __init__(self, logger=None):
        self.ser = None
        self.log = logger or (lambda msg: None)
        self.same_rig = False
        self.tx_mode = None

    @property
    def connected(self) -> bool:
        return self.ser is not None

    def use_same_rig(self, on: bool):
        self.same_rig = bool(on)

    def connect(self, port: str, baud: int = 38400, serial_factory=None):
        if serial_factory is None:
            import serial
            serial_factory = lambda: serial.Serial(port, baudrate=int(baud), bytesize=8, parity="N",
                                                   stopbits=1, timeout=0.4, write_timeout=0.5)
        self.ser = serial_factory()
        try:
            self.read_frequency()
            rid = self._query("ID;")
            self.name = {"0570": "FT-991", "0670": "FT-991A", "0761": "FTDX10", "0681": "FTDX101D",
                         "0682": "FTDX101MP", "0800": "FT-710", "0650": "FT-891"}.get(rid[2:6], "Yaesu CAT texto")
        except Exception:
            self.disconnect()
            raise
        self.log(f"Yaesu: {self.name} conectado em {port} {baud} 8N1")

    def disconnect(self):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser, self.tx_mode = None, None

    def _write(self, text: str):
        if self.ser is None:
            raise ConnectionError("Yaesu desconectado")
        self.ser.write(text.encode("ascii"))
        time.sleep(0.02)

    def _query(self, text: str) -> str:
        if self.ser is None:
            raise ConnectionError("Yaesu desconectado")
        self.ser.reset_input_buffer()
        self.ser.write(text.encode("ascii"))
        data = b""
        deadline = time.monotonic() + 1.0
        while not data.endswith(b";") and time.monotonic() < deadline:
            chunk = self.ser.read(1)
            if chunk:
                data += chunk
        answer = data.decode("ascii", "replace")
        if not answer.endswith(";") or answer == "?;":
            raise TimeoutError(f"Yaesu não respondeu a {text} (CAT RATE/porta no menu do rádio?)")
        return answer

    def read_frequency(self) -> tuple[int, str]:
        fa = self._query("FA;")
        hz = int(fa[2:-1])
        mode = "?"
        try:
            md = self._query("MD0;")
            mode = YAESU_TEXT_MODE_NAMES.get(md[3:4], md[3:4])
        except (TimeoutError, ValueError):
            pass
        return hz, mode

    def is_transmitting(self) -> Optional[bool]:
        try:
            return self._query("TX;")[2:3] in ("1", "2")
        except Exception:
            return None

    @staticmethod
    def _mode_code(mode: str) -> str:
        return YAESU_TEXT_MODES.get(normalize_mode(mode), YAESU_TEXT_MODES["FM"])

    def set_rx(self, hz: int, mode: str):
        if self.is_transmitting():
            return False
        self._write(f"FA{int(hz):09d};MD0{self._mode_code(mode)};")
        return True

    def set_tx(self, hz: int, mode: str, same_rig_rx: bool = False):
        if self.is_transmitting():
            return False
        if not (same_rig_rx or self.same_rig):
            self._write(f"FA{int(hz):09d};MD0{self._mode_code(mode)};")
            return True
        self._write(f"FB{int(hz):09d};")
        code = self._mode_code(mode)
        if code != self.tx_mode:
            self._write(f"SV;MD0{code};SV;")   # modo do VFO-B: troca A/B, ajusta, destroca
            self.tx_mode = code
        return True


KENWOOD_MODES = {"LSB": "1", "USB": "2", "CW": "3", "FM": "4", "AM": "5", "PKT": "2"}


class KenwoodText:
    """Kenwood CAT em texto (FA/FB/MD/FR/FT/IF), para rádios sem o modo SAT do TS-2000.

    Split: RX no VFO A (FR0) e TX no VFO B (FT1). Nunca envia TX;/RX; (sem PTT).
    """
    name = "Kenwood"

    def __init__(self, logger=None):
        self.ser = None
        self.log = logger or (lambda msg: None)
        self.split = False
        self.model = ""

    @property
    def connected(self) -> bool:
        return self.ser is not None

    def connect(self, port: str, baud: int = 9600, serial_factory=None):
        if serial_factory is None:
            import serial
            serial_factory = lambda: serial.Serial(port, baudrate=int(baud), bytesize=8, parity="N",
                                                   stopbits=1, timeout=0.3, write_timeout=0.5)
        self.ser = serial_factory()
        try:
            ident = self._query("ID;", "ID")
            self.model = {"ID019;": "TS-2000", "ID020;": "TS-480", "ID021;": "TS-590S", "ID023;": "TS-590SG",
                          "ID024;": "TS-990", "ID017;": "TS-570", "ID022;": "TS-990"}.get(ident, ident.strip(";"))
            self.read_frequency()
        except Exception:
            self.disconnect()
            raise
        self.name = f"Kenwood {self.model}"
        self.log(f"Kenwood: {self.model} conectado em {port} {baud}")

    def disconnect(self):
        if self.ser is not None:
            try:
                if self.split:
                    self._write("FR0;FT0;")
            except Exception:
                pass
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser, self.split = None, False

    def _write(self, command: str):
        if self.ser is None:
            raise ConnectionError("Kenwood desconectado")
        self.ser.write(command.encode("ascii"))
        self.log("TX " + command)

    def _query(self, command: str, prefix: str, timeout: float = 1.5) -> str:
        if self.ser is None:
            raise ConnectionError("Kenwood desconectado")
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass
        self._write(command)
        pending, deadline = "", time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = self.ser.read(64).decode("ascii", "replace")
            pending += chunk
            while ";" in pending:
                frame, pending = pending.split(";", 1)
                if frame.startswith(prefix):
                    return frame + ";"
            if len(pending) > 256:
                pending = ""
        raise TimeoutError(f"Kenwood não respondeu a {command}")

    def read_frequency(self) -> tuple[int, str]:
        fa = self._query("FA;", "FA")
        hz = int(fa[2:-1])
        mode = "?"
        try:
            md = self._query("MD;", "MD")
            mode = {v: k for k, v in KENWOOD_MODES.items() if k != "PKT"}.get(md[2:3], "?")
        except (TimeoutError, ValueError):
            pass
        return hz, mode

    def is_transmitting(self) -> Optional[bool]:
        try:
            answer = self._query("IF;", "IF", timeout=0.6)
        except Exception:
            return None
        body = answer[2:-1]
        return len(body) >= 27 and body[26] == "1"

    def _set(self, vfo: str, hz: int, mode: str):
        if not 30_000 <= hz <= 99_999_999_999:
            raise ValueError("Frequência fora da faixa do CAT Kenwood")
        self._write(f"{vfo}{int(hz):011d};")
        self._write("MD" + KENWOOD_MODES.get(normalize_mode(mode), "4") + ";")

    def set_rx(self, hz: int, mode: str):
        if self.is_transmitting():
            return False
        self._set("FA", hz, mode)
        return True

    def set_tx(self, hz: int, mode: str, same_rig_rx: bool = False):
        if self.is_transmitting():
            return False
        if not same_rig_rx:
            self._set("FA", hz, mode)
            return True
        if not self.split:
            self._write("FR0;FT1;")   # RX no VFO A, TX no VFO B
            self.split = True
        if not 30_000 <= hz <= 99_999_999_999:
            raise ValueError("Frequência fora da faixa do CAT Kenwood")
        self._write(f"FB{int(hz):011d};")   # o modo do TX segue o do VFO A (MD vale para o VFO em uso)
        return True


class Rigctld:
    """Cliente do protocolo de rede do Hamlib (rigctld, SDR++, gqrx)."""
    name = "rigctld"

    def __init__(self, logger=None):
        self.sock: Optional[socket.socket] = None
        self.log = logger or (lambda msg: None)
        self.split = False
        self._buf = b""

    @property
    def connected(self) -> bool:
        return self.sock is not None

    def connect(self, host: str = "127.0.0.1", port: int = 4532, sock_factory=None):
        self.sock = sock_factory() if sock_factory else socket.create_connection((host, int(port)), timeout=2)
        self.sock.settimeout(2)
        self.query("f")
        self.log(f"rigctld: conectado a {host}:{port}")

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock, self.split = None, False

    def query(self, command: str) -> str:
        if self.sock is None:
            raise ConnectionError("rigctld desconectado")
        self.sock.sendall((command + "\n").encode("ascii"))
        while b"\n" not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("rigctld encerrou a conexão")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        text = line.decode("ascii", "replace").strip()
        if text.startswith("RPRT") and text != "RPRT 0":
            raise RuntimeError(f"rigctld recusou '{command}': {text}")
        return text

    def is_transmitting(self) -> Optional[bool]:
        try:
            return self.query("t").strip() == "1"
        except Exception:
            return None

    @staticmethod
    def _passband(mode: str) -> int:
        return {"FM": 15000, "CW": 500, "AM": 6000}.get(mode, 2400)

    def set_rx(self, hz: int, mode: str):
        m = HAMLIB_MODES.get(normalize_mode(mode), "FM")
        self.query(f"F {int(hz)}")
        self.query(f"M {m} {self._passband(normalize_mode(mode))}")
        return True

    def set_tx(self, hz: int, mode: str, same_rig_rx: bool = False):
        if self.is_transmitting():
            return False
        m = HAMLIB_MODES.get(normalize_mode(mode), "FM")
        if not same_rig_rx:
            self.query(f"F {int(hz)}")
            self.query(f"M {m} {self._passband(normalize_mode(mode))}")
            return True
        if not self.split:
            self.query("S 1 VFOB")
            self.split = True
        self.query(f"I {int(hz)}")
        self.query(f"X {m} {self._passband(normalize_mode(mode))}")
        return True


class DopplerDispatcher:
    """Envia RX/TX corrigidos aos equipamentos escolhidos, com limiar e intervalo mínimo."""

    def __init__(self, threshold_hz: int = 10, min_interval_s: float = 0.5):
        self.threshold_hz = threshold_hz
        self.min_interval_s = min_interval_s
        self._sent: dict[str, tuple[int, str, float]] = {}

    def due(self, key: str, hz: int, mode: str, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        last = self._sent.get(key)
        if last is None or last[1] != mode:
            return True
        return abs(hz - last[0]) >= self.threshold_hz and now - last[2] >= self.min_interval_s

    def mark(self, key: str, hz: int, mode: str, now: Optional[float] = None):
        self._sent[key] = (int(hz), mode, time.monotonic() if now is None else now)

    def reset(self):
        self._sent.clear()
