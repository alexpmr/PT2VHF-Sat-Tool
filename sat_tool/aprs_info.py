"""Pacotes APRS recebidos via satélite (ISS/digipeaters): campos legíveis para a Telemetria (v1.6.0).

Usa o aprslib (o mesmo parser do PT2VHF APRS Client). Calcula distância/azimute até a estação
e o locator Maidenhead da posição. Nunca transmite nada.
"""
from __future__ import annotations

from math import asin, atan2, cos, degrees, radians, sin, sqrt
from typing import Optional


def latlon_to_maidenhead(lat: float, lon: float, chars: int = 6) -> str:
    lon += 180.0
    lat += 90.0
    out = chr(ord("A") + int(lon // 20)) + chr(ord("A") + int(lat // 10))
    out += str(int((lon % 20) // 2)) + str(int(lat % 10))
    if chars >= 6:
        out += chr(ord("a") + int((lon % 2) * 12)) + chr(ord("a") + int((lat % 1) * 24))
    return out


def distance_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    p1, p2 = radians(lat1), radians(lat2)
    dlat, dlon = p2 - p1, radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    dist = 2 * 6371.0 * asin(min(1.0, sqrt(a)))
    brg = (degrees(atan2(sin(dlon) * cos(p2), cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dlon))) + 360) % 360
    return dist, brg


def parse(text: str) -> Optional[dict]:
    """TNC2 ("ORIGEM>DESTINO,CAMINHO:info") → dict do aprslib, ou None se não for APRS."""
    if not text or ">" not in text or ":" not in text:
        return None
    head, _, info = text.partition(":")
    if info.startswith("T#"):  # telemetria APRS (o aprslib não interpreta)
        src, _, rest = head.partition(">")
        parts = info[2:].split(",")
        try:
            vals = [float(v) for v in parts[1:6]]
        except ValueError:
            vals = parts[1:6]
        return {"from": src, "to": rest.split(",")[0], "path": rest.split(",")[1:], "format": "telemetry",
                "telemetry": {"seq": parts[0].lstrip("0") or "0", "vals": vals,
                              "bits": parts[6] if len(parts) > 6 else ""}}
    try:
        import aprslib
        return aprslib.parse(text)
    except Exception:
        return None


def describe(pkt: dict, station: Optional[tuple[float, float]] = None) -> tuple[str, dict]:
    """Resumo de uma linha + campos detalhados (ordenados) para o painel."""
    fields: dict = {"De": pkt.get("from", ""), "Para": pkt.get("to", ""),
                    "Caminho": ",".join(pkt.get("path") or []) or "direto"}
    digis = [p.rstrip("*") for p in (pkt.get("path") or []) if p.endswith("*")]
    if digis:
        fields["Digipeater usado"] = ", ".join(digis)
    fmt = pkt.get("format", "")
    fields["Tipo"] = fmt or "?"
    summary = []
    if "latitude" in pkt and "longitude" in pkt:
        lat, lon = float(pkt["latitude"]), float(pkt["longitude"])
        loc = latlon_to_maidenhead(lat, lon)
        fields["Posição"] = f"{lat:.4f}, {lon:.4f} ({loc})"
        fields["Símbolo"] = f"{pkt.get('symbol_table', '')}{pkt.get('symbol', '')}"
        txt = f"Posição {loc}"
        if station:
            dist, brg = distance_bearing(station[0], station[1], lat, lon)
            fields["Distância/azimute"] = f"{dist:.0f} km · {brg:.0f}°"
            txt += f" · {dist:.0f} km {brg:.0f}°"
        summary.append(txt)
    if fmt == "message" or "message_text" in pkt:
        fields["Mensagem"] = pkt.get("message_text", "")
        fields["Destinatário"] = pkt.get("addresse", "")
        if pkt.get("msgNo"):
            fields["ID"] = pkt["msgNo"]
        if pkt.get("response"):
            fields["Resposta"] = pkt["response"].upper()
        summary.append(f"Msg → {pkt.get('addresse', '')}: {pkt.get('message_text', pkt.get('response', ''))}")
    if pkt.get("status"):
        fields["Status"] = pkt["status"]
        summary.append("Status: " + pkt["status"])
    if pkt.get("object_name"):
        fields["Objeto/item"] = pkt["object_name"]
    if "telemetry" in pkt:
        tl = pkt["telemetry"]
        fields["Telemetria"] = f"#{tl.get('seq')} valores {tl.get('vals')} bits {tl.get('bits', '')}"
        summary.append(f"Telemetria #{tl.get('seq')}")
    if pkt.get("weather"):
        fields["Clima"] = ", ".join(f"{k}={v}" for k, v in pkt["weather"].items())
        summary.append("Clima")
    if fmt == "mic-e":
        fields["Mic-E"] = pkt.get("mtype", "")
    if pkt.get("comment"):
        fields["Comentário"] = pkt["comment"]
        summary.append(pkt["comment"])
    return " · ".join(summary) or fmt, fields
