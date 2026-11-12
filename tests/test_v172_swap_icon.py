"""v1.7.2 (backlog 12/11/2026): ícone <> no topo do display troca MAIN e SUB."""
import os
import subprocess
import sys
import textwrap


def test_swap_icon_between_main_and_sub():
    source = textwrap.dedent(r'''
        from sat_tool import lcd
        from sat_tool.qt_compat import QApplication
        app = QApplication([])
        for model in ("matriz", "led7", "lcd7", "digital"):
            disp = lcd.LcdDisplay(model=model)
            disp.set_state(rx_hz=436795100, tx_hz=145850000)
            img, keys = disp.render_image(1000, 150, 1.0)
            r = keys.get("swap2")
            assert r is not None, (model, keys)
            assert abs(r.center().x() - 500) < 3 and r.top() < 30, (model, r)
            for name, other in keys.items():
                if name != "swap2" and hasattr(other, "intersects"):
                    assert not r.intersects(other), (model, name)
            disp.resize(1000, 150)
            disp._keys = keys
            assert disp.key_at(r.center()) == "swap2", model
    ''')
    r = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert r.returncode == 0, r.stdout + r.stderr
