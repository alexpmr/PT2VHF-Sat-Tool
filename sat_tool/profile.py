"""Station equipment capabilities and explicit/operator-selected satellite filtering.

Fallback suggestions are *candidates*, NOT operational confirmations. Actual
transponder service and frequencies come from timestamped SatNOGS records.
"""
from __future__ import annotations

from typing import Any

# NORAD IDs are stable keys. Modes here are historical capability hints only.
CANDIDATES = {
    "25544": {"modes": ("FM",), "note": "ARISS/ISS; verificar repetidor ativo"},
    "27607": {"modes": ("FM",), "note": "SO-50; confirmar status"},
    "43017": {"modes": ("FM",), "note": "AO-91; confirmar status"},
    "44496": {"modes": ("FM",), "note": "PO-101; confirmar status"},
    "44881": {"modes": ("SSB", "CW"), "note": "RS-44; confirmar status"},
    "24278": {"modes": ("SSB", "CW"), "note": "FO-29; confirmar status"},
    "39444": {"modes": ("SSB", "CW"), "note": "AO-73; confirmar status"},
}


def normalize_modes(modes):
    accepted = {"FM", "SSB", "CW"}
    return sorted(accepted.intersection({str(m).upper() for m in (modes or [])}))


def row_modes(row: dict) -> set:
    text = str(row.get("mode") or "").upper()
    label = str(row.get("description") or "").upper()
    kind = str(row.get("type") or "").upper()
    whole = " ".join((text, label, kind))
    modes = set()
    if "FM" in whole or "AFSK" in whole or "FSK" in whole:
        modes.add("FM")
    if any(s in whole for s in ("SSB", "USB", "LSB", "LINEAR")):
        modes.add("SSB")
    if "CW" in whole or "MORSE" in whole:
        modes.add("CW")
    return modes


def freq_band(hz):
    if hz is None:
        return ""
    hz = int(hz)
    if 144_000_000 <= hz <= 148_000_000:
        return "VHF"
    if 430_000_000 <= hz <= 450_000_000:
        return "UHF"
    if 1_240_000_000 <= hz <= 1_300_000_000:
        return "23cm"
    return "other"


def capability(norad: str, rows: list, modes: list, bands: list) -> dict:
    """Return compatibility from published channel data, never claim active from orbit."""
    wanted = set(normalize_modes(modes))
    available_bands = set(bands or [])
    matches = []
    for row in rows:
        if row.get("alive") is False or str(row.get("status", "")).lower() not in ("", "active"):
            continue
        these = row_modes(row)
        dl = row.get("downlink_low")
        ul = row.get("uplink_low")
        if not these.intersection(wanted) or not dl:
            continue
        if freq_band(dl) not in available_bands:
            continue
        if ul is not None and freq_band(ul) not in available_bands:
            continue
        matches.append({"modes": sorted(these.intersection(wanted)), "receive_only": ul is None,
                        "downlink": int(dl), "uplink": int(ul) if ul is not None else None})
    if matches:
        return {"suggested": True, "confirmed": False, "source": "SatNOGS (canal publicado)",
                "modes": sorted({m for row in matches for m in row["modes"]}),
                "rx_only": all(row["receive_only"] for row in matches), "channels": matches,
                "notice": "Canal listado; funcionamento e permissão TX não confirmados"}
    if rows:
        return {"suggested": False, "confirmed": False, "source": "SatNOGS", "modes": [],
                "rx_only": False, "channels": [], "notice": "Sem canal compatível no cache"}
    hint = CANDIDATES.get(str(norad))
    hints = sorted(wanted.intersection(hint["modes"])) if hint else []
    if not ({"VHF", "UHF"} <= available_bands):
        hints = []  # Do not assume historical band pair works with restricted equipment.
    return {"suggested": bool(hints), "confirmed": False, "source": "histórico (não validado)",
            "modes": hints, "rx_only": False, "channels": [],
            "notice": hint["note"] if hint and hints else "Aguardando dados de transponder"}


def choose_satellites(orbit_objects: dict, rows_by_norad: dict, modes: list, bands: list,
                      manual_selection=None):
    """Return stable, ordered NORAD IDs, respecting explicit manual choices."""
    if manual_selection is not None:
        return [str(n) for n in manual_selection if str(n) in orbit_objects]
    selected = []
    for ident, obj in orbit_objects.items():
        if capability(ident, rows_by_norad.get(str(ident), []), modes, bands)["suggested"]:
            selected.append(str(ident))
    return sorted(selected, key=lambda i: str(orbit_objects[i].get("OBJECT_NAME", i)))


def render_service(modes: list) -> str:
    return "/".join(normalize_modes(modes)) or "modo desconhecido"
