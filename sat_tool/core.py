"""Standalone orbital/Doppler computation; no Qt or CAT side effects."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import acos, cos, degrees, radians, sin, asin
from typing import Any

C = 299_792_458.0
R_EARTH_KM = 6371.0
UTC = timezone.utc


@dataclass
class Station:
    callsign: str
    lat: float
    lon: float
    altitude_m: float = 0.0
    min_elevation: float = 10.0

    def validate(self):
        if not -90 <= self.lat <= 90 or not -180 <= self.lon <= 180:
            raise ValueError("Latitude/longitude fora dos limites")
        if not 0 <= self.min_elevation <= 90:
            raise ValueError("Elevação mínima deve estar entre 0 e 90°")


def doppler_frequencies(uplink_hz: int, downlink_hz: int, radial_m_s: float) -> tuple[int, int]:
    """Positive radial velocity means receding.

    Ground RX must follow satellite-to-ground Doppler f_down*(1-v/c).
    Ground TX compensates ground-to-satellite Doppler f_up/(1-v/c).
    """
    if abs(radial_m_s) > 20000:
        raise ValueError("Velocidade radial implausível")
    return round(uplink_hz / (1.0 - radial_m_s / C)), round(downlink_hz * (1.0 - radial_m_s / C))


def paired_linear_uplink(downlink_hz: int, dl_low: int, dl_high: int,
                         ul_low: int, ul_high: int, inverted: bool) -> int:
    """Translate a linear-transponder receive cursor into its uplink position.

    Interpolate within actual uplink/downlink passband, clamp endpoints.
    """
    if dl_high <= dl_low or ul_high <= ul_low:
        raise ValueError("Transponder linear requer faixas válidas")
    x = max(0.0, min(1.0, (downlink_hz - dl_low) / (dl_high - dl_low)))
    return round(ul_high - x * (ul_high - ul_low) if inverted else ul_low + x * (ul_high - ul_low))


def make_satellite(omm: dict[str, Any], ts=None):
    from skyfield.api import EarthSatellite, load
    ts = ts or load.timescale(builtin=True)
    if omm.get("TLE_LINE1") and omm.get("TLE_LINE2"):
        return EarthSatellite(omm["TLE_LINE1"], omm["TLE_LINE2"], omm.get("OBJECT_NAME", ""), ts)
    return EarthSatellite.from_omm(ts, omm)


def now_utc():
    return datetime.now(UTC)


def position(sat, station: Station, when: datetime | None = None, ts=None) -> dict:
    from skyfield.api import load, wgs84
    ts = ts or load.timescale(builtin=True)
    when = when or now_utc()
    t = ts.from_datetime(when)
    site = wgs84.latlon(station.lat, station.lon, elevation_m=station.altitude_m)
    topocentric = sat - site
    difference = topocentric.at(t)
    alt, az, distance = difference.altaz()
    sub = wgs84.subpoint(sat.at(t))
    # Centered finite difference: positive when satellite is moving away.
    before = ts.from_datetime(when - timedelta(seconds=0.5))
    after = ts.from_datetime(when + timedelta(seconds=0.5))
    radial = (topocentric.at(after).distance().m - topocentric.at(before).distance().m)
    height_km = sub.elevation.km
    horizon = degrees(acos(R_EARTH_KM / (R_EARTH_KM + max(0.0, height_km))))
    return {
        "elevation": alt.degrees, "azimuth": az.degrees, "range_km": distance.km,
        "radial_m_s": radial, "sat_lat": sub.latitude.degrees, "sat_lon": sub.longitude.degrees,
        "height_km": height_km, "footprint_radius_deg": horizon,
        "visible": alt.degrees >= station.min_elevation,
    }


def ground_track(sat, start: datetime | None = None, *, minutes: int = 120, steps: int = 100, ts=None) -> list[list[list[float]]]:
    """Return longitude-wrap-safe polyline segments [lat,lon]."""
    from skyfield.api import load, wgs84
    ts = ts or load.timescale(builtin=True)
    start = start or now_utc()
    segments: list[list[list[float]]] = [[]]
    previous_lon = None
    for i in range(steps + 1):
        t = ts.from_datetime(start + timedelta(minutes=minutes * (i / steps - 0.25)))
        sub = wgs84.subpoint(sat.at(t))
        lat, lon = sub.latitude.degrees, sub.longitude.degrees
        if previous_lon is not None and abs(lon - previous_lon) > 180:
            segments.append([])
        segments[-1].append([lat, lon])
        previous_lon = lon
    return [segment for segment in segments if len(segment) >= 2]


def footprint(lat: float, lon: float, angular_radius_deg: float, points: int = 72) -> list[list[list[float]]]:
    """Ground horizon circle, split at dateline."""
    la, lo, r = map(radians, (lat, lon, angular_radius_deg))
    segs: list[list[list[float]]] = [[]]
    last = None
    for i in range(points + 1):
        bearing = 2 * 3.141592653589793 * i / points
        lat2 = asin(sin(la) * cos(r) + cos(la) * sin(r) * cos(bearing))
        lon2 = lo + __import__('math').atan2(sin(bearing) * sin(r) * cos(la), cos(r) - sin(la) * sin(lat2))
        a = degrees(lat2)
        b = ((degrees(lon2) + 180) % 360) - 180
        if last is not None and abs(last - b) > 180:
            segs.append([])
        segs[-1].append([a,b])
        last = b
    return [s for s in segs if len(s)>1]


def predict_passes(sat, station: Station, now: datetime | None = None,
                   hours: int = 36, ts=None) -> list[dict]:
    from skyfield.api import load, wgs84
    ts = ts or load.timescale(builtin=True)
    now = now or now_utc()
    site = wgs84.latlon(station.lat, station.lon, elevation_m=station.altitude_m)
    t0 = ts.from_datetime(now)
    t1 = ts.from_datetime(now + timedelta(hours=hours))
    times, events = sat.find_events(site, t0, t1, altitude_degrees=station.min_elevation)
    passes = []
    active = None
    for t, event in zip(times, events):
        when = t.utc_datetime().replace(tzinfo=UTC)
        if event == 0:
            active = {"aos": when, "max_el": 0.0, "tca": None, "los": None}
        elif event == 1:
            if active is None:  # Already in progress at t0.
                active = {"aos": now, "max_el": 0.0, "tca": None, "los": None}
            alt, _, _ = (sat - site).at(t).altaz()
            active["max_el"] = round(alt.degrees, 1)
            active["tca"] = when
        elif event == 2:
            if active is None:
                active = {"aos": now, "max_el": 0.0, "tca": None, "los": None}
            active["los"] = when
            if active["max_el"] == 0.0:
                # Keep pass even if culmination was before t0; use current altitude.
                alt,_,_ = (sat - site).at(t0).altaz()
                active["max_el"] = round(alt.degrees, 1)
            passes.append(active)
            active = None
    return passes


def transponder_options(rows: list[dict]) -> list[dict]:
    """Only operational entries; labels explicitly distinguish RX-only devices."""
    options = []
    for t in rows:
        if str(t.get("status", "")).lower() not in ("active", ""):
            continue
        if t.get("alive") is False:
            continue
        dl = t.get("downlink_low")
        ul = t.get("uplink_low")
        if not dl:
            continue
        name = t.get("description") or t.get("mode") or t.get("type") or "Canal"
        options.append({
            "name": str(name), "downlink": int(dl), "downlink_high": int(t.get("downlink_high") or dl),
            "uplink": int(ul) if ul else None,
            "uplink_high": int(t.get("uplink_high") or ul) if ul else None,
            "mode": (t.get("mode") or "FM").upper(), "inverted": bool(t.get("invert")),
            "uuid": t.get("uuid"), "receive_only": ul is None,
            "type": t.get("type") or "",
        })
    return options

def ground_track_between(sat, begin:datetime, end:datetime, *, ts=None, max_samples:int=220):
    """Ground track between two UTC instants, splitting at the ±180° meridian.

    History here is orbit reconstructed from elements, not received GPS telemetry.
    """
    from skyfield.api import load,wgs84
    if begin.tzinfo is None or end.tzinfo is None:
        raise ValueError("Orbit track needs timezone-aware datetimes")
    if end<=begin: return []
    ts=ts or load.timescale(builtin=True)
    duration=(end-begin).total_seconds()
    steps=max(4,min(max_samples,int(duration/120)+1))
    result=[[]];last_lon=None
    for i in range(steps+1):
        when=begin+timedelta(seconds=duration*i/steps)
        sub=wgs84.subpoint(sat.at(ts.from_datetime(when)))
        lat,lon=sub.latitude.degrees,sub.longitude.degrees
        if last_lon is not None and abs(lon-last_lon)>180:
            result.append([])
        result[-1].append([lat,lon])
        last_lon=lon
    return [p for p in result if len(p)>=2]


def track_period_bounds(now:datetime, period_hours:float, direction:str, last_pass:dict|None=None):
    """Normalize user-visible trail presets into historical/forecast UTC intervals."""
    if now.tzinfo is None:raise ValueError("Timezone required")
    if not 0.1<=period_hours<=48:
        raise ValueError("Orbital period outside 0.1-48h")
    if direction not in ("Futuro","Passado","Ambos","Última passagem"):
        raise ValueError("Unknown track direction")
    period=timedelta(hours=period_hours)
    if direction=="Última passagem":
        if last_pass and last_pass.get("aos") and last_pass.get("los") and last_pass["los"]<=now:
            return (last_pass["aos"],last_pass["los"]),None
        return (now-timedelta(hours=2),now),None
    if direction=="Passado":
        return (now-period,now),None
    if direction=="Futuro":
        return None,(now,now+period)
    half=period/2
    return (now-half,now),(now,now+half)
