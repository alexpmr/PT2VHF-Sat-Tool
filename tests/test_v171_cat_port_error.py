"""v1.7.1: porta CAT ausente/em uso com mensagem clara (sem confundir com sintonia bloqueada)."""
from sat_tool.cat import classify_port_error, port_error_text


def test_missing_port_is_explained():
    msg = "could not open port 'COM15': FileNotFoundError(2, 'O sistema não pode encontrar o arquivo especificado.')"
    assert classify_port_error(msg) == "missing"
    title, advice = port_error_text(msg, "COM15")
    assert title == "Porta CAT indisponível (COM15)"
    assert "driver" in advice and "Configurações → Rádio" in advice


def test_busy_and_other():
    assert classify_port_error("could not open port 'COM3': PermissionError(13, 'Acesso negado.')") == "busy"
    assert port_error_text("timeout esperando ID;")[0] == "Falha de conexão CAT"
