"""Optional station location sources.

No external request unless UI previously obtained explicit user consent.
This module never persists or applies a fix to station settings by itself.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional
import requests

IP_ENDPOINT = "https://ipwho.is/"


@dataclass(frozen=True)
class GeoFix:
    latitude: float
    longitude: float
    source: str
    altitude_m: Optional[float] = None
    accuracy_m: Optional[float] = None
    description: str = ""
    approximate: bool = False

    def validate(self):
        if not (math.isfinite(self.latitude) and -90 <= self.latitude <= 90):
            raise ValueError("Latitude recebida inválida")
        if not (math.isfinite(self.longitude) and -180 <= self.longitude <= 180):
            raise ValueError("Longitude recebida inválida")
        if self.altitude_m is not None and not math.isfinite(self.altitude_m):
            raise ValueError("Altitude recebida inválida")
        if self.accuracy_m is not None and (not math.isfinite(self.accuracy_m) or self.accuracy_m < 0):
            raise ValueError("Precisão recebida inválida")
        return self


def lookup_approximate_ip(*, http_get=None) -> GeoFix:
    """One HTTPS request. The caller MUST ask for consent before invoking.

    ipwho.is receives the user's public IP and standard HTTP metadata. The
    lookup is city/region-level only and must not be labeled as GPS accuracy.
    """
    request = http_get or requests.get
    response = request(IP_ENDPOINT, timeout=9, headers={
        "User-Agent": "PT2VHF-Sat-Tool/1.0.1 (optional consent-based location)",
        "Accept": "application/json",
    })
    response.raise_for_status()
    url = getattr(response, "url", IP_ENDPOINT)
    if not str(url).startswith("https://"):
        raise ValueError("A consulta de localização perdeu a conexão HTTPS")
    data = response.json()
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ValueError("O serviço não conseguiu determinar a região aproximada do IP")
    lat = data.get("latitude")
    lon = data.get("longitude")
    if not isinstance(lat, (float, int)) or isinstance(lat, bool):
        raise ValueError("O serviço não retornou latitude válida")
    if not isinstance(lon, (float, int)) or isinstance(lon, bool):
        raise ValueError("O serviço não retornou longitude válida")
    place = ", ".join(str(data[k]).strip() for k in ("city", "region", "country")
                      if data.get(k))
    return GeoFix(float(lat), float(lon), source="IP público (aproximada)",
                  description=place or "Região estimada pelo IP",
                  approximate=True).validate()


def nmea_checksum_valid(line: str) -> bool:
    line=line.strip()
    if not line.startswith("$") or "*" not in line:
        return False
    payload,_,crc=line[1:].rpartition("*")
    if len(crc)!=2:
        return False
    value=0
    for character in payload:
        value ^= ord(character)
    try:
        return value == int(crc,16)
    except ValueError:
        return False


def _nmea_degrees(value: str, hemisphere: str, latitude: bool) -> float:
    if hemisphere not in (("N","S") if latitude else ("E","W")):
        raise ValueError("Hemisfério NMEA inválido")
    if not value or "." not in value:
        raise ValueError("Coordenada NMEA ausente")
    digit_count=2 if latitude else 3
    if len(value)<digit_count+2:
        raise ValueError("Coordenada NMEA incompleta")
    degrees=int(value[:digit_count])
    minutes=float(value[digit_count:])
    if not 0<=minutes<60:
        raise ValueError("Minutos NMEA inválidos")
    decimal=degrees+minutes/60.0
    return -decimal if hemisphere in ("S","W") else decimal


def parse_nmea_position(line: str) -> Optional[GeoFix]:
    """Read a valid, checksum-verified RMC or GGA NMEA position.

    Does not accept a void RMC fix, GGA quality=0, or unknown sentence types.
    """
    if not nmea_checksum_valid(line):
        return None
    fields=line.strip()[1:].split("*",1)[0].split(",")
    if len(fields)<7:
        return None
    kind=fields[0][-3:]
    try:
        if kind=="RMC" and len(fields)>=7:
            if fields[2] != "A":
                return None
            lat=_nmea_degrees(fields[3],fields[4],True)
            lon=_nmea_degrees(fields[5],fields[6],False)
            return GeoFix(lat,lon,source="GPS NMEA serial",
                          description="Posição RMC válida, checksum verificado").validate()
        if kind=="GGA" and len(fields)>=10:
            if not fields[6] or int(fields[6])<=0:
                return None
            lat=_nmea_degrees(fields[2],fields[3],True)
            lon=_nmea_degrees(fields[4],fields[5],False)
            altitude=float(fields[9]) if fields[9] and fields[10]=="M" else None
            return GeoFix(lat,lon,source="GPS NMEA serial",altitude_m=altitude,
                          description="Posição GGA válida, checksum verificado").validate()
    except (ValueError,IndexError):
        return None
    return None


def read_gps_serial(port: str, *, baud: int=9600, timeout_s: float=12) -> GeoFix:
    """Read NMEA from explicitly selected serial GPS port, with no writes."""
    import serial
    if not isinstance(port,str) or not port.strip():
        raise ValueError("Selecione a porta serial do GPS")
    if not 4800<=int(baud)<=115200:
        raise ValueError("Baud GPS fora da faixa permitida")
    deadline=time.monotonic()+max(2.0,min(30.0,float(timeout_s)))
    with serial.Serial(port=port.strip(),baudrate=baud,timeout=1.0) as device:
        while time.monotonic()<deadline:
            raw=device.readline()
            if not raw:
                continue
            fix=parse_nmea_position(raw.decode("ascii",errors="ignore"))
            if fix is not None:
                return fix
    raise TimeoutError("GPS sem posição NMEA válida no prazo; confira porta, baud e antena")
