"""Deterministic next-pass, operator-mode and Doppler planning.

All frequencies here are *predictions*, never confirmed CAT readings. No radio I/O.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .core import doppler_frequencies, paired_linear_uplink
from .profile import row_modes, freq_band, normalize_modes


def select_channel(rows: list, selected_modes: list, available_bands: list):
    """Select published RX and optional TX service; avoid false QSO claims for beacons."""
    desired=set(normalize_modes(selected_modes))
    bands=set(available_bands)
    candidates=[]
    for raw in rows or []:
        if raw.get("alive") is False or str(raw.get("status") or "").lower() not in ("", "active"):
            continue
        down=raw.get("downlink_low")
        uplink=raw.get("uplink_low")
        if not down or freq_band(down) not in bands:
            continue
        if uplink is not None and freq_band(uplink) not in bands:
            continue
        compatible=desired.intersection(row_modes(raw))
        if not compatible:
            continue
        # Explicitly classify receive-only services; a CW beacon is NOT a QSO transponder.
        rx_only=uplink is None
        mode=next((m for m in ("FM","SSB","CW") if m in compatible),None)
        dl_low=int(down)
        dl_high=int(raw.get("downlink_high") or dl_low)
        ul_low=int(uplink) if uplink is not None else None
        ul_high=int(raw.get("uplink_high") or ul_low) if ul_low is not None else None
        linear=bool(mode in ("SSB","CW") and ul_low and dl_high>dl_low and ul_high>ul_low)
        dl=round((dl_low+dl_high)/2) if dl_high>dl_low else dl_low
        ul=paired_linear_uplink(dl,dl_low,dl_high,ul_low,ul_high,bool(raw.get("invert"))) if linear else ul_low
        candidates.append({
            "mode":mode,"downlink_hz":dl,"uplink_hz":ul,
            "rx_only":rx_only,"linear":linear,"inverted":bool(raw.get("invert")),
            "name":str(raw.get("description") or raw.get("mode") or "Canal publicado"),
            "source":"SatNOGS · dados publicados, operação não confirmada",
        })
    # Prefer usable two-way channel, but never invent TX where only a beacon is listed.
    return sorted(candidates,key=lambda c:(c["rx_only"],("FM","SSB","CW").index(c["mode"]),c["name"]))[0] if candidates else None


def select_next_pass(passes: list, rows_by_norad: dict, selected_modes: list,
                     available_bands: list, now: datetime, enabled_ids=None):
    """Priority: active visible pass, then next AOS, only channels matching station."""
    if now.tzinfo is None:
        raise ValueError("UTC-aware current time required")
    allowed=set(str(i) for i in enabled_ids) if enabled_ids is not None else None
    possible=[]
    for p in passes:
        sid=str(p.get("id",""))
        if allowed is not None and sid not in allowed:
            continue
        aos,los=p.get("aos"),p.get("los")
        if not aos or not los or los<=now:
            continue
        channel=select_channel(rows_by_norad.get(sid,[]),selected_modes,available_bands)
        if channel:
            is_current=aos<=now<los
            # Select active highest elevation first when overlapping, then chronological future.
            sort_key=(0,-float(p.get("max_el",0)),aos) if is_current else (1,aos.timestamp(),aos)
            possible.append((sort_key,{**p,"channel":channel,"in_progress":is_current}))
    return min(possible,key=lambda item:item[0])[1] if possible else None


def clock_text(seconds: float) -> str:
    remaining=max(0,int(seconds))
    days,remaining=divmod(remaining,86400)
    hh,remaining=divmod(remaining,3600)
    mm,ss=divmod(remaining,60)
    return (f"{days}d " if days else "")+f"{hh:02d}:{mm:02d}:{ss:02d}"


def status_at(p:dict,when:datetime):
    if when < p["aos"]:
        return "PRÓXIMA PASSAGEM",clock_text((p["aos"]-when).total_seconds())
    if when < p["los"]:
        return "EM PASSAGEM",clock_text((p["los"]-when).total_seconds())
    return "CONCLUÍDA","00:00:00"


def frequency_prediction(channel:dict,radial_m_s:float):
    """Satellite-relative Doppler as estimates; RX-only is explicitly represented."""
    down=int(channel["downlink_hz"])
    up=channel.get("uplink_hz")
    if up is not None:
        corrected_up,corrected_down=doppler_frequencies(int(up),down,radial_m_s)
    else:
        _,corrected_down=doppler_frequencies(0,down,radial_m_s)
        corrected_up=None
    return {
        "rx_hz":corrected_down,"tx_hz":corrected_up,
        "rx_offset_hz":corrected_down-down,
        "tx_offset_hz":corrected_up-int(up) if up is not None else None,
        "nominal_rx_hz":down,"nominal_tx_hz":int(up) if up is not None else None,
    }


def orbital_age_days(epoch:datetime,when:datetime):
    if epoch.tzinfo is None or when.tzinfo is None:
        raise ValueError("Use timezone-aware datetimes")
    return abs((when-epoch).total_seconds())/86400
