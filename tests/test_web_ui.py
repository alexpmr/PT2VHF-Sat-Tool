"""Safety and live HTTP tests for the read-only local/LAN dashboard."""
from __future__ import annotations
import http.client
import json
import socket
from urllib.parse import urlsplit, parse_qs

import pytest
from sat_tool.web_ui import LocalStatusServer, HTML


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(port, path, method="GET", headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        status = response.status
        headers_dict = dict(response.getheaders())
        body = response.read()
        return status, headers_dict, body
    finally:
        connection.close()


def test_dashboard_http_is_read_only_and_no_cat_routes(tmp_path):
    map_file = tmp_path / "map.html"
    map_file.write_text("<!doctype html><title>offline map</title>", encoding="utf-8")
    server = LocalStatusServer(lan=False, port=free_port(), map_path=map_file)
    server.publish({"version": "1.3.18", "satellite": "SO-50",
                    "cat_state": "desconectado", "passes": [],
                    "metrics": {"Elevação": "12°"}})
    try:
        server.start()
        status, _, payload = call(server.port, "/")
        assert status == 200 and b"PT2VHF SAT TOOL" in payload
        status, headers, payload = call(server.port, "/api/status")
        data = json.loads(payload)
        assert status == 200 and data["satellite"] == "SO-50"
        assert headers["Referrer-Policy"] == "no-referrer"
        status, _, payload = call(server.port, "/map")
        assert status == 200 and b"offline map" in payload
        for path in ("/api/cat", "/api/ptt", "/api/settings", "/etc/passwd"):
            assert call(server.port, path)[0] == 404
        assert call(server.port, "/api/status", method="POST")[0] == 405
    finally:
        server.stop()


def test_lan_requires_random_token_and_uses_http_only_cookie(tmp_path):
    server = LocalStatusServer(lan=True, port=free_port(), map_path=tmp_path / "map.html")
    try:
        server.start()
        assert call(server.port, "/")[0] == 401
        assert call(server.port, "/api/status")[0] == 401
        assert call(server.port, "/?key=wrong")[0] == 401
        status, headers, _ = call(server.port, "/?key="+server.key)
        assert status == 303 and headers["Location"] == "/"
        cookie = headers["Set-Cookie"]
        assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
        token_cookie = cookie.split(";", 1)[0]
        assert call(server.port, "/api/status", headers={"Cookie": token_cookie})[0] == 200
        assert call(server.port, "/api/status", method="POST")[0] == 405
    finally:
        server.stop()


@pytest.mark.parametrize("port", [0, -1, 1023, 65536])
def test_reject_privileged_or_invalid_port(port):
    with pytest.raises(ValueError):
        LocalStatusServer(port=port)


def test_gui_web_requires_explicit_opt_in_and_never_writes_cat():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "sat_tool" / "app.py").read_text(encoding="utf-8")
    assert "web_allow_lan" in source
    assert "self.web_lan=QCheckBox(" in source
    assert "self.web_server.stop()" in source
    assert "self.publish_web_snapshot()" in source
    assert "LocalStatusServer(" in source
    assert "cat_auto_select" not in HTML
    assert "/api/status" in HTML
