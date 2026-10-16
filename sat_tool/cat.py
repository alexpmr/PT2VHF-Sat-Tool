"""Conservative Kenwood TS-2000 CAT interface: never sends PTT."""
from __future__ import annotations
from dataclasses import dataclass
import threading
import time

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


def decode_satellite_status(answer: str) -> dict:
    """Decode the Kenwood SA response without changing the radio.

    P1: SAT, P2: channel, P3: MAIN/SUB orientation, P4: CTRL,
    P5/P6: TRACE, P7: VFO/memory. P8 (name) is optional for
    diagnostic parsing so older firmware can still be inspected.
    """
    if not answer.startswith("SA") or not answer.endswith(";") or len(answer) < 10:
        raise ValueError("Resposta SA inválida: "+repr(answer))
    values=answer[2:9]
    if len(values)!=7 or not values.isdigit() or values[0] not in "01" or values[2] not in "01":
        raise ValueError("Parâmetros SA inválidos: "+repr(answer))
    return {
        "sat": values[0]=="1",
        "channel": int(values[1]),
        "main_downlink": values[2]=="1",
        "ctrl_sub": values[3]=="1",
        "trace": values[4]=="1",
        "trace_reverse": values[5]=="1",
        "memory_mode": values[6]=="1",
        "raw": answer,
    }


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



def parse_smeter(answer: str, receiver: int) -> int:
    """SM0/SM1 reports 4 digits, scaled 0-30 MAIN, 0-15 SUB."""
    prefix=f"SM{receiver}"
    if receiver not in (0,1) or not answer.startswith(prefix) or not answer.endswith(";"):
        raise ValueError("Resposta de S-meter inválida")
    digits=answer[3:-1]
    limit=30 if receiver==0 else 15
    if len(digits)!=4 or not digits.isdigit() or int(digits)>limit:
        raise ValueError("S-meter fora da escala do TS-2000")
    return int(digits)


def parse_power_setting(answer:str) -> int:
    if not answer.startswith("PC") or not answer.endswith(";") or len(answer)!=6:
        raise ValueError("Resposta PC inválida")
    digits=answer[2:5]
    if not digits.isdigit() or not 0<=int(digits)<=100:
        raise ValueError("Potência configurada inválida")
    return int(digits)


def parse_meter(answer:str):
    if not answer.startswith("RM") or not answer.endswith(";") or len(answer)!=8:
        raise ValueError("Resposta RM inválida")
    scale=answer[2]
    value=answer[3:7]
    if scale not in "0123" or not value.isdigit() or int(value)>30:
        raise ValueError("Escala RM inválida")
    return {"0":"—","1":"SWR","2":"COMP","3":"ALC"}[scale],int(value)

@dataclass
class RadioState:
    connected: bool = False
    model: str = ""
    sat: bool = False
    downlink: int | None = None
    uplink: int | None = None
    mode: str = "?"
    sat_raw: str = ""
    signal_main: int | None = None
    signal_sub: int | None = None
    power_set_w: int | None = None
    meter_type: str = ""
    meter_value: int | None = None


