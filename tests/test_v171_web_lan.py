"""v1.7.1: acesso pela rede como no APRS Client — IPs da LAN, firewall, presença, sessões e controles opcionais."""
from __future__ import annotations
import http.client
import json
import os
import socket
import subprocess
import sys
import textwrap
import time

import pytest
from sat_tool import web_ui
from sat_tool.web_ui import LocalStatusServer, pin_hash


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(port, path, method="GET", headers=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    finally:
        c.close()


def control(port, payload, cookie="", extra=None):
    headers = {"Content-Type": "application/json", "X-PT2VHF": "1"}
    if cookie:
        headers["Cookie"] = cookie
    headers.update(extra or {})
    return call(port, "/api/control", "POST", headers, json.dumps(payload).encode())


def login(server):
    status, headers, _ = call(server.port, "/?key=" + server.key)
    assert status == 303
    return headers["Set-Cookie"].split(";", 1)[0]


def test_public_addresses_are_refused_and_private_ones_allowed():
    for ip in ("8.8.8.8", "200.160.2.3", "2001:4860::8888", "not-an-ip", "0.0.0.0"):
        assert not web_ui.client_allowed(ip), ip
    for ip in ("127.0.0.1", "192.168.0.20", "10.1.2.3", "172.16.5.4", "::1", "::ffff:192.168.1.5"):
        assert web_ui.client_allowed(ip), ip


def test_lan_candidates_are_private_ipv4_only_and_unique(monkeypatch):
    monkeypatch.setattr(socket, "gethostbyname_ex", lambda h: (h, [], ["8.8.8.8", "192.168.0.10", "127.0.0.1",
                                                                        "169.254.1.1", "10.0.0.7", "192.168.0.10"]))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("172.20.0.2", 0))])
    got = web_ui.lan_ipv4_candidates(max_age=0)
    assert "8.8.8.8" not in got and "127.0.0.1" not in got and "169.254.1.1" not in got
    assert {"192.168.0.10", "10.0.0.7", "172.20.0.2"} <= set(got) and len(got) == len(set(got))
    # resolução lenta do nome da máquina não se repete a cada atualização do diagnóstico
    monkeypatch.setattr(socket, "gethostbyname_ex", lambda h: (_ for _ in ()).throw(AssertionError("sem cache")))
    assert web_ui.lan_ipv4_candidates() == got


def test_firewall_rule_is_port_only_private_profile_and_local_subnet():
    args = web_ui.firewall_rule_args(8094)
    assert "localport=8094" in args and "profile=private" in args and "remoteip=localsubnet" in args
    assert "dir=in" in args and "protocol=TCP" in args
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    ok, msg = web_ui.request_windows_firewall_rule(8094, runner=runner, platform="win32")
    assert ok and "8094" in msg and "RunAs" in calls[0][-1] and "netsh.exe" in calls[0][-1]
    assert web_ui.firewall_rule_present(8094, runner=runner, platform="win32") is True
    deny = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "")
    assert web_ui.request_windows_firewall_rule(8094, runner=deny, platform="win32")[0] is False
    assert web_ui.firewall_rule_present(8094, runner=deny, platform="win32") is False
    assert web_ui.request_windows_firewall_rule(8094, runner=runner, platform="linux")[0] is False
    assert web_ui.firewall_rule_present(8094, runner=runner, platform="linux") is None


def test_remote_presence_and_last_access_diagnostics():
    s = LocalStatusServer(lan=True, port=free_port())
    s.note_remote_request("127.0.0.1")                  # a própria máquina não conta como remoto
    assert s.diagnostics()["last_remote"] == "" and s.remote_active() == []
    s.note_remote_request("192.168.0.31")              # heartbeat de outro computador
    d = s.diagnostics()
    assert d["remote_active"] == ["192.168.0.31"] and d["last_remote"].startswith("192.168.0.31 às ")
    s._presence["192.168.0.31"] = time.monotonic() - 60
    assert s.remote_active() == [] and s.diagnostics()["last_remote"].startswith("192.168.0.31")


def test_validate_control_never_accepts_ptt_or_raw_cat():
    for bad in ("ptt", "PTT_ON", "tx", "transmit", "cat_raw", "send_command"):
        with pytest.raises(PermissionError):
            web_ui.validate_control({"action": bad, "value": True})
    with pytest.raises(ValueError):
        web_ui.validate_control({"action": "reboot"})
    with pytest.raises(ValueError):
        web_ui.validate_control({"action": "auto_cat", "value": "sim"})
    assert web_ui.validate_control({"action": "rotor_stop", "value": 123}) == ("rotor_stop", None)
    assert web_ui.validate_control({"action": "select_satellite", "value": " 27607 "}) == ("select_satellite", "27607")
    assert not any("ptt" in a or a == "tx" for a in web_ui.CONTROL_ACTIONS)


