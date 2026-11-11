"""Satellite dashboard for the browser: localhost, or explicit token-protected LAN.

v1.7.1 (modelo do PT2VHF APRS Client):
* lista de todos os IPv4 privados da máquina, regra opcional no firewall do Windows, diagnóstico (servidor
  escutando, último acesso remoto, navegador remoto ativo agora por heartbeat);
* sessões com validade, chave renovável, só clientes de rede privada (IP público recusado);
* controles remotos **opcionais** (desligados por padrão) com PIN da estação: satélite, Auto CAT, A/B, RX ONLY,
  rastrear/estacionar/PARAR do rotor. **Nunca PTT/TX** — não existe rota nem ação para isso.

Nunca chamar CAT, PTT ou métodos Qt numa thread HTTP: os comandos vão para uma fila que a janela principal
esvazia no próprio thread (``drain_commands``).
"""
from __future__ import annotations
import collections
import hashlib
import hmac
import ipaddress
import json
import os
import queue
import secrets
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

COOKIE = "PT2VHFSession"
PRESENCE_SECONDS = 10.0
MAX_BODY = 4096
PIN_MAX_FAILS = 5
PIN_LOCK_SECONDS = 300.0

# Ações que um navegador pode pedir (com "Permitir controle pela rede" ligado e PIN correto).
CONTROL_ACTIONS = {
    "select_satellite": "str",
    "auto_cat": "bool",
    "ab": None,
    "rx_only": "bool",
    "rotor_track": "bool",
    "rotor_park": None,
    "rotor_stop": None,
}
FORBIDDEN_WORDS = ("ptt", "tx", "transmit", "key", "cat_raw", "command")

