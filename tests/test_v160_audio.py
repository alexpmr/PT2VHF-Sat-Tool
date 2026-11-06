"""v1.6.0: áudio contínuo — jitter buffer, deriva de relógio e GUI ocupada."""
import numpy as np

from sat_tool.audio_ring import AudioRing, RATE


def test_ring_plays_continuously_with_clock_drift_and_bursty_producer():
    ring = AudioRing()
    produced = consumed = 0
    # 10 min simulados: produtor 0,2 % mais rápido (deriva) em rajadas de 100 ms; consumidor a cada 20 ms.
    block = int(RATE * 0.1 * 1.002)
    t = 0
    while t < 600_000:  # ms
        if t % 100 == 0:
            ring.push(np.ones(block, dtype=np.float32))
            produced += block
        out = ring.pull(int(RATE * 0.02))
        consumed += len(out)
        t += 20
    assert ring.underruns <= 1          # só o início (antes de abastecer)
    assert ring.level_ms < 1600         # nunca acumula atraso ilimitado
    assert ring.adjustments > 0         # deriva compensada


def test_ring_silence_before_prime_and_recovers():
    ring = AudioRing(target_ms=100)
    assert not ring.pull(480).any()
    ring.push(np.ones(RATE // 10, dtype=np.float32))
    assert ring.pull(480).all()
