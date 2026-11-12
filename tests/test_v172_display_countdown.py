"""v1.7.2 (backlog 12/11/2026): contagem da passagem no display em segmentos, ao lado da frequência MAIN."""
from sat_tool.lcd import SEG, _Seven, countdown_text


def test_seven_segment_supports_countdown_glyphs():
    assert countdown_text(342) == "5:42" and SEG["H"] == "bcefg"
    # ':' ocupa uma célula estreita (não uma célula de dígito inteira)
    st = _Seven.__new__(_Seven)
    assert st.digits_w("5:42", 40) < st.digits_w("5042", 40)


def test_ts2000_layouts_draw_big_countdown_instead_of_small_tag():
    import os, subprocess, sys, textwrap
    source = textwrap.dedent(r"""
        from sat_tool.qt_compat import QApplication
        from sat_tool import lcd
        app = QApplication([])
        drawn = []
        for model in ("matriz", "led7", "lcd7", "digital"):
            d = lcd.LcdDisplay(model=model); d.resize(900, 150)
            for kw in (dict(los_s=342), dict(aos_s=1500), {}):
                calls = []
                d.set_state(rx_hz=436795100, rx_mode="FM", tx_hz=145850000, tx_mode="FM", visible=True,
                            elevation=38, los_s=kw.get("los_s"), aos_s=kw.get("aos_s"))
                for cls in (lcd._Style, lcd._Matrix):
                    o = cls.tag
                    def spy(self, x, y, s, *a, _o=o, **k):
                        calls.append(s); return _o(self, x, y, s, *a, **k)
                    cls.tag = spy
                d.render_image(900, 150, 1.0)
                import importlib
                if "los_s" in kw:
                    assert "LOS" in calls and not any(c.startswith("LOS ") for c in calls), (model, calls)
                elif "aos_s" in kw:
                    assert "AOS" in calls and not any(c.startswith("AOS ") for c in calls), (model, calls)
                else:
                    assert "LOS" not in calls and "AOS" not in calls
                importlib.reload(lcd)   # desfaz o espião
                d = lcd.LcdDisplay(model=model); d.resize(900, 150)
    """)
    r = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stdout + r.stderr


def test_countdown_units_h_m_s_half_height():
    """v1.8.0: contagem grande com H, M e S na metade da altura dos números."""
    from sat_tool.lcd import countdown_parts, _Style
    assert countdown_parts(3942) == [("01", "H"), ("05", "M"), ("42", "S")]
    assert countdown_parts(342) == [("05", "M"), ("42", "S")]
    assert countdown_parts(None) == []
    assert hasattr(_Style, "countdown") and hasattr(_Style, "unit")
