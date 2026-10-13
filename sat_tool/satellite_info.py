"""Human-readable satellite parameters from CelesTrak and cached SatNOGS records."""
from __future__ import annotations
from math import isfinite


def orbital_characteristics(item: dict) -> dict:
    def number(v):
        try:
            x = float(v)
            return x if isfinite(x) else None
        except (TypeError, ValueError):
            return None
    tle = item.get('TLE_LINE2')
    if tle:
        inc = number(tle[8:16])
        ecc = number('0.' + tle[26:33].strip())
        motion = number(tle[52:63])
    else:
        inc = number(item.get('INCLINATION'))
        ecc = number(item.get('ECCENTRICITY'))
        motion = number(item.get('MEAN_MOTION'))
    period = 1440/motion if motion and motion>0 else None
    return {'name': str(item.get('OBJECT_NAME') or 'Sem nome'),
            'norad': str(item.get('NORAD_CAT_ID') or ''),
            'inclination_deg': inc, 'eccentricity': ecc,
            'period_min': period, 'epoch': str(item.get('EPOCH') or 'TLE / verificar época')}


def operational_characteristics(rows: list[dict]) -> dict:
    """Operational hints reflect community information, never imply guaranteed TX access."""
    active = [r for r in rows if str(r.get('status','')).lower() in ('', 'active') and r.get('alive') is not False]
    freq = sorted({round(float(r['downlink_low'])/1e6, 6) for r in active if r.get('downlink_low')})
    modes = sorted({str(r.get('mode')).upper() for r in active if r.get('mode')})
    kinds = sorted({str(r.get('type')) for r in active if r.get('type')})
    return {'active_channels': len(active), 'modes': modes, 'types': kinds,
            'downlinks_mhz': freq, 'status': 'Canais publicados' if active else 'Operação não confirmada'}


def characteristics_text(item: dict, rows: list[dict]):
    o = orbital_characteristics(item)
    op = operational_characteristics(rows)
    inc = f"{o['inclination_deg']:.2f}°" if o['inclination_deg'] is not None else '—'
    period = f"{o['period_min']:.1f} min" if o['period_min'] is not None else '—'
    ecc = f"{o['eccentricity']:.5f}" if o['eccentricity'] is not None else '—'
    modes = ', '.join(op['modes']) if op['modes'] else 'não informados'
    frequencies = ', '.join(f'{x:.3f}' for x in op['downlinks_mhz'][:6]) or 'não informadas'
    return (f"{o['name']}  •  NORAD {o['norad']}  •  Inclinação: {inc}  •  Período: {period}\n"
            f"Excentricidade: {ecc}  •  Modos: {modes}\n"
            f"Downlink (MHz): {frequencies}  •  {op['status']}")
