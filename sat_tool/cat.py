"""Conservative Kenwood TS-2000 CAT interface: never sends PTT."""
from __future__ import annotations
from dataclasses import dataclass
import threading

MODES = {"LSB": "1", "USB": "2", "CW": "3", "FM": "4", "AM": "5", "FSK": "6", "CW-R": "7", "FSK-R": "9"}
MODES_REV = {v: k for k, v in MODES.items()}


def available_ports():
    from serial.tools import list_ports
    return [port.device for port in list_ports.comports()]


def frequency_command(channel: str, freq_hz: int) -> str:
    if channel not in ("FA", "FB"):
        raise ValueError("Somente FA (downlink) e FB (uplink) são permitidos")
    if not 100000 <= freq_hz <= 1_299_999_999:
        raise ValueError("Frequência CAT fora do intervalo seguro")
    return f"{channel}{int(freq_hz):011d};"


def parse_frequency(answer: str, channel: str) -> int:
    prefix = channel
    if not answer.startswith(prefix) or not answer.endswith(";"):
        raise ValueError(f"Resposta inesperada para {channel}: {answer!r}")
    digits = answer[2:-1]
    if len(digits) != 11 or not digits.isdigit():
        raise ValueError(f"Resposta CAT inválida: {answer!r}")
    return int(digits)


def satellite_mode_command(answer: str) -> str:
    """Preserve memory channel; select main RX/sub TX; turn off radio TRACE.

    SAT command P1-P7, see TS-2000 PC commands p.135. P5 in manual has a
    typographical inconsistency; setting 0 avoids dual autonomous tracking.
    """
    if not answer.startswith("SA") or len(answer) < 9:
        raise ValueError("Não foi possível ler SA; do TS-2000")
    p = answer[2:9]
    if len(p) != 7 or not p[:2].isdigit():
        raise ValueError("Resposta SA inválida")
    return f"SA1{p[1]}10000;"


@dataclass
class RadioState:
    connected: bool = False
    model: str = ""
    sat: bool = False
    downlink: int | None = None
    uplink: int | None = None
    mode: str = "?"
    sat_raw: str = ""


class TS2000:
    def __init__(self, logger=None):
        self.port = None
        self.logger = logger or (lambda x: None)
        self.lock = threading.RLock()
        self.state = RadioState()

    @property
    def connected(self):
        return self.port is not None and self.port.is_open

    def _exchange(self, command: str, expected: str | None = None) -> str:
        with self.lock:
            if not self.connected:
                raise ConnectionError("TS-2000 desconectado")
            if not command.endswith(";") or not command[:2].isalpha():
                raise ValueError("Comando CAT malformado")
            self.port.reset_input_buffer()
            self.port.write(command.encode("ascii"))
            self.port.flush()
            self.logger("TX " + command)
            if expected is None:
                return ""
            for _ in range(3):
                answer = self.port.read_until(b";").decode("ascii", errors="replace")
                self.logger("RX " + answer)
                if answer.startswith(expected) and answer.endswith(";"):
                    return answer
            raise TimeoutError(f"Sem resposta válida do CAT para {expected}")

    def connect(self, port: str, baud: int = 9600, stopbits: int = 1):
        self.disconnect()
        import serial
        self.port = serial.Serial(port, baudrate=baud, bytesize=8, parity='N',
                                  stopbits=stopbits, timeout=0.35, write_timeout=0.75)
        try:
            identity = self._exchange("ID;", "ID")
            if identity != "ID019;":
                raise ConnectionError(f"Resposta de rádio não reconhecido: {identity}")
            self.state = RadioState(connected=True, model="Kenwood TS-2000")
            self.poll()
            return self.state
        except Exception:
            self.disconnect()
            raise

    def disconnect(self):
        with self.lock:
            if self.port is not None:
                self.port.close()
            self.port = None
            self.state = RadioState()

    def poll(self):
        sa = self._exchange("SA;", "SA")
        fa = self._exchange("FA;", "FA")
        fb = self._exchange("FB;", "FB")
        md = self._exchange("MD;", "MD")
        self.state.sat_raw = sa
        self.state.sat = sa.startswith("SA1")
        self.state.downlink = parse_frequency(fa, "FA")
        self.state.uplink = parse_frequency(fb, "FB")
        self.state.mode = MODES_REV.get(md[2:3], "?")
        return self.state

    def enable_satellite_mode(self):
        sa = self._exchange("SA;", "SA")
        self._exchange(satellite_mode_command(sa))
        state = self.poll()
        if not state.sat:
            raise RuntimeError("Não foi possível confirmar o modo SAT")
        return state

    def set_frequencies(self, uplink_hz: int, downlink_hz: int):
        sa = self._exchange("SA;", "SA")
        if not sa.startswith("SA1"):
            raise RuntimeError("Ative SAT no rádio antes de alterar as frequências")
        if len(sa) < 5 or sa[4] != "1":
            raise RuntimeError("A seleção MAIN RX / SUB TX não está configurada")
        # Radio handles actual RF PTT, never sent here.
        self._exchange(frequency_command("FA", downlink_hz))
        self._exchange(frequency_command("FB", uplink_hz))
        return self.poll()

    def set_main_mode(self, mode: str):
        if mode not in MODES:
            raise ValueError("Modo CAT não suportado")
        if not self.poll().sat:
            raise RuntimeError("Ative SAT primeiro")
        self._exchange("MD" + MODES[mode] + ";")
        return self.poll()
