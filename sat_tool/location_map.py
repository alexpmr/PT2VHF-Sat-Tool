"""Ground station map-picking validation; no station persistence or CAT side effects."""
from __future__ import annotations
import math


def valid_coordinates(lat, lon):
    """Validate untrusted JS/Qt map point with explicit type checks."""
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError("Coordenadas inválidas")
    if not isinstance(lat, (float,int)) or not isinstance(lon, (float,int)):
        raise ValueError("Coordenadas inválidas")
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError("Coordenadas não finitas")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Latitude/longitude fora dos limites WGS-84")
    return round(float(lat), 7), round(float(lon), 7)


def parse_coordinate_fields(lat_text, lon_text):
    """Support Brazilian decimal comma as well as point, no thousands separators."""
    try:
        lat=float(str(lat_text).strip().replace(",","."))
        lon=float(str(lon_text).strip().replace(",","."))
    except (ValueError,TypeError):
        raise ValueError("Informe latitude e longitude em graus decimais")
    return valid_coordinates(lat,lon)


def sanitize_map_pick(pick):
    """Only accept exact coordinate message shape from embedded, local map."""
    if not isinstance(pick,dict) or set(pick)!= {"lat","lon"}:
        raise ValueError("Resposta do mapa inválida")
    return valid_coordinates(pick["lat"],pick["lon"])