HTML = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PT2VHF Sat Tool · Web</title><style>
:root{color-scheme:dark;font:14px Segoe UI,Arial,sans-serif;color:#e8f2fa;background:#081726}
*{box-sizing:border-box}body{margin:0}header{background:#102b43;padding:12px 18px;border-bottom:1px solid #3a627d;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
strong{font-size:1.15rem}#time{margin-left:auto;color:#98d8ec;font-variant-numeric:tabular-nums}
main{max-width:1440px;margin:auto;padding:12px;display:grid;gap:12px}
.card{background:#10273c;border:1px solid #31516a;border-radius:9px;padding:12px;min-width:0}
h2{color:#7eebd5;font-size:1rem;margin:0 0 10px}.data{font-weight:750;font-size:1.1rem;overflow-wrap:anywhere}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
@media(min-width:900px){.content{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(290px,1fr);gap:12px}}
#map{width:100%;height:365px;border:0;border-radius:6px}.table{overflow-x:auto}
table{width:100%;border-collapse:collapse}th,td{padding:7px 10px;border-bottom:1px solid #35536a;text-align:left;white-space:nowrap}
th{color:#9cdcec}.muted{color:#a8c7d6;font-size:.85rem}footer{text-align:center;color:#98b4c3;padding:14px;font-size:.83rem}
.chip{padding:4px 8px;border-radius:6px;background:#733c3c;color:#ffd0c4}.chip.ok{background:#125743;color:#a4f7c9}.chip.warn{background:#6f5727;color:#ffe0a6}
#display{width:100%;image-rendering:pixelated;border-radius:6px;background:#000;display:block}
#rotorpos{font-size:1.6rem;font-weight:900;color:#5af08a;font-variant-numeric:tabular-nums}
#controls{display:none}#controls.on{display:block}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0}
button,select,input{font:inherit;border-radius:6px;border:1px solid #3d6a88;background:#173a55;color:#e8f2fa;padding:7px 12px}
button:hover{background:#1f4d70}button.stop{background:#b3261e;border-color:#ff8a80;font-weight:800}
button.on{background:#125743;border-color:#5af08a}select{max-width:100%}#pin{width:9em}
#ctlmsg{min-height:1.2em}
@media(max-width:540px){#map{height:250px}main{padding:8px}}
</style></head><body>
<header><strong>PT2VHF SAT TOOL <span id="version"></span></strong><span id="cat" class="chip">CAT</span><span id="rot" class="chip">ROTOR</span><span class="muted" id="mode">Painel Web</span><span id="time">—</span></header>
<main><section class="card"><h2>Satélite selecionado</h2><div class="data" id="satellite">Aguardando aplicação</div><div class="muted" id="catalog">—</div></section>
<section class="card" id="displaycard"><h2>Display do rádio</h2><img id="display" alt="Display do rádio"></section>
<section class="cards"><div class="card"><h2>RX / DOWNLINK</h2><div class="data" id="rx">—</div></div><div class="card"><h2>TX / UPLINK</h2><div class="data" id="tx">—</div></div><div class="card"><h2>Próxima passagem</h2><div class="data" id="nextpass">—</div></div>
<div class="card"><h2>Rotor</h2><div id="rotorpos">—</div><div class="muted" id="rotortarget">—</div><div class="muted" id="rotorstate">—</div></div></section>
<section class="card" id="controls"><h2>Controle pela rede · sem PTT</h2>
<div class="row"><label>PIN da estação <input id="pin" type="password" inputmode="numeric" autocomplete="off" maxlength="12"></label><span class="muted">O PIN fica só nesta aba do navegador.</span></div>
<div class="row"><select id="satsel" aria-label="Satélite"></select><button data-act="select_satellite">Selecionar satélite</button></div>
<div class="row"><button id="autocat" data-act="auto_cat">Auto CAT</button><button data-act="ab">A/B</button><button id="rxonly" data-act="rx_only">RX ONLY</button></div>
<div class="row"><button id="rtrack" data-act="rotor_track">Rastrear passagem</button><button data-act="rotor_park">Estacionar</button><button class="stop" data-act="rotor_stop">PARAR ROTOR</button></div>
<div class="muted" id="ctlmsg"></div></section>
<div class="content"><section class="card"><h2>Mapa orbital · trajetória e estação</h2><iframe id="map" src="/map" title="Mapa vetorial offline"></iframe></section>
<section class="card"><h2>Telemetria orbital</h2><div id="metrics"></div><p id="visibility" class="muted">—</p><p id="catdetail" class="muted"></p></section></div>
<section class="card"><h2>Próximas passagens</h2><div class="table"><table><thead><tr><th>AOS local</th><th>TCA local</th><th>LOS local</th><th>Duração</th><th>Máx °</th><th>Qualidade</th><th>Modos</th></tr></thead><tbody id="passes"></tbody></table></div></section>
<section class="card"><h2>Telemetria decodificada · APRS</h2><div class="table"><table><thead><tr><th>UTC</th><th>Origem</th><th>APRS / quadro</th></tr></thead><tbody id="aprs"></tbody></table></div></section></main>
<footer>PT2VHF.com · O PTT/TX nunca é acionado pela rede. HTTP na LAN não é criptografado: não exponha a porta à Internet.</footer>
<script>
(function(){"use strict";const el=id=>document.getElementById(id);
let previous=null,stamp=0;function value(id,v){el(id).textContent=String(v==null?"—":v)}
function chip(id,text,cls){const c=el(id);c.textContent=text;c.className="chip "+(cls||"")}
function rows(id,list,keys){const tb=el(id);tb.replaceChildren();(list||[]).forEach(r=>{const tr=document.createElement("tr");
keys.forEach(k=>{const td=document.createElement("td");td.textContent=r[k]||"—";tr.appendChild(td)});tb.appendChild(tr)})}
function render(s){previous=s;value("version","v"+(s.version||""));value("time",s.utc);
value("satellite",s.satellite);value("catalog",String(s.catalog_count||0)+" satélites OMM/TLE");
value("rx",s.rx);value("tx",s.tx);value("nextpass",s.nextpass);value("visibility",s.visibility);value("catdetail",s.cat_detail);
chip("cat","CAT "+(s.cat_state||"desconectado"),s.cat_state==="conectado"?"ok":s.cat_state==="degradado"?"warn":"");
const r=s.rotor||{};if(r.enabled){el("rot").style.display="";chip("rot","ROTOR "+(r.state||""),r.connected?"ok":"");value("rotorpos",r.position);value("rotortarget",r.target);value("rotorstate",r.status)}
else{el("rot").style.display="none";value("rotorpos","—");value("rotortarget","Rotor desativado");value("rotorstate","")}
value("mode",s.controls?"Painel Web · controle pela rede habilitado":"Painel Web de consulta");
const m=el("metrics");m.replaceChildren();Object.entries(s.metrics||{}).forEach(([k,v])=>{const p=document.createElement("p");p.textContent=k+": "+v;m.appendChild(p)});
rows("passes",s.passes,["aos","tca","los","duration","max_el","quality","modes"]);rows("aprs",s.aprs,["utc","source","text"]);
if(s.display){el("displaycard").style.display="";if(s.display!==stamp){stamp=s.display;el("display").src="/api/display.png?t="+encodeURIComponent(s.display)}}else{el("displaycard").style.display="none"}
el("controls").classList.toggle("on",!!s.controls);if(s.controls){const sel=el("satsel");const want=JSON.stringify(s.satellites||[]);
if(sel.dataset.list!==want){sel.dataset.list=want;sel.replaceChildren();(s.satellites||[]).forEach(o=>{const op=document.createElement("option");op.value=o.id;op.textContent=o.name;sel.appendChild(op)})}
if(document.activeElement!==sel)sel.value=s.satellite_id||"";el("autocat").classList.toggle("on",!!s.auto_cat);el("rxonly").classList.toggle("on",!!s.rx_only);
el("rtrack").classList.toggle("on",!!r.tracking);el("rtrack").disabled=!r.enabled}
try{const f=el("map");if(f.contentWindow&&typeof f.contentWindow.updateOrbit==="function"&&s.orbit){f.contentWindow.updateOrbit(s.orbit)}}catch(e){}}
el("map").addEventListener("load",()=>{if(previous)render(previous)});
try{el("pin").value=sessionStorage.getItem("pt2vhf-pin")||""}catch(e){}
el("pin").addEventListener("change",()=>{try{sessionStorage.setItem("pt2vhf-pin",el("pin").value)}catch(e){}});
async function act(action){const s=previous||{};let v=null;
if(action==="select_satellite")v=el("satsel").value;else if(action==="auto_cat")v=!s.auto_cat;else if(action==="rx_only")v=!s.rx_only;else if(action==="rotor_track")v=!((s.rotor||{}).tracking);
try{const r=await fetch("/api/control",{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json","X-PT2VHF":"1"},body:JSON.stringify({action:action,value:v,pin:el("pin").value})});
const j=await r.json().catch(()=>({}));value("ctlmsg",r.ok?"Pedido enviado: "+action:(j.error||("HTTP "+r.status)));setTimeout(refresh,400)}catch(e){value("ctlmsg","Sem acesso: "+e.message)}}
document.querySelectorAll("button[data-act]").forEach(b=>b.addEventListener("click",()=>act(b.dataset.act)));
async function refresh(){try{const r=await fetch("/api/status",{cache:"no-store"});if(!r.ok)throw Error("HTTP "+r.status);render(await r.json())}catch(e){value("time","Sem acesso: "+e.message)}}
refresh();setInterval(refresh,1500);
})();
</script></body></html>"""


def _private_ipv4(raw):
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return False
    return ip.version == 4 and ip.is_private and not ip.is_loopback and not ip.is_link_local


_LAN_CACHE = [0.0, []]


def lan_ipv4_candidates(max_age=30.0):
    """Todos os IPv4 privados desta máquina (Wi-Fi, cabo, VPN de casa), o da rota padrão primeiro.

    Guardado por `max_age` s: a resolução do nome da máquina pode levar vários segundos (ex.: macOS sem DNS
    local) e o diagnóstico é atualizado na janela a cada 2 s."""
    now = time.monotonic()
    if max_age and _LAN_CACHE[0] and now - _LAN_CACHE[0] < max_age:
        return list(_LAN_CACHE[1])
    found = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        found.append(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()
    try:
        found.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    out = []
    for raw in found:
        if _private_ipv4(raw) and raw not in out:
            out.append(raw)
    _LAN_CACHE[0], _LAN_CACHE[1] = time.monotonic(), list(out)
    return out


def detect_lan_ipv4():
    c = lan_ipv4_candidates()
    return c[0] if c else ""


def client_allowed(raw):
    """Só rede privada ou a própria máquina; IP público (ou inválido) é recusado."""
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return bool(ip.is_loopback or (ip.is_private and not ip.is_unspecified))


def pin_hash(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", str(pin).encode("utf-8"), str(salt).encode("utf-8"), 120_000).hex()


def valid_pin(pin):
    pin = str(pin or "")
    return pin.isdigit() and 4 <= len(pin) <= 12


def validate_control(payload):
    """Confere a ação pedida pelo navegador. Devolve (ação, valor) ou levanta ValueError/PermissionError."""
    if not isinstance(payload, dict):
        raise ValueError("Pedido inválido")
    action = str(payload.get("action", "")).strip().lower()
    if action not in CONTROL_ACTIONS:
        if any(word in action for word in FORBIDDEN_WORDS):
            raise PermissionError("PTT/TX e comandos diretos ao rádio nunca são aceitos pela rede")
        raise ValueError("Ação desconhecida")
    kind, value = CONTROL_ACTIONS[action], payload.get("value")
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError("Valor inválido")
    elif kind == "str":
        value = str(value or "").strip()
        if not value or len(value) > 64:
            raise ValueError("Satélite inválido")
    else:
        value = None
    return action, value


# ---------- firewall do Windows ----------
def firewall_rule_name(port):
    return f"PT2VHF Sat Tool Web (TCP {int(port)})"


def firewall_rule_args(port):
    """Regra de entrada só para a porta, perfil Privado e só da sub-rede local."""
    return ["advfirewall", "firewall", "add", "rule", f"name={firewall_rule_name(port)}", "dir=in",
            "action=allow", "protocol=TCP", f"localport={int(port)}", "profile=private", "remoteip=localsubnet"]


def _hidden():
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def firewall_rule_present(port, runner=subprocess.run, platform=None):
    """True/False no Windows; None onde não se aplica ou não foi possível consultar."""
    if (platform or sys.platform) != "win32":
        return None
    try:
        r = runner(["netsh", "advfirewall", "firewall", "show", "rule", f"name={firewall_rule_name(port)}"],
                   capture_output=True, text=True, timeout=10, **_hidden())
    except (OSError, subprocess.SubprocessError):
        return None
    return r.returncode == 0


def request_windows_firewall_rule(port, runner=subprocess.run, platform=None):
    """Pede ao Windows (UAC) para criar a regra. Devolve (ok, mensagem)."""
    if (platform or sys.platform) != "win32":
        return False, "A regra de firewall automática só existe no Windows."
    args = ",".join("'" + a.replace("'", "''") + "'" for a in firewall_rule_args(port))
    ps = (f"$p = Start-Process -FilePath 'netsh.exe' -ArgumentList {args} -Verb RunAs -Wait -PassThru "
          "-WindowStyle Hidden; exit $p.ExitCode")
    try:
        r = runner(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                   capture_output=True, text=True, timeout=120, **_hidden())
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Não foi possível pedir a liberação: {exc}"
    if r.returncode == 0:
        return True, f"Porta TCP {int(port)} liberada no firewall (perfil Privado, só a rede local)."
    return False, "O Windows não criou a regra (permissão negada no UAC ou erro do netsh)."


class LocalStatusServer:
    """Servidor HTTP do painel. Sem controles por padrão; nunca há rota de PTT/TX."""

    def __init__(self, lan=False, port=8094, map_path=None, controls=False, pin_hash_value="", pin_salt="",
                 session_hours=8):
        self.lan, self.port = bool(lan), int(port)
        if not 1024 <= self.port <= 65535:
            raise ValueError("Porta TCP inválida (1024 a 65535)")
        self.key = secrets.token_urlsafe(32)
        self.map_path = Path(map_path or Path(__file__).with_name("map.html"))
        self.controls = bool(controls)
        self.pin_hash_value, self.pin_salt = str(pin_hash_value or ""), str(pin_salt or "")
        self.session_seconds = max(1, int(session_hours)) * 3600
        self._httpd = None
        self._thread = None
        self._lock = threading.Lock()
        self._sessions = {}
        self._presence = {}
        self._fails = {}
        self.last_remote = None
        self.last_request = 0.0
        self.commands = queue.Queue()
        self.events = collections.deque(maxlen=200)
        self._snapshot = {"version": "", "passes": [], "metrics": {}}
        self._display_png = b""

    # ----- endereços e diagnóstico -----
    @property
    def url(self):
        host = detect_lan_ipv4() if self.lan else "127.0.0.1"
        if not host:
            return ""
        return self.url_for(host)

    def url_for(self, host):
        return "http://" + host + ":" + str(self.port) + "/" + ("?key=" + self.key if self.lan else "")

    def urls(self):
        hosts = lan_ipv4_candidates() if self.lan else []
        return [self.url_for(h) for h in hosts] or ([self.url_for("127.0.0.1")] if not self.lan else [])

    @property
    def listening(self):
        return self._httpd is not None

    def note_remote_request(self, raw_ip):
        """Registra acesso de outro computador (último acesso + presença por heartbeat)."""
        now = time.monotonic()
        self.last_request = now
        try:
            if ipaddress.ip_address(raw_ip).is_loopback:
                return
        except ValueError:
            return
        with self._lock:
            self._presence[raw_ip] = now
            self.last_remote = (raw_ip, datetime.now())

    def remote_active(self, window=PRESENCE_SECONDS):
        now = time.monotonic()
        with self._lock:
            return sorted(ip for ip, t in self._presence.items() if now - t <= window)

    def diagnostics(self):
        active = self.remote_active()
        last = ""
        if self.last_remote:
            last = self.last_remote[0] + " às " + self.last_remote[1].strftime("%H:%M:%S")
        return {"listening": self.listening, "port": self.port, "lan": self.lan, "controls": self.controls,
                "addresses": self.urls(), "last_remote": last, "remote_active": active}

    def rotate_key(self):
        """Nova chave: os links antigos e todas as sessões abertas deixam de valer."""
        with self._lock:
            self.key = secrets.token_urlsafe(32)
            self._sessions.clear()
        return self.key

    def browser_recent(self, seconds=15.0):
        return self.last_request and time.monotonic() - self.last_request <= seconds

    # ----- dados da janela principal -----
    def publish(self, snapshot):
        self._snapshot = dict(snapshot)

    def publish_display(self, png):
        self._display_png = bytes(png or b"")

    def drain_commands(self):
        out = []
        while True:
            try:
                out.append(self.commands.get_nowait())
            except queue.Empty:
                return out

    def _event(self, text):
        self.events.append(datetime.now().strftime("%H:%M:%S") + " · " + text)

    # ----- sessões e PIN -----
    def _new_session(self):
        token = secrets.token_urlsafe(32)
        with self._lock:
            now = time.monotonic()
            self._sessions = {k: v for k, v in self._sessions.items() if v > now}
            self._sessions[token] = now + self.session_seconds
        return token

    def _session_ok(self, token):
        if not token:
            return False
        with self._lock:
            exp = self._sessions.get(token)
            if exp is None:
                return False
            if exp < time.monotonic():
                self._sessions.pop(token, None)
                return False
            return True

    def check_pin(self, ip, pin):
        now = time.monotonic()
        with self._lock:
            count, since = self._fails.get(ip, (0, now))
            if count >= PIN_MAX_FAILS and now - since < PIN_LOCK_SECONDS:
                return "locked"
            if now - since >= PIN_LOCK_SECONDS:
                count, since = 0, now
        ok = bool(self.pin_hash_value) and valid_pin(pin) and hmac.compare_digest(
            pin_hash(pin, self.pin_salt), self.pin_hash_value)
        with self._lock:
            if ok:
                self._fails.pop(ip, None)
            else:
                self._fails[ip] = (count + 1, since)
        return "ok" if ok else "wrong"

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def respond(self, status, body, mime="text/plain; charset=utf-8", extra=None):
                raw = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(status)
                for k, v in [("Content-Type", mime), ("Content-Length", str(len(raw))),
                             ("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer"),
                             ("X-Frame-Options", "SAMEORIGIN"), ("X-Content-Type-Options", "nosniff"),
                             ("Content-Security-Policy",
                              "default-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'")] + (extra or []):
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(raw)

            def json(self, status, data):
                self.respond(status, json.dumps(data, ensure_ascii=False, allow_nan=False),
                             "application/json; charset=utf-8")

            def auth(self, path):
                ip = self.client_address[0]
                if not client_allowed(ip):
                    owner._event("Acesso recusado de endereço fora da rede local: " + str(ip))
                    self.respond(HTTPStatus.FORBIDDEN, "Endereço externo bloqueado")
                    return False
                if not owner.lan:
                    owner.note_remote_request(ip)
                    return True
                cookies = SimpleCookie()
                try:
                    cookies.load(self.headers.get("Cookie", ""))
                except Exception:
                    pass
                token = cookies.get(COOKIE)
                if token and owner._session_ok(token.value):
                    owner.note_remote_request(ip)
                    return True
                incoming = parse_qs(urlsplit(self.path).query).get("key", [""])[0]
                if path == "/" and incoming and hmac.compare_digest(incoming, owner.key):
                    session = owner._new_session()
                    owner.note_remote_request(ip)
                    owner._event("Nova sessão do navegador " + str(ip))
                    self.respond(HTTPStatus.SEE_OTHER, b"", extra=[
                        ("Location", "/"),
                        ("Set-Cookie", f"{COOKIE}={session}; Path=/; HttpOnly; SameSite=Strict; Max-Age={owner.session_seconds}")])
                    return False
                self.respond(HTTPStatus.UNAUTHORIZED, "Use o endereço completo com chave exibido no Sat Tool")
                return False

            def do_GET(self):
                path = urlsplit(self.path).path
                if not self.auth(path):
                    return
                if path == "/":
                    self.respond(HTTPStatus.OK, HTML, "text/html; charset=utf-8")
                elif path == "/api/status":
                    data = dict(owner._snapshot)
                    data["controls"] = owner.controls
                    self.json(HTTPStatus.OK, data)
                elif path == "/api/display.png":
                    if not owner._display_png:
                        self.respond(HTTPStatus.NOT_FOUND, "Display indisponível")
                    else:
                        self.respond(HTTPStatus.OK, owner._display_png, "image/png")
                elif path == "/map":
                    try:
                        content = owner.map_path.read_bytes()
                    except OSError:
                        self.respond(HTTPStatus.NOT_FOUND, "Mapa indisponível")
                        return
                    self.respond(HTTPStatus.OK, content, "text/html; charset=utf-8")
                else:
                    self.respond(HTTPStatus.NOT_FOUND, "Não encontrado")

            def do_POST(self):
                path = urlsplit(self.path).path
                if path != "/api/control":
                    self.respond(HTTPStatus.METHOD_NOT_ALLOWED, "Somente consulta nesta rota", extra=[("Allow", "GET")])
                    return
                if not self.auth(path):
                    return
                ip = self.client_address[0]
                if not owner.controls:
                    self.json(HTTPStatus.FORBIDDEN, {"error": "Controle pela rede desligado no Sat Tool"})
                    return
                # Cabeçalho próprio + mesma origem: um site de fora não consegue disparar ações.
                origin = self.headers.get("Origin", "")
                host = self.headers.get("Host", "")
                if self.headers.get("X-PT2VHF") != "1" or (origin and origin != "http://" + host):
                    self.json(HTTPStatus.FORBIDDEN, {"error": "Origem não autorizada"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = -1
                if not 0 < length <= MAX_BODY:
                    self.json(HTTPStatus.BAD_REQUEST, {"error": "Pedido inválido"})
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    action, value = validate_control(payload)
                except PermissionError as exc:
                    owner._event(f"Recusado de {ip}: {exc}")
                    self.json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
                    return
                except (ValueError, UnicodeDecodeError) as exc:
                    self.json(HTTPStatus.BAD_REQUEST, {"error": str(exc) or "Pedido inválido"})
                    return
                result = owner.check_pin(ip, payload.get("pin", ""))
                if result == "locked":
                    self.json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "PIN errado várias vezes; aguarde 5 minutos"})
                    return
                if result != "ok":
                    owner._event(f"PIN incorreto de {ip}")
                    self.json(HTTPStatus.FORBIDDEN, {"error": "PIN incorreto"})
                    return
                owner.commands.put({"action": action, "value": value, "ip": ip})
                owner._event(f"{ip} pediu {action}" + ("" if value is None else f" = {value}"))
                self.json(HTTPStatus.ACCEPTED, {"ok": True})

        self._httpd = ThreadingHTTPServer(("0.0.0.0" if self.lan else "127.0.0.1", self.port), Handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="sat-web", daemon=True)
        self._thread.start()
        return self.url

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
            self._thread = None
