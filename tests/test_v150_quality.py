"""v1.5.0: qualidade da passagem em estrelas com passagens sintéticas."""
from datetime import datetime, timezone

import numpy as np

from sat_tool import quality


def synthetic(max_el, minutes, min_range, radial_peak=7000.0, sunlit=True):
    t = np.arange(0, minutes * 60 + 10, 10.0)
    x = (t - t[-1] / 2) / (t[-1] / 2)
    el = max_el * (1 - x ** 2)
    rng = min_range + 2000 * x ** 2
    radial = radial_peak * x
    return {"t": t, "el": el, "range_km": rng, "radial_m_s": radial, "sunlit": np.full(len(t), sunlit)}


WED_MORNING = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)


def q(samples, **kw):
    args = dict(norad="27607", mode="FM", downlink_hz=436_795_000, alive=True,
                local_start=WED_MORNING, min_elevation=10)
    args.update(kw)
    return quality.score_pass(samples, **args)


def test_high_long_pass_beats_low_short_pass():
    good = q(synthetic(70, 12, 600))
    bad = q(synthetic(12, 4, 2400))
    assert good.stars >= 4 and bad.stars <= 2
    assert "elevação máxima 70°" in good.tooltip


def test_fast_doppler_penalizes_ssb_more_than_fm():
    s = synthetic(80, 10, 500, radial_peak=7200.0)
    assert q(s, mode="USB").score < q(s, mode="FM").score


def test_ao7_needs_sunlight_and_dead_satellite_is_penalized():
    dark = synthetic(60, 12, 700, sunlit=False)
    lit = synthetic(60, 12, 700, sunlit=True)
    assert q(dark, norad="7530", mode="USB").score < q(lit, norad="7530", mode="USB").score
    assert any("AO-7" in r for r in q(dark, norad="7530", mode="USB").reasons)
    assert q(lit, alive=False).score < q(lit).score


def test_weekend_evening_fm_crowding_and_stars_range():
    s = synthetic(50, 10, 900)
    sat_evening = datetime(2026, 11, 7, 20, 0)
    assert q(s, local_start=sat_evening).score < q(s).score
    for case in (synthetic(5, 1, 3000), synthetic(89, 15, 400)):
        assert 1 <= q(case).stars <= 5
    assert q(synthetic(89, 15, 400)).label == "★★★★★" and "☆" not in q(synthetic(30, 6, 900)).label


def test_shadow_geometry():
    sun = np.array([1.0, 0, 0])
    assert quality.in_shadow(np.array([-7000.0, 0, 0]), sun)
    assert not quality.in_shadow(np.array([7000.0, 0, 0]), sun)
    assert not quality.in_shadow(np.array([-7000.0, 8000.0, 0]), sun)
