"""v1.6.0: pacotes APRS decodificados (posição, Mic-E, mensagem, telemetria) e locator."""
from sat_tool import aprs_info


def test_position_digipeater_distance_and_locator():
    pkt = aprs_info.parse("PT2VHF-7>APRS,ARISS*:!1554.00S/04756.00W-Teste SDR")
    summary, fields = aprs_info.describe(pkt, (-15.79, -47.88))
    assert fields["Digipeater usado"] == "ARISS" and fields["Posição"].endswith("(GH64ac)")
    assert "km" in fields["Distância/azimute"] and "Teste SDR" in summary


def test_message_status_and_telemetry():
    msg = aprs_info.parse("PY2XX>APRS,RS0ISS*::PT2VHF   :73 via ISS{12")
    _, f = aprs_info.describe(msg)
    assert f["Mensagem"] == "73 via ISS" and f["Destinatário"].strip() == "PT2VHF" and f["ID"] == "12"
    tlm = aprs_info.parse("PT2VHF-11>APRS:T#005,199,000,255,073,123,01101001")
    s, f = aprs_info.describe(tlm)
    assert "Telemetria #5" in s and "199.0" in f["Telemetria"]


def test_mic_e_and_non_aprs():
    mic = aprs_info.parse("PT2VHF-9>T5TQ1R,ARISS*:`(_fn\"Oj/]Teste Mic-E")
    assert mic and mic.get("format") == "mic-e" and "latitude" in mic
    assert aprs_info.parse("texto qualquer") is None
    assert aprs_info.latlon_to_maidenhead(-15.79, -47.88) == "GH64bf"
