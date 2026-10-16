"""Safe transponder selection for the TS-2000 CAT satellite controller.

A satellite can expose telemetry and many other channels in SatNOGS, not all
of which are two-way amateur crossband voice repeaters. Do not assume that the
first API record is a valid SAT uplink/downlink pairing.
"""
from __future__ import annotations


BANDS = (
    ("2 m", 144_000_000, 148_000_000),
    ("70 cm", 420_000_000, 450_000_000),
    ("23 cm", 1_240_000_000, 1_300_000_000),
)


def cat_band(hz: int | None) -> str | None:
    if hz is None:
        return None
    for name, low, high in BANDS:
        if low <= hz <= high:
            return name
    return None


def cat_pair_diagnostic(uplink_hz: int | None, downlink_hz: int | None) -> tuple[bool, str]:
    """Report the *actual* chosen frequency pair; never assume SAT service from NORAD."""
    rx_band = cat_band(downlink_hz)
    tx_band = cat_band(uplink_hz)
    if downlink_hz is None:
        return False, "downlink ausente"
    if uplink_hz is None:
        return False, f"canal somente RX ({rx_band or 'banda desconhecida'}); sem uplink para SAT completo"
    if not rx_band or not tx_band:
        return False, f"faixa CAT não reconhecida (RX {rx_band or 'desconhecida'}, TX {tx_band or 'desconhecida'})"
    if rx_band == tx_band:
        return False, f"RX e TX estão ambos em {rx_band} (mesma banda)"
    return True, f"crossband válido (RX {rx_band}, TX {tx_band})"


# Fixed reference values from AMSAT SO-50 satellite information and current
# Live FM Satellites table, NOT derived from the order of SatNOGS API records.
# Frequencies are preloaded for CAT only; the application never keys PTT.
SO50_VOICE = {
    "name": "SO-50 · repetidor FM V/U (AMSAT)",
    "downlink": 436_795_000,
    "downlink_high": 436_795_000,
    "uplink": 145_850_000,
    "uplink_high": 145_850_000,
    "mode": "FM",
    "inverted": False,
    "uuid": "amsat-so50-fm-voice",
    "receive_only": False,
    "type": "Transceiver",
    "source": "AMSAT (frequências publicadas)",
}


def prioritized_transponders(norad: int | str, options: list[dict]) -> list[dict]:
    """Put verified SO-50 FM voice first; keep other SatNOGS modes selectable.

    The API may return telemetry channels or legacy/incorrect TX mappings
    before the voice repeater. A known-good profile avoids accidentally
    selecting those channels as the default Auto CAT pair.
    """
    result = list(options)
    if str(norad) == "27607":
        # Do not duplicate an equal or near-equal SatNOGS voice channel.
        result = [
            item for item in result
            if not (
                (item.get("uplink") is not None)
                and abs(int(item["uplink"]) - SO50_VOICE["uplink"]) <= 1500
                and abs(int(item["downlink"]) - SO50_VOICE["downlink"]) <= 1500
                and str(item.get("mode","")).upper().startswith("FM")
            )
        ]
        return [dict(SO50_VOICE), *result]
    # Other satellites: prefer the first actual two-way crossband entry
    # rather than automatically choosing a telemetry-only/same-band entry.
    suitable = [x for x in result if cat_pair_diagnostic(x.get("uplink"),x.get("downlink"))[0]]
    if suitable:
        chosen = suitable[0]
        return [chosen, *[x for x in result if x is not chosen]]
    return result