class TS2000:
    def __init__(self, logger=None):
        self.port = None
        self.logger = logger or (lambda x: None)
        self.lock = threading.RLock()
        self.state = RadioState()
        self._last_optional_poll = 0.0

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
        with self.lock:
            sa=self._exchange("SA;","SA")
            fa=self._exchange("FA;","FA")
            fb=self._exchange("FB;","FB")
            md=self._exchange("MD;","MD")
            self.state.sat_raw=sa
            self.state.sat=sa.startswith("SA1")
            self.state.downlink=parse_frequency(fa,"FA")
            self.state.uplink=parse_frequency(fb,"FB")
            self.state.mode=MODES_REV.get(md[2:3],"?")
            # Optional meters run at most once every 5 seconds. Commands are read-only.
            if time.monotonic()-self._last_optional_poll>=5:
                self._last_optional_poll=time.monotonic()
                for command,expected,parse,attr in (
                    ("SM0;","SM0",lambda raw:parse_smeter(raw,0),"signal_main"),
                    ("SM1;","SM1",lambda raw:parse_smeter(raw,1),"signal_sub"),
                    ("PC;","PC",parse_power_setting,"power_set_w"),
                    ("RM;","RM",parse_meter,"meter")):
                    try:
                        value=parse(self._exchange(command,expected))
                        if attr=="meter":
                            self.state.meter_type,self.state.meter_value=value
                        else:setattr(self.state,attr,value)
                    except (TimeoutError,ValueError,ConnectionError) as exc:
                        if attr=="meter":
                            self.state.meter_type="";self.state.meter_value=None
                        else:setattr(self.state,attr,None)
                        self.logger(f"CAT leitura opcional {command}: {exc}")
            return self.state

    def read_diagnostics(self) -> dict:
        """Read-only probe: safe with SAT on; never writes VFO, SAT or PTT.

        Runs under the same serial lock as CAT polling and retuning. Return
        individual errors rather than losing all evidence on one timeout.
        """
        responses={}
        errors={}
        with self.lock:
            if not self.connected:
                raise ConnectionError("Conecte o TS-2000 antes de testar CAT")
            for code in ("ID","SA","FA","FB","MD"):
                try:
                    responses[code]=self._exchange(code+";",code)
                except (TimeoutError,ValueError,ConnectionError) as exc:
                    errors[code]=str(exc)
        status={}
        try:
            status=decode_satellite_status(responses["SA"])
        except (KeyError,ValueError) as exc:
            errors.setdefault("SA",str(exc))
        frequency={}
        for key in ("FA","FB"):
            try:
                frequency[key]=parse_frequency(responses[key],key)
            except (KeyError,ValueError) as exc:
                errors.setdefault(key,str(exc))
        mode=None
        if "MD" in responses:
            raw=responses["MD"]
            if len(raw)>=4 and raw.endswith(";"):
                mode=MODES_REV.get(raw[2:-1],"?")
            else:
                errors["MD"]="Resposta MD inválida: "+repr(raw)
        return {"raw":responses,"errors":errors,"sat":status,
                "frequency_hz":frequency,"main_mode":mode}

    def enable_satellite_mode(self):
        sa = self._exchange("SA;", "SA")
        self._exchange(satellite_mode_command(sa))
        state = self.poll()
        if not state.sat:
            raise RuntimeError("Não foi possível confirmar o modo SAT")
        return state

    def set_frequencies(self, uplink_hz: int, downlink_hz: int):
        with self.lock:
            sa=self._exchange("SA;","SA")
            if not sa.startswith("SA1"):
                raise RuntimeError("Ative SAT no rádio antes de alterar as frequências")
            if len(sa)<5 or sa[4]!="1":
                raise RuntimeError("A seleção MAIN RX / SUB TX não está configurada")
            self._exchange(frequency_command("FA",downlink_hz))
            self._exchange(frequency_command("FB",uplink_hz))
            state=self.poll()
            if state.downlink!=downlink_hz or state.uplink!=uplink_hz:
                raise RuntimeError("TS-2000 não confirmou as frequências por CAT")
            return state

    def set_satellite_channel(self,downlink_hz:int,uplink_hz:int|None,rx_mode:str):
        """Operator-authorized SAT preset: FA=RX, FB=TX when defined, MD=MAIN.
        
        The SUB TX demodulation mode is not silently guessed: TS-2000 CAT MD
        operates MAIN only in this driver. Never send PTT/TX/RX commands.
        """
        if rx_mode not in MODES:
            raise ValueError("Modo RX não suportado pelo driver CAT")
        frequency_command("FA",downlink_hz)
        if uplink_hz is not None:frequency_command("FB",uplink_hz)
        with self.lock:
            sa=self._exchange("SA;","SA")
            if not sa.startswith("SA1") or len(sa)<5 or sa[4]!="1":
                raise RuntimeError("Ative SAT com MAIN=RX e SUB=TX antes do Auto CAT")
            self._exchange(frequency_command("FA",downlink_hz))
            if uplink_hz is not None:
                self._exchange(frequency_command("FB",uplink_hz))
            self._exchange("MD"+MODES[rx_mode]+";")
            st=self.poll()
            if st.downlink!=downlink_hz or (uplink_hz is not None and st.uplink!=uplink_hz):
                raise RuntimeError("Rádio não confirmou as frequências")
            if st.mode!=rx_mode:
                raise RuntimeError("Rádio não confirmou o modo de recepção")
            return st

    def set_main_mode(self, mode: str):
        if mode not in MODES:
            raise ValueError("Modo CAT não suportado")
        if not self.poll().sat:
            raise RuntimeError("Ative SAT primeiro")
        self._exchange("MD" + MODES[mode] + ";")
        return self.poll()
