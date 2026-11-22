"""v1.9.5: estilos FT-847, FT-817/818, TS-790 e IC-705 (fotos do operador, 22/11/2026)."""
from test_v171_radio_displays import run


def test_ft847_and_ft817_styles_render():
    run(r'''
        from sat_tool.qt_compat import QApplication
        from sat_tool.lcd import LcdDisplay, RADIO_MODELS, themes_for
        app = QApplication([])
        assert {"ft847", "ft817", "ts790", "ic705"} <= set(RADIO_MODELS)
        assert themes_for("ft847") == ("azul",) and themes_for("ft817") == ("âmbar", "laranja")
        for model in ("ft847", "ft817", "ts790", "ic705"):
            for extra in (dict(), dict(transmitting=True), dict(rx_only=True), dict(swapped=True)):
                d = LcdDisplay(model=model, theme="verde")
                d.set_state(rx_hz=436795120, rx_mode="FM", tx_hz=145850000, tx_mode="FM", sat_on=True, link="CAT",
                            auto=True, signal=18, power_w=25, los_s=25, sat_name="SO-50", **extra)
                img, keys = d.render_image(1300, 150, 1.0)
                assert set(keys) == {"swap", "rxonly", "type", "light"}, (model, extra)
                assert img.width() == 1300
        print("OK")
    ''')
