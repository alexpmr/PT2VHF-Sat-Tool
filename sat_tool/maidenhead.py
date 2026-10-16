"""Maidenhead (QTH/Grid Locator) to WGS-84 cell center, independent of GPS."""
from __future__ import annotations

import math
import re


def maidenhead_to_latlon(locator: str) -> tuple[float, float]:
    """Return geographic center (lat, lon) for 2/4/6/8/10-character grid.

    Maidenhead coordinates designate an *area*, not a GPS fix; the center is
    an approximation even for a six-character square. No network or CAT I/O.
    """
    grid=str(locator).strip().upper()
    if (len(grid) not in (2,4,6,8,10)
            or not re.fullmatch(r"[A-R]{2}(?:[0-9]{2}(?:[A-X]{2}(?:[0-9]{2}(?:[A-X]{2})?)?)?)?",grid)):
        raise ValueError("Grid Maidenhead inválido. Use AA00, AA00aa, AA00aa00 ou AA00aa00aa.")
    lon,lat=-180.0,-90.0
    width_lon,width_lat=20.0,10.0
    lon+=(ord(grid[0])-65)*width_lon
    lat+=(ord(grid[1])-65)*width_lat
    for i in range(2,len(grid),2):
        if (i//2)%2:
            width_lon/=10.0; width_lat/=10.0
            x=int(grid[i]); y=int(grid[i+1])
        else:
            width_lon/=24.0; width_lat/=24.0
            x=ord(grid[i])-65; y=ord(grid[i+1])-65
        lon+=x*width_lon
        lat+=y*width_lat
    lon+=width_lon/2.0
    lat+=width_lat/2.0
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError("Grid inválido")
    return round(lat,8),round(lon,8)
