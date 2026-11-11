"""Conservative Kenwood TS-2000 CAT interface: never sends PTT.

Kenwood TS-2000 manual, appendix p.135: in SA satellite mode FA controls
satellite downlink and FB controls satellite uplink. FC is the independent
SUB receiver VFO and MUST NOT be treated as SAT uplink by the CAT driver.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import threading
import time

MODES = {"LSB": "1", "USB": "2", "CW": "3", "FM": "4", "AM": "5", "FSK": "6", "CW-R": "7", "FSK-R": "9"}
MODES_REV = {v: k for k, v in MODES.items()}


def available_ports():
    from serial.tools import list_ports
    return [port.device for port in list_ports.comports()]


def frequency_command(channel: str, freq_hz: int) -> str:
    if channel not in ("FA", "FB", "FC"):
        raise ValueError("Somente FA (VFO A), FB (VFO B) e FC (SUB) são permitidos")
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



def parse_extra(name: str, answer: str):
    """Valores de leitura do TS-2000 para o display (v1.6.0). Formatos do manual de comandos PC."""
    body=answer.rstrip(";")
    if name=="af_gain":      # AG P1(0/1) P2(000-255)
        return int(body[3:6])
    if name=="rf_gain":      # RG P1(000-255)
        return int(body[2:5])
    if name=="squelch":      # SQ P1(0/1) P2(000-255)
        return int(body[3:6])
    if name=="preamp":       # PA P1(0/1) [P2]
        return body[2:3]=="1"
    if name=="attenuator":   # RA P1P2(00/01) P3P4
        return body[2:4]!="00"
    if name in ("nb","nr"):  # NB0/1, NR0/1/2
        return int(body[2:3])
    if name=="if":           # IF: P8 (TX/RX) na posição 28
        if len(body)<29:
            raise ValueError("IF curto")
        return {"tx":body[28]=="1"}
    raise ValueError(name)


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
    vfo_b: int | None = None  # SAT uplink when SA P1=1 and P3=1
    sub_receiver: int | None = None  # FC is not the SAT uplink register
    mode: str = "?"
    sat_raw: str = ""
    signal_main: int | None = None
    signal_sub: int | None = None
    power_set_w: int | None = None
    meter_type: str = ""
    meter_value: int | None = None
    main_downlink: bool = True
    extras: dict = field(default_factory=dict)  # v1.6.0: AG/RG/SQ/PA/RA/NB/NR/IF (leitura)


class TS2000:
    def __init__(self, logger=None):
        self.port = None
        self.logger = logger or (lambda x: None)
        self.lock = threading.RLock()
        self.state = RadioState()
        self._last_optional_poll = 0.0
        self.main_downlink_expected = True  # v1.6.0: botão MAIN↔SUB

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
            # pyserial.read_until() may return *partial bytes* at timeout.
            # Real TS-2000 COM1 logs show RX "F" followed by "A00...;" and
            # RX "M" followed by "D4;". Each part is a transport fragment,
            # not an independent CAT frame. Reassemble until ';', bounded
            # by a wall-clock deadline and a maximum response size.
            #
            # Do not resend a command here: automatic retries of FA/FB/MD
            # writes could override an operator's dial adjustment.
            deadline = time.monotonic() + 4.0
            pending = ""
            reads = 0
            while time.monotonic() < deadline and reads < 48:
                reads += 1
                chunk = self.port.read_until(b";").decode("ascii", errors="replace")
                if not chunk:
                    continue
                self.logger("RX " + chunk)
                pending += chunk
                if len(pending) > 256:
                    raise TimeoutError(
                        f"Resposta CAT excessiva sem enquadramento para {expected}")
                while ";" in pending:
                    raw_frame, pending = pending.split(";", 1)
                    frame = raw_frame + ";"
                    if frame.startswith(expected):
                        return frame
                    # Replies '?' and unsolicited/nonmatching frames do
                    # not invalidate a subsequent complete matching reply.
            suffix = f" (parcial {pending!r})" if pending else ""
            raise TimeoutError(f"Sem resposta CAT completa para {expected}{suffix}")

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
            fb=self._exchange("FB;","FB")  # dedicated SAT uplink (Kenwood SA manual)
            fc=self._exchange("FC;","FC")  # SUB receiver VFO, diagnostic only
            md=self._exchange("MD;","MD")
            self.state.sat_raw=sa
            self.state.sat=decode_satellite_status(sa)["sat"]
            self.state.downlink=parse_frequency(fa,"FA")
            self.state.vfo_b=parse_frequency(fb,"FB")
            self.state.sub_receiver=parse_frequency(fc,"FC")
            self.state.uplink=self.state.vfo_b if self.state.sat else None
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

    def poll_telemetry(self):
        """Read current TS-2000 control/meter state without touching VFOs/PTT.

        The CAT Doppler worker already reads SA/FA/FB at a much faster cadence.
        These supplementary commands run on a separate, throttled read-only
        worker, serialized under the same COM-port lock.
        """
        with self.lock:
            sa=self._exchange("SA;","SA")
            md=self._exchange("MD;","MD")
            fc=self._exchange("FC;","FC")
            self.state.sat_raw=sa
            self.state.sat=decode_satellite_status(sa)["sat"]
            self.state.mode=MODES_REV.get(md[2:3],"?")
            self.state.sub_receiver=parse_frequency(fc,"FC")
            for command,expected,receiver,attr in (
                ("SM0;","SM0",0,"signal_main"),
                ("SM1;","SM1",1,"signal_sub")):
                try:
                    setattr(self.state,attr,parse_smeter(self._exchange(command,expected),receiver))
                except (TimeoutError,ValueError,ConnectionError) as exc:
                    setattr(self.state,attr,None)
                    self.logger(f"CAT S-meter {command}: {exc}")
            if time.monotonic()-self._last_optional_poll>=6:
                self._last_optional_poll=time.monotonic()
                for command,expected,parser,attr in (
                    ("PC;","PC",parse_power_setting,"power_set_w"),
                    ("RM;","RM",parse_meter,"meter")):
                    try:
                        val=parser(self._exchange(command,expected))
                        if attr=="meter":
                            self.state.meter_type,self.state.meter_value=val
                        else:
                            setattr(self.state,attr,val)
                    except (TimeoutError,ValueError,ConnectionError) as exc:
                        if attr=="meter":
                            self.state.meter_type="";self.state.meter_value=None
                        else:
                            setattr(self.state,attr,None)
                        self.logger(f"CAT leitura opcional {command}: {exc}")
                # v1.6.0: parâmetros extras para o display (somente leitura, baixa prioridade).
                extras={}
                for command,expected,name in (("AG0;","AG","af_gain"),("RG;","RG","rf_gain"),("SQ0;","SQ","squelch"),
                                              ("PA;","PA","preamp"),("RA;","RA","attenuator"),("NB;","NB","nb"),
                                              ("NR;","NR","nr"),("IF;","IF","if")):
                    try:
                        answer=self._exchange(command,expected)
                        extras[name]=parse_extra(name,answer)
                    except (TimeoutError,ValueError,ConnectionError):
                        extras[name]=None
                self.state.extras=extras
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
            for code in ("ID","SA","FA","FB","FC","MD"):
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
        for key in ("FA","FB","FC"):
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
                "frequency_hz":frequency,"main_mode":mode,
                "sat_uplink_hz":frequency.get("FB") if status.get("sat") else None,
                "sub_receiver_hz":frequency.get("FC")}

    def enable_satellite_mode(self):
        sa = self._exchange("SA;", "SA")
        self._exchange(satellite_mode_command(sa))
        state = self.poll()
        if not state.sat:
            raise RuntimeError("Não foi possível confirmar o modo SAT")
        return state

    def poll_tracking(self):
        """Low-latency live SAT readback; no FC/MD/meters in Doppler loop.

        SA/FA/FB provide real radio state. Full telemetry remains available via
        poll(), but it should not monopolize the COM port between live writes.
        """
        with self.lock:
            sa=self._exchange("SA;","SA")
            fa=self._exchange("FA;","FA")
            fb=self._exchange("FB;","FB")
            self.state.sat_raw=sa
            status=decode_satellite_status(sa)
            self.state.sat=status["sat"]
            fa_hz,fb_hz=parse_frequency(fa,"FA"),parse_frequency(fb,"FB")
            self.state.main_downlink=status["main_downlink"]
            if self.state.sat and not status["main_downlink"]:
                # v1.6.0: MAIN TX / SUB RX (botão MAIN↔SUB): papéis de FA/FB invertidos.
                self.state.downlink,self.state.vfo_b,self.state.uplink=fb_hz,fb_hz,fa_hz
            else:
                self.state.downlink=fa_hz
                self.state.vfo_b=fb_hz
                self.state.uplink=self.state.vfo_b if self.state.sat else None
            return self.state

    def set_frequencies(self, uplink_hz: int, downlink_hz: int):
        """Write VFOs only after SAT status is validated, then verify FA/FB fast."""
        with self.lock:
            sa=self._exchange("SA;","SA")
            status=decode_satellite_status(sa)
            if not status["sat"]:
                raise RuntimeError("Ative SAT no rádio antes de alterar as frequências")
            if status["main_downlink"]!=self.main_downlink_expected:
                raise RuntimeError("A orientação MAIN/SUB do rádio difere da selecionada no programa")
            # Never key TX/PTT. Confirm with short readback, not full SM/RM/FC poll.
            rx_vfo,tx_vfo=("FA","FB") if self.main_downlink_expected else ("FB","FA")
            self._exchange(frequency_command(rx_vfo,downlink_hz))
            self._exchange(frequency_command(tx_vfo,uplink_hz))
            state=self.poll_tracking()
            if state.downlink!=downlink_hz or state.uplink!=uplink_hz:
                raise RuntimeError(
                    f"TS-2000 não confirmou CAT: RX esperado {downlink_hz}, real {state.downlink}; "
                    f"TX esperado {uplink_hz}, real {state.uplink}")
            return state

    def set_satellite_channel(self,downlink_hz:int,uplink_hz:int|None,rx_mode:str):
        """Operator-authorized SAT preset: FA=SAT downlink, FB=SAT uplink, MD=MAIN.
        
        The SUB TX demodulation mode is not silently guessed: TS-2000 CAT MD
        operates MAIN only in this driver. Never send PTT/TX/RX commands.
        """
        if rx_mode not in MODES:
            raise ValueError("Modo RX não suportado pelo driver CAT")
        frequency_command("FA",downlink_hz)
        if uplink_hz is not None:frequency_command("FB",uplink_hz)
        with self.lock:
            sa=self._exchange("SA;","SA")
            want="1" if self.main_downlink_expected else "0"
            if not sa.startswith("SA1") or len(sa)<6 or sa[4]!=want:
                raise RuntimeError("Ative SAT com MAIN=RX e SUB=TX antes do Auto CAT" if want=="1" else
                                   "Ative SAT com MAIN=TX e SUB=RX (MAIN↔SUB invertido) antes do Auto CAT")
            if sa[5]!="0":
                raise RuntimeError("CTRL está na SUB; selecione CTRL MAIN para alterar o modo de RX")
            rx_vfo,tx_vfo=("FA","FB") if want=="1" else ("FB","FA")
            self._exchange(frequency_command(rx_vfo,downlink_hz))
            if uplink_hz is not None:
                self._exchange(frequency_command(tx_vfo,uplink_hz))
            self._exchange("MD"+MODES[rx_mode]+";")
            st=self.poll()
            if st.downlink!=downlink_hz or (uplink_hz is not None and st.uplink!=uplink_hz):
                raise RuntimeError("Rádio não confirmou as frequências")
            if st.mode!=rx_mode:
                raise RuntimeError("Rádio não confirmou o modo de recepção")
            return st

    def set_orientation(self, main_downlink: bool, settle_s: float = 0.35, attempts: int = 6):
        """MAIN↔SUB no TS-2000 (SA P3: 1 = MAIN RX/SUB TX, 0 = MAIN TX/SUB RX). Só com SAT ON; sem PTT.

        v1.7.0: o rádio leva alguns centésimos para reconfigurar as bandas; a leitura SA é repetida
        (até ~2 s) antes de declarar falha, e a mensagem diz o que foi lido de volta.
        """
        with self.lock:
            sa=self._exchange("SA;","SA")
            status=decode_satellite_status(sa)
            if not status["sat"]:
                raise RuntimeError("Ative SAT no rádio antes de inverter MAIN/SUB")
            if status["main_downlink"]==bool(main_downlink):
                self.main_downlink_expected=bool(main_downlink)
                self.state.main_downlink=bool(main_downlink)
                return self.state
            p=sa[2:9]
            command=f"SA{p[0]}{p[1]}{'1' if main_downlink else '0'}{p[3:7]};"
            self._exchange(command)
            check=status
            for _ in range(max(1,attempts)):
                if settle_s:
                    time.sleep(settle_s)
                check=decode_satellite_status(self._exchange("SA;","SA"))
                if check["main_downlink"]==bool(main_downlink):
                    break
            if check["main_downlink"]!=bool(main_downlink):
                raise RuntimeError("O TS-2000 não aceitou a inversão MAIN/SUB pelo CAT (SA lido: "+check["raw"]+
                                   "). Faça a troca no painel do rádio: o programa acompanha a orientação lida.")
            self.main_downlink_expected=bool(main_downlink)
            self.state.main_downlink=bool(main_downlink)
            return self.state

    def set_rx_only(self, downlink_hz: int, mode: str | None = None):
        """v1.6.0 Somente RX: escreve só o VFO de recepção (FA com SAT OFF; o VFO de RX com SAT ON).

        Nunca escreve o uplink, nunca liga SAT e nunca aciona PTT. Confirma por readback.
        """
        with self.lock:
            sa=self._exchange("SA;","SA")
            status=decode_satellite_status(sa)
            vfo="FA" if (not status["sat"] or status["main_downlink"]) else "FB"
            self._exchange(frequency_command(vfo,downlink_hz))
            if mode in MODES and (not status["sat"] or not status["ctrl_sub"]):
                self._exchange("MD"+MODES[mode]+";")
            got=parse_frequency(self._exchange(vfo+";",vfo),vfo)
            if got!=downlink_hz:
                raise RuntimeError(f"TS-2000 não confirmou RX: esperado {downlink_hz}, real {got}")
            self.state.sat=status["sat"]
            self.state.downlink=got
            return self.state

    def set_main_mode(self, mode: str):
        if mode not in MODES:
            raise ValueError("Modo CAT não suportado")
        if not self.poll().sat:
            raise RuntimeError("Ative SAT primeiro")
        self._exchange("MD" + MODES[mode] + ";")
        return self.poll()


_PORT_MISSING_MARKERS = ("file not found", "filenotfound", "could not open port", "cannot find",
                         "no such file", "não foi possível encontrar", "the system cannot find",
                         "o sistema não pode encontrar", "errno 2")
_PORT_BUSY_MARKERS = ("access is denied", "acesso negado", "permissionerror", "errno 13", "resource busy",
                      "device or resource busy", "permission denied")


def classify_port_error(message: str) -> str:
    """'missing' (porta não existe), 'busy' (em uso/sem permissão) ou 'other'. v1.7.1."""
    text = str(message or "").casefold()
    if any(m in text for m in _PORT_BUSY_MARKERS):
        return "busy"
    if any(m in text for m in _PORT_MISSING_MARKERS):
        return "missing"
    return "other"


def port_error_text(message: str, port: str = "") -> tuple:
    """(resumo curto, orientação) para falha ao abrir a porta CAT, sem confundir com sintonia bloqueada."""
    where = f" ({port})" if port else ""
    kind = classify_port_error(message)
    if kind == "missing":
        return (f"Porta CAT indisponível{where}",
                "A porta não existe neste computador agora. Confira se o cabo USB/serial está ligado, "
                "se o driver da interface está instalado e qual COM o Windows atribuiu (Gerenciador de "
                "Dispositivos), e escolha a porta certa em Configurações → Rádio.")
    if kind == "busy":
        return (f"Porta CAT em uso{where}",
                "Outro programa (ex.: HRD, WSJT-X, Omni-Rig, Flrig) está com a porta aberta, ou falta "
                "permissão. Feche o outro programa ou use um splitter de COM e tente de novo.")
    return (f"Falha de conexão CAT{where}",
            "A porta abriu, mas o rádio não respondeu como esperado. Confira velocidade, modelo e cabo em "
            "Configurações → Rádio e veja LOGs / CAT.")
