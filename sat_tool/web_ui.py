"""Read-only satellite dashboard: localhost, or explicit passwordless-token LAN.
Never call CAT, PTT or Qt GUI methods on an HTTP thread.
"""
from __future__ import annotations
import hmac
import ipaddress
import json
import secrets
import socket
import threading
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

HTML = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PT2VHF Sat Tool · Web</title><style>
:root{color-scheme:dark;font:14px Segoe UI,Arial,sans-serif;color:#e8f2fa;background:#081726}
*{box-sizing:border-box}body{margin:0}header{background:#102b43;padding:14px 18px;border-bottom:1px solid #3a627d;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
strong{font-size:1.15rem}#time{margin-left:auto;color:#98d8ec}
main{max-width:1440px;margin:auto;padding:12px;display:grid;gap:12px}
.card{background:#10273c;border:1px solid #31516a;border-radius:9px;padding:12px;min-width:0}
h2{color:#7eebd5;font-size:1rem;margin:0 0 10px}.data{font-weight:750;font-size:1.1rem;overflow-wrap:anywhere}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
@media(min-width:900px){.content{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(290px,1fr);gap:12px}}
#map{width:100%;height:365px;border:0;border-radius:6px}.table{overflow-x:auto}
table{width:100%;border-collapse:collapse}th,td{padding:8px 10px;border-bottom:1px solid #35536a;text-align:left;white-space:nowrap}
th{color:#9cdcec}.muted{color:#a8c7d6;font-size:.85rem}footer{text-align:center;color:#98b4c3;padding:14px;font-size:.83rem}
#cat{padding:4px 8px;border-radius:6px;background:#733c3c;color:#ffd0c4}#cat.ok{background:#125743;color:#a4f7c9}#cat.warn{background:#6f5727;color:#ffe0a6}
@media(max-width:540px){#map{height:250px}main{padding:8px}}
</style></head><body>
<header><strong>PT2VHF SAT TOOL <span id="version"></span></strong><span id="cat">CAT</span><span class="muted">Painel Web de consulta</span><span id="time">—</span></header>
<main><section class="card"><h2>Satélite selecionado</h2><div class="data" id="satellite">Aguardando aplicação</div><div class="muted" id="catalog">—</div></section>
<section class="cards"><div class="card"><h2>RX / DOWNLINK</h2><div class="data" id="rx">—</div></div><div class="card"><h2>TX / UPLINK</h2><div class="data" id="tx">—</div></div><div class="card"><h2>Próxima passagem</h2><div class="data" id="nextpass">—</div></div></section>
<div class="content"><section class="card"><h2>Mapa orbital · trajetória e estação</h2><iframe id="map" src="/map" title="Mapa vetorial offline"></iframe></section>
<section class="card"><h2>Telemetria orbital</h2><div id="metrics"></div><p id="visibility" class="muted">—</p><p id="catdetail" class="muted"></p></section></div>
<section class="card"><h2>Passagens nas próximas 36 h</h2><div class="table"><table><thead><tr><th>AOS local</th><th>TCA local</th><th>LOS local</th><th>Duração</th><th>Máx °</th><th>Modos</th></tr></thead><tbody id="passes"></tbody></table></div></section></main>
<footer>PT2VHF.com · Interface Web somente leitura. O CAT e o PTT permanecem sob controle da aplicação desktop. HTTP LAN não é criptografado: não exponha a porta à Internet.</footer>
<script>
(function(){"use strict";const el=id=>document.getElementById(id);
let previous=null;function value(id,v){el(id).textContent=String(v==null?"—":v)}
function render(s){previous=s;value("version","v"+(s.version||""));value("time",s.utc);
value("satellite",s.satellite);value("catalog",String(s.catalog_count||0)+" satélites OMM/TLE");
value("rx",s.rx);value("tx",s.tx);value("nextpass",s.nextpass);value("visibility",s.visibility);
value("catdetail",s.cat_detail);const cat=el("cat");cat.className=s.cat_state==="conectado"?"ok":s.cat_state==="degradado"?"warn":"";
cat.textContent="CAT "+(s.cat_state||"desconectado");
let m=el("metrics");m.replaceChildren();
Object.entries(s.metrics||{}).forEach(([k,v])=>{let p=document.createElement("p");p.textContent=k+": "+v;m.appendChild(p)});
let tbody=el("passes");tbody.replaceChildren();(s.passes||[]).forEach(row=>{let tr=document.createElement("tr");
["aos","tca","los","duration","max_el","modes"].forEach(k=>{let td=document.createElement("td");td.textContent=row[k]||"—";tr.appendChild(td)});
tbody.appendChild(tr)});
try{let iframe=el("map");if(iframe.contentWindow&&typeof iframe.contentWindow.updateOrbit==="function"&&s.orbit){iframe.contentWindow.updateOrbit(s.orbit)}}catch(e){}
}
el("map").addEventListener("load",()=>{if(previous)render(previous)});
async function refresh(){try{let r=await fetch("/api/status",{cache:"no-store"});if(!r.ok)throw Error("HTTP "+r.status);render(await r.json())}catch(e){value("time","Sem acesso: "+e.message)}}
refresh();setInterval(refresh,3000);
})();
</script></body></html>"""


def detect_lan_ipv4():
    candidates = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        candidates.append(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()
    try:
        candidates.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    for raw in candidates:
        try:
            ip = ipaddress.ip_address(raw)
            if ip.version == 4 and ip.is_private and not ip.is_loopback and not ip.is_link_local:
                return str(ip)
        except ValueError:
            pass
    return ""


class LocalStatusServer:
    """The browser has no write endpoints, including CAT/PTT, even with LAN token."""

    def __init__(self, lan=False, port=8094, map_path=None):
        self.lan, self.port = bool(lan), int(port)
        if not 1024 <= self.port <= 65535:
            raise ValueError("Porta TCP inválida (1024 a 65535)")
        self.key = secrets.token_urlsafe(32)
        self.map_path = Path(map_path or Path(__file__).with_name("map.html"))
        self._httpd = None
        self._thread = None
        self._snapshot = {"version": "", "passes": [], "metrics": {}}

    @property
    def url(self):
        host = detect_lan_ipv4() if self.lan else "127.0.0.1"
        if not host:
            return ""
        return "http://" + host + ":" + str(self.port) + "/" + ("?key=" + self.key if self.lan else "")

    def publish(self, snapshot):
        self._snapshot = dict(snapshot)

    def start(self):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def respond(self, status, body, mime="text/plain; charset=utf-8", extra=None):
                raw = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(status)
                for k,v in [("Content-Type",mime),("Content-Length",str(len(raw))),
                    ("Cache-Control","no-store"),("Referrer-Policy","no-referrer"),
                    ("X-Frame-Options","SAMEORIGIN"),("X-Content-Type-Options","nosniff"),
                    ("Content-Security-Policy",
                     "default-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self'; object-src 'none'")]+(extra or []):
                    self.send_header(k,v)
                self.end_headers()
                self.wfile.write(raw)

            def auth(self,path):
                try:
                    ip = ipaddress.ip_address(self.client_address[0])
                    if not (ip.is_private or ip.is_loopback):
                        self.respond(HTTPStatus.FORBIDDEN,"Endereço externo bloqueado")
                        return False
                except ValueError:
                    self.respond(HTTPStatus.FORBIDDEN,"Endereço inválido")
                    return False
                if not owner.lan:
                    return True
                cookies = SimpleCookie()
                try:
                    cookies.load(self.headers.get("Cookie",""))
                except Exception:
                    pass
                token = cookies.get("PT2VHFSession")
                if token and hmac.compare_digest(token.value,owner.key):
                    return True
                incoming = parse_qs(urlsplit(self.path).query).get("key",[""])[0]
                if path=="/" and incoming and hmac.compare_digest(incoming,owner.key):
                    self.respond(HTTPStatus.SEE_OTHER,b"",extra=[
                        ("Location","/"),("Set-Cookie","PT2VHFSession="+owner.key+"; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800")])
                    return False
                self.respond(HTTPStatus.UNAUTHORIZED,"Use o endereço completo com chave exibido no Sat Tool")
                return False

            def do_GET(self):
                path=urlsplit(self.path).path
                if not self.auth(path):
                    return
                if path=="/":
                    self.respond(HTTPStatus.OK,HTML,"text/html; charset=utf-8")
                elif path=="/api/status":
                    self.respond(HTTPStatus.OK,json.dumps(owner._snapshot,ensure_ascii=False,allow_nan=False),
                        "application/json; charset=utf-8")
                elif path=="/map":
                    try:
                        content=owner.map_path.read_bytes()
                    except OSError:
                        self.respond(HTTPStatus.NOT_FOUND,"Mapa indisponível")
                        return
                    self.respond(HTTPStatus.OK,content,"text/html; charset=utf-8")
                else:
                    self.respond(HTTPStatus.NOT_FOUND,"Não encontrado")

            def do_POST(self):
                self.respond(HTTPStatus.METHOD_NOT_ALLOWED,"Interface de consulta: controles remotos desabilitados",extra=[("Allow","GET")])

        self._httpd = ThreadingHTTPServer(("0.0.0.0" if self.lan else "127.0.0.1",self.port), Handler)
        self._httpd.daemon_threads = True
        self._thread=threading.Thread(target=self._httpd.serve_forever,name="sat-web",daemon=True)
        self._thread.start()
        return self.url

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
            self._thread = None
