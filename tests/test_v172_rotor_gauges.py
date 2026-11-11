"""v1.7.2: dois gauges do rotor (direção e elevação) com real × alvo em tempo real."""
import os
import subprocess
import sys
import textwrap


def test_two_gauges_follow_real_and_target():
    source = textwrap.dedent(r'''
        from sat_tool.qt_compat import QApplication
        from sat_tool.rotor_widgets import RotorCompass, AzimuthGauge, ElevationGauge
        app = QApplication([])
        w = RotorCompass(size=76); w.show(); app.processEvents()
        assert isinstance(w.az_gauge, AzimuthGauge) and isinstance(w.el_gauge, ElevationGauge)
        w.set_values((215.0, 32.0), (220.0, 35.0), True)
        assert (w.az_gauge.real, w.az_gauge.target) == (215.0, 220.0)
        assert (w.el_gauge.real, w.el_gauge.target, w.el_gauge.flip) == (32.0, 35.0, True)
        assert "Direção" in w.az_gauge.accessibleName() and "215°" in w.az_gauge.accessibleName()
        assert "Elevação" in w.el_gauge.accessibleName() and "32°" in w.el_gauge.accessibleName()
        assert w.accessibleName().startswith("Rotor real AZ 215° EL 32°")
        assert not w.grab().isNull()
        w.set_values(None, None)
        assert w.az_gauge.real is None and w.el_gauge.target is None
        assert not w.grab().isNull()
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=60,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
