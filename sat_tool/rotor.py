"""Controle de rotor az/el pelo protocolo Yaesu GS-232A/B (v1.7.0).

Pensado para o Yaesu G-5400B ligado à interface ERC-M (DF9GR, Easy Rotor Control), que aparece
no computador como porta serial (USB) e emula o GS-232. Também serve para outros controladores
GS-232 (Yaesu GS-232A/B, ERC, K3NG etc.).

Segurança: nenhum movimento por simples seleção de satélite; o rastreamento só começa quando o
operador pede. PARAR ("S") é enviado em qualquer erro, perda de comunicação ou ao fechar o programa.
Toda escrita fica no log.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

POS_RE = re.compile(r"(?:AZ\s*=\s*|\+)(-?\d{1,4})\s*(?:EL\s*=\s*|\+)(-?\d{1,4})", re.I)


@dataclass
class RotorProfile:
    """Limites mecânicos e calibração. Padrão: G-5400B (azimute 450°, elevação 180°)."""
    name: str = "Yaesu G-5400B"
    az_max: float = 450.0        # 360 ou 450 (sobreposição após o norte)
    el_max: float = 180.0        # 90 ou 180 (G-5400B sobe até 180°)
    north_offset: float = 0.0    # correção do norte da antena (graus somados ao comando)
    park_az: float = 0.0
    park_el: float = 0.0
    tolerance: float = 4.0       # só move se o erro passar disto (motor lento, sem liga/desliga)
    min_interval_s: float = 2.0  # intervalo mínimo entre comandos de movimento
    min_el: float = 0.0          # máscara de horizonte do rotor


PROFILES = {
    "g5400b": RotorProfile(),
    "g5500": RotorProfile(name="Yaesu G-5500"),
    "az360_el90": RotorProfile(name="Genérico 360°/90°", az_max=360.0, el_max=90.0),
}


def parse_position(answer: str) -> tuple[float, float]:
    """'AZ=123  EL=045' (GS-232A) ou '+0123+0045' (GS-232B) → (123.0, 45.0)."""
    m = POS_RE.search(answer or "")
    if not m:
        raise ValueError("Resposta de posição inválida: " + repr(answer))
    return float(m.group(1)), float(m.group(2))


def move_command(az: float, el: float) -> str:
    """GS-232: 'Waaa eee' (graus inteiros, 3 dígitos)."""
    return f"W{int(round(az)):03d} {int(round(el)):03d}\r"


def _unwrap(seq):
    out = [seq[0] % 360.0]
    for a in seq[1:]:
        prev = out[-1]
        out.append(prev + (a - prev + 180.0) % 360.0 - 180.0)
    return out


def plan_pass(track: list[tuple[float, float, float]], profile: RotorProfile, prefer: str = "auto") -> dict:
    """Escolhe como seguir a passagem sem bater no batente.

    track: [(t, azimute 0–360, elevação)] em ordem temporal (t em segundos, qualquer origem).
    Retorna {"mode": "normal"|"flip"|"reposiciona", "times": [...], "track": [(az_rotor, el_rotor)]}.
    No modo flip (elevação até 180°) a antena passa "por cima": az+180 e 180−el, evitando a volta
    completa no meio da passagem. prefer (v1.7.1): "auto" (normal se couber), "flip" (flip sempre que
    o rotor permitir) ou "normal" (nunca flip).
    """
    if not track:
        return {"mode": "normal", "times": [], "track": []}
    times = [t for t, _, _ in track]
    els = [max(0.0, e) for _, _, e in track]

    def fits(az_list):
        for shift in (0.0, 360.0, -360.0):
            vals = [a + shift for a in az_list]
            if min(vals) >= 0 and max(vals) <= profile.az_max:
                return shift
        return None

    def flip():
        if profile.el_max < 180 or prefer == "normal":
            return None
        faz = _unwrap([(a + 180.0) % 360.0 for _, a, _ in track])
        fshift = fits(faz)
        if fshift is None:
            return None
        return {"mode": "flip", "times": times, "track": [(a + fshift, 180.0 - e) for a, e in zip(faz, els)]}

    if prefer == "flip" and flip() is not None:
        return flip()
    az = _unwrap([a for _, a, _ in track])
    shift = fits(az)
    if shift is not None:
        return {"mode": "normal", "times": times, "track": [(a + shift, e) for a, e in zip(az, els)]}
    if flip() is not None:
        return flip()
    # sem solução contínua: segue normalmente e reposiciona uma vez ao cruzar o batente
    return {"mode": "reposiciona", "times": times, "track": [(a % 360.0, e) for (_, a, _), e in zip(track, els)]}


def to_rotor(az: float, el: float, plan: Optional[dict], profile: RotorProfile,
             when: Optional[float] = None, current_az: Optional[float] = None) -> tuple[float, float]:
    """Apontamento (az 0–360, el) → coordenadas do rotor, coerentes com o plano da passagem.

    Entre az e az+360 (sobreposição do G-5400B) escolhe o mais próximo do azimute planejado
    para esse instante (ou da posição atual), para não dar a volta no batente.
    """
    el = max(profile.min_el, el)
    if (plan or {}).get("mode") == "flip":
        az, el = (az + 180.0) % 360.0, 180.0 - el
    else:
        az = az % 360.0
    ref = current_az
    if plan and plan.get("track"):
        if when is not None and plan.get("times"):
            i = min(range(len(plan["times"])), key=lambda k: abs(plan["times"][k] - when))
        else:
            i = 0
        ref = plan["track"][i][0]
    candidates = [c for c in (az, az + 360.0) if 0 <= c <= profile.az_max] or [az]
    best = min(candidates, key=lambda c: abs(c - ref)) if ref is not None else candidates[0]
    return (min(profile.az_max, max(0.0, best + profile.north_offset)),
            min(profile.el_max, max(0.0, el)))


def needs_move(target: tuple[float, float], current: Optional[tuple[float, float]], profile: RotorProfile) -> bool:
    if current is None:
        return True
    return abs(target[0] - current[0]) > profile.tolerance or abs(target[1] - current[1]) > profile.tolerance


class GS232Rotor:
    """Cliente GS-232A/B por porta serial (pyserial). Thread-safe; nunca bloqueia a interface."""

    def __init__(self, logger: Callable[[str], None] | None = None):
        self.logger = logger or (lambda text: None)
        self.port = None
        self.lock = threading.RLock()
        self.position: Optional[tuple[float, float]] = None
        self.last_command_at = 0.0
        self.failures = 0

    @property
    def connected(self) -> bool:
        return bool(self.port is not None and getattr(self.port, "is_open", False))

    def connect(self, port: str, baud: int = 9600, timeout: float = 1.0, opener=None):
        with self.lock:
            self.close()
            if opener is None:
                import serial
                opener = serial.Serial
            self.port = opener(port=port, baudrate=int(baud), timeout=timeout, write_timeout=timeout)
            self.logger(f"Rotor: porta {port} aberta a {baud} bps")
            self.position = self.read_position()
            return self.position

    def close(self):
        with self.lock:
            if self.port is not None:
                try:
                    self.port.close()
                except Exception:
                    pass
            self.port = None

    def _send(self, command: str, expect_answer: bool = False) -> str:
        with self.lock:
            if not self.connected:
                raise ConnectionError("Rotor desconectado")
            try:
                self.port.reset_input_buffer()
            except Exception:
                pass
            self.port.write(command.encode("ascii"))
            self.port.flush()
            self.logger("Rotor TX " + command.strip())
            if not expect_answer:
                return ""
            raw = self.port.read_until(b"\r") or b""
            answer = raw.decode("ascii", errors="replace").strip()
            self.logger("Rotor RX " + answer)
            return answer

    def read_position(self) -> tuple[float, float]:
        try:
            pos = parse_position(self._send("C2\r", expect_answer=True))
        except Exception:
            self.failures += 1
            raise
        self.failures = 0
        self.position = pos
        return pos

    def move(self, az: float, el: float, profile: RotorProfile) -> tuple[float, float]:
        az = min(profile.az_max, max(0.0, az))
        el = min(profile.el_max, max(0.0, el))
        self._send(move_command(az, el))
        self.last_command_at = time.monotonic()
        return az, el

    def stop(self):
        """PARAR: 'S' interrompe azimute e elevação (GS-232)."""
        if self.connected:
            try:
                self._send("S\r")
            except Exception as exc:
                self.logger("Rotor: falha ao enviar PARAR: " + str(exc))

    def park(self, profile: RotorProfile):
        return self.move(profile.park_az, profile.park_el, profile)


def probe_port(port: str, baud: int = 9600, opener=None) -> Optional[tuple[float, float]]:
    """Autodetecção somente leitura: envia 'C2' e aceita só resposta de posição válida. Não move o rotor."""
    rotor = GS232Rotor()
    try:
        return rotor.connect(port, baud, timeout=0.6, opener=opener)
    except Exception:
        return None
    finally:
        rotor.close()


def calibrated_north_offset(read_az: float, true_az: float, current_offset: float = 0.0) -> float:
    """Calibração guiada do norte: a antena aponta de fato para `true_az` (ex.: referência visual), mas o
    controlador lê `read_az`. Retorna a nova correção do norte (somada aos comandos), em −180…180."""
    raw = current_offset + (read_az - true_az)
    return (raw + 180.0) % 360.0 - 180.0


def jog_target(position: Optional[tuple[float, float]], d_az: float, d_el: float,
               profile: RotorProfile) -> Optional[tuple[float, float]]:
    """Ajuste manual por setas: posição atual + passo, dentro dos limites do rotor."""
    if position is None:
        return None
    return (min(profile.az_max, max(0.0, position[0] + d_az)), min(profile.el_max, max(0.0, position[1] + d_el)))


def antenna_line(lat: float, lon: float, az: float, km: float = 2500.0, steps: int = 24) -> list:
    """Linha no mapa (lat, lon) saindo da estação na direção `az` (grande círculo), para a seta do rotor."""
    import math
    r = 6371.0
    la1, lo1, b = math.radians(lat), math.radians(lon), math.radians(az % 360.0)
    out = []
    for i in range(steps + 1):
        d = km * i / steps / r
        la2 = math.asin(math.sin(la1) * math.cos(d) + math.cos(la1) * math.sin(d) * math.cos(b))
        lo2 = lo1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(la1), math.cos(d) - math.sin(la1) * math.sin(la2))
        out.append([round(math.degrees(la2), 4), round((math.degrees(lo2) + 540.0) % 360.0 - 180.0, 4)])
    return out
