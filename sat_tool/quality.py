"""Qualidade da passagem (1 a 5 estrelas): nota composta do que afeta um contato real.

Não é só elevação máxima ou duração. Considera geometria (elevação, tempo útil, distância),
taxa de variação do Doppler (difícil em SSB/CW nas passagens altas), estado do satélite,
iluminação (satélites que só operam ao sol, como o AO-7) e congestionamento provável em FM.
Cada fator vira um motivo legível para o tooltip da linha.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import radians

import numpy as np

C = 299_792_458.0
R_EARTH_KM = 6371.0
# Satélites cujas baterias falharam: operam apenas iluminados pelo sol.
SUN_ONLY = {"7530": "AO-7"}

WEIGHTS = {"elevation": 30, "usable": 20, "range": 10, "doppler": 10, "status": 10, "sun": 10, "crowd": 10}


@dataclass
class PassQuality:
    stars: int
    score: float
    reasons: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return "★" * self.stars + "☆" * (5 - self.stars)

    @property
    def tooltip(self) -> str:
        return f"Qualidade {self.stars}/5 ({self.score:.0f} pontos)\n" + "\n".join("• " + r for r in self.reasons)


def sun_unit_vector(when: datetime) -> np.ndarray:
    """Direção do Sol em coordenadas equatoriais (precisão ~0,01°, suficiente para eclipse)."""
    jd = when.timestamp() / 86400.0 + 2440587.5
    n = jd - 2451545.0
    g = radians((357.529 + 0.98560028 * n) % 360)
    q = (280.459 + 0.98564736 * n) % 360
    lam = radians(q + 1.915 * np.sin(g) + 0.020 * np.sin(2 * g))
    eps = radians(23.439 - 0.00000036 * n)
    return np.array([np.cos(lam), np.cos(eps) * np.sin(lam), np.sin(eps) * np.sin(lam)])


def in_shadow(sat_km: np.ndarray, sun_hat: np.ndarray) -> bool:
    """Sombra cilíndrica da Terra."""
    proj = float(np.dot(sat_km, sun_hat))
    return proj < 0 and float(np.linalg.norm(sat_km - proj * sun_hat)) < R_EARTH_KM


def sample_pass(sat, station, p: dict, ts, step_s: float = 10.0) -> dict:
    """Amostra a passagem: elevação, distância, velocidade radial e iluminação."""
    from skyfield.api import wgs84
    aos, los = p["aos"], p["los"]
    total = max(step_s, (los - aos).total_seconds())
    offsets = np.arange(0, total + step_s, step_s)
    whens = [aos + timedelta(seconds=float(s)) for s in offsets]
    t = ts.from_datetimes(whens)
    site = wgs84.latlon(station.lat, station.lon, elevation_m=station.altitude_m)
    topo = (sat - site).at(t)
    alt, _, dist = topo.altaz()
    rng = dist.km
    radial = np.gradient(rng * 1000.0, offsets) if len(offsets) > 1 else np.zeros(1)
    geo = sat.at(t).position.km.T
    sunlit = np.array([not in_shadow(geo[i], sun_unit_vector(w)) for i, w in enumerate(whens)])
    return {"t": offsets, "el": alt.degrees, "range_km": rng, "radial_m_s": radial, "sunlit": sunlit}


def score_pass(samples: dict, *, norad: str, mode: str, downlink_hz: int | None, alive: bool | None,
               local_start: datetime, min_elevation: float = 10.0) -> PassQuality:
    el = np.asarray(samples["el"])
    t = np.asarray(samples["t"])
    step = float(t[1] - t[0]) if len(t) > 1 else 10.0
    rng = np.asarray(samples["range_km"])
    reasons, parts = [], {}

    max_el = float(el.max()) if len(el) else 0.0
    parts["elevation"] = np.clip((max_el - min_elevation) / (60.0 - min_elevation), 0, 1)
    reasons.append(f"elevação máxima {max_el:.0f}°")

    usable = float((el >= max(15.0, min_elevation)).sum() * step)
    parts["usable"] = np.clip(usable / 360.0, 0, 1)
    reasons.append(f"{usable / 60:.1f} min acima de {max(15.0, min_elevation):.0f}°"
                   + (" — curto para um QSO" if usable < 120 else ""))

    min_range = float(rng.min()) if len(rng) else 3000.0
    parts["range"] = np.clip(1 - (min_range - 500.0) / 2000.0, 0, 1)
    reasons.append(f"distância mínima {min_range:.0f} km")

    linear = mode.upper() in ("USB", "LSB", "CW", "SSB")
    if downlink_hz and len(t) > 2:
        rate = float(np.max(np.abs(np.gradient(samples["radial_m_s"], t)))) * downlink_hz / C
        limit = 40.0 if linear else 150.0
        parts["doppler"] = np.clip(1 - max(0.0, rate - limit / 2) / limit, 0, 1)
        if rate > limit:
            reasons.append(f"Doppler rápido ({rate:.0f} Hz/s){' — exige correção contínua em SSB/CW' if linear else ''}")
    else:
        parts["doppler"] = 1.0

    if alive is False:
        parts["status"] = 0.0
        reasons.append("satélite sem transmissor ativo no SatNOGS")
    else:
        parts["status"] = 1.0 if alive else 0.6

    sunlit = np.asarray(samples.get("sunlit", np.ones(len(el), dtype=bool)))
    lit = float(sunlit.mean()) if len(sunlit) else 1.0
    if str(norad) in SUN_ONLY:
        parts["sun"] = lit
        if lit < 0.95:
            reasons.append(f"{SUN_ONLY[str(norad)]} só opera iluminado: {lit * 100:.0f}% da passagem ao sol")
    else:
        parts["sun"] = 1.0
        if lit < 0.05:
            reasons.append("passagem em eclipse")

    crowd = 1.0
    if not linear:
        busy = local_start.weekday() >= 5 or 18 <= local_start.hour <= 22
        if busy:
            crowd = 0.5
            reasons.append("horário/dia de muito movimento em satélites FM")
    parts["crowd"] = crowd

    score = sum(WEIGHTS[k] * float(v) for k, v in parts.items())
    # Passagem muito baixa ou curta nunca passa de 2 estrelas.
    if max_el < 15 or usable < 90:
        score = min(score, 35.0)
    # Os fatores de estado/sol/movimento dão ~30 pontos a quase toda passagem; a escala começa em 40.
    stars = int(np.clip(1 + round(4 * np.clip((score - 40.0) / 60.0, 0, 1)), 1, 5))
    return PassQuality(stars, score, reasons)


def pass_quality(sat, station, p: dict, ts, *, norad: str, mode: str, downlink_hz: int | None,
                 alive: bool | None) -> PassQuality:
    samples = sample_pass(sat, station, p, ts)
    return score_pass(samples, norad=norad, mode=mode, downlink_hz=downlink_hz, alive=alive,
                      local_start=p["aos"].astimezone(), min_elevation=station.min_elevation)