def test_controls_blocked_when_disabled_and_need_pin_header_and_session(tmp_path):
    salt = "abc"
    s = LocalStatusServer(lan=True, port=free_port(), map_path=tmp_path / "m.html",
                          controls=False, pin_hash_value=pin_hash("2468", salt), pin_salt=salt)
    try:
        s.start()
        cookie = login(s)
        assert control(s.port, {"action": "rotor_stop", "pin": "2468"}, cookie)[0] == 403   # desligado
        s.controls = True
        assert control(s.port, {"action": "rotor_stop", "pin": "2468"})[0] == 401          # sem sessão
        st, _, body = control(s.port, {"action": "ptt", "value": True, "pin": "2468"}, cookie)
        assert st == 403 and "PTT" in json.loads(body)["error"]
        assert control(s.port, {"action": "rotor_stop", "pin": "0000"}, cookie)[0] == 403   # PIN errado
        st, _, _ = call(s.port, "/api/control", "POST", {"Cookie": cookie, "Content-Type": "application/json"},
                        json.dumps({"action": "rotor_stop", "pin": "2468"}).encode())
        assert st == 403                                                                   # sem cabeçalho próprio
        assert control(s.port, {"action": "rotor_stop", "pin": "2468"}, cookie,
                       {"Origin": "http://evil.example"})[0] == 403                        # outra origem
        assert s.drain_commands() == []
        st, _, _ = control(s.port, {"action": "select_satellite", "value": "27607", "pin": "2468"}, cookie)
        assert st == 202
        assert s.drain_commands() == [{"action": "select_satellite", "value": "27607", "ip": "127.0.0.1"}]
        data = json.loads(call(s.port, "/api/status", headers={"Cookie": cookie})[2])
        assert data["controls"] is True
        assert any("pediu select_satellite" in e for e in s.events)
        assert call(s.port, "/api/ptt", "POST", {"Cookie": cookie})[0] == 405
        assert call(s.port, "/api/ptt", headers={"Cookie": cookie})[0] == 404
    finally:
        s.stop()


def test_pin_lockout_after_repeated_failures():
    s = LocalStatusServer(port=free_port(), controls=True, pin_hash_value=pin_hash("1357", "x"), pin_salt="x")
    for _ in range(web_ui.PIN_MAX_FAILS):
        assert s.check_pin("192.168.0.9", "0000") == "wrong"
    assert s.check_pin("192.168.0.9", "1357") == "locked"
    assert s.check_pin("192.168.0.10", "1357") == "ok"
    assert LocalStatusServer(port=free_port(), controls=True).check_pin("1.2.3.4", "1357") == "wrong"  # sem PIN salvo


def test_rotating_key_drops_old_links_and_sessions_and_sessions_expire(tmp_path):
    s = LocalStatusServer(lan=True, port=free_port(), map_path=tmp_path / "m.html")
    try:
        s.start()
        old_key, cookie = s.key, login(s)
        assert call(s.port, "/api/status", headers={"Cookie": cookie})[0] == 200
        s.rotate_key()
        assert call(s.port, "/api/status", headers={"Cookie": cookie})[0] == 401
        assert call(s.port, "/?key=" + old_key)[0] == 401
        cookie = login(s)
        assert "Max-Age=28800" in call(s.port, "/?key=" + s.key)[1]["Set-Cookie"]
        token = cookie.split("=", 1)[1]
        s._sessions[token] = time.monotonic() - 1
        assert call(s.port, "/api/status", headers={"Cookie": cookie})[0] == 401
    finally:
        s.stop()


def test_display_png_route(tmp_path):
    s = LocalStatusServer(port=free_port(), map_path=tmp_path / "m.html")
    try:
        s.start()
        assert call(s.port, "/api/display.png")[0] == 404
        s.publish_display(b"\x89PNG fake")
        st, h, body = call(s.port, "/api/display.png")
        assert st == 200 and h["Content-Type"] == "image/png" and body.startswith(b"\x89PNG")
        assert s.browser_recent()
    finally:
        s.stop()


def test_gui_settings_controls_and_command_queue():
    source = textwrap.dedent(r'''
        import tempfile
        from pathlib import Path
        from sat_tool import app as gui
        from sat_tool.config import Config
        class FakeWeb(gui.QWidget):
            def setHtml(self,*a,**k):pass
            def page(self):return self
            def runJavaScript(self,*a,**k):pass
            def reload(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda d:[]
        gui.MainWindow.background=lambda self,key,fn:None
        gui.MainWindow.check_for_updates=lambda self:None
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); w.show(); app.processEvents()
            assert w.config.values["web_controls"] is False            # desligado por padrão
            w.web_controls.setChecked(True)                            # sem PIN: não liga
            assert w.web_controls.isChecked() is False and w.config.values["web_controls"] is False
            w.web_pin.setText("12"); w.web_save_pin()
            assert not w.config.values["web_pin_hash"]
            w.web_pin.setText("2468"); w.web_save_pin()
            assert w.config.values["web_pin_hash"] and "2468" not in str(w.config.values)
            import socket
            s=socket.socket(); s.bind(("127.0.0.1",0)); port=s.getsockname()[1]; s.close()
            w.web_port.setValue(port)
            w.web_controls.setChecked(True)
            w.web_enabled.setChecked(True); app.processEvents()
            assert w.web_server is not None and w.web_server.controls
            assert "escutando na porta" in w.web_diag.text()
            # pedidos do navegador são aplicados no thread da janela; PTT não tem ação
            w.web_server.commands.put({"action":"rx_only","value":True,"ip":"192.168.0.5"})
            w.web_server.commands.put({"action":"ptt","value":True,"ip":"192.168.0.5"})
            w.web_tick(); app.processEvents()
            assert w.config.values["rx_only"] is True
            assert w.apply_web_command({"action":"ptt","value":True,"ip":"x"}) is False
            w.web_server.controls=False
            assert w.apply_web_command({"action":"rx_only","value":False,"ip":"x"}) is False
            assert w.config.values["rx_only"] is True
            w.web_server.controls=True
            w.web_server.last_request=__import__("time").monotonic()
            w.publish_web_snapshot(force=True)
            snap=w.web_server._snapshot
            assert snap["rotor"]=={"enabled":False} and "satellites" in snap and snap["rx_only"] is True
            assert w.web_server._display_png.startswith(b"\x89PNG") and snap["display"]
            w.web_rotate_key()
            w.web_enabled.setChecked(False); app.processEvents()
            assert w.web_server is None and "parado" in w.web_diag.text()
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
