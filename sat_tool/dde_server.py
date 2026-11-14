"""v1.9.0: servidor DDE compatível com o Orbitron, para o WiSpDDE (CX6DD) e outros drivers DDE.

Especificação do Orbitron (stoff.pl): aplicação "Orbitron", tópico "Tracking", item "TrackingData",
texto "SNnome AZxxx.x ELxx.x DNhz UPhz DMmodo UMmodo" atualizado a cada cálculo. O WiSpDDE se conecta
como cliente (Receive DDE from: Orbitron) e controla os rádios e o rotor que ele suporta.
Só existe no Windows; não rode junto com o Orbitron, que usa o mesmo nome de serviço.
"""
from __future__ import annotations

import sys

SERVICE, TOPIC, ITEM = "Orbitron", "Tracking", "TrackingData"


def tracking_text(snap: dict | None) -> str:
    """Texto do item TrackingData; vazio quando nenhum satélite é acompanhado (como no Orbitron)."""
    if not snap:
        return ""
    name = "_".join(str(snap.get("name") or "SAT").split()) or "SAT"
    parts = [f"SN{name}", f"AZ{float(snap.get('azimuth', 0.0)) % 360:.1f}",
             f"EL{max(-90.0, min(90.0, float(snap.get('elevation', 0.0)))):.1f}"]
    if snap.get("rx_hz"):
        parts.append(f"DN{int(snap['rx_hz'])}")
    if snap.get("tx_hz"):
        parts.append(f"UP{int(snap['tx_hz'])}")
    for key, field in (("rx_mode", "DM"), ("tx_mode", "UM")):
        mode = dde_mode(snap.get(key))
        if mode:
            parts.append(field + mode)
    return " ".join(parts)


def dde_mode(mode) -> str:
    m = str(mode or "").upper()
    if not m:
        return ""
    if m.startswith("FM"):
        return "FM-N"
    return {"USB": "USB", "LSB": "LSB", "CW": "CW", "AM": "AM", "FSK": "FSK"}.get(m, m.replace(" ", "_"))


def available() -> bool:
    return sys.platform == "win32"


class DdeServer:
    """Servidor DDEML (ctypes). Deve ser criado na thread da interface (o laço de mensagens do Qt)."""

    XTYP_ADVSTART, XTYP_ADVSTOP, XTYP_ADVREQ = 0x1030, 0x8040, 0x2022
    XTYP_CONNECT, XTYP_REQUEST, XTYP_WILDCONNECT = 0x1062, 0x20B0, 0x20E2
    CF_TEXT, CP_WINUNICODE, DNS_REGISTER, DNS_UNREGISTER = 1, 1200, 1, 2
    CBF_FAIL_POKES, CBF_FAIL_EXECUTES = 0x00040000, 0x00008000

    def __init__(self, logger=None):
        self.log = logger or (lambda msg: None)
        self.text = ""
        self.inst = None
        self.started = False

    def start(self):
        if not available():
            raise OSError("Servidor DDE só existe no Windows")
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        self._u = u
        HDDEDATA = ctypes.c_void_p
        self._proto = ctypes.WINFUNCTYPE(HDDEDATA, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t)
        u.DdeInitializeW.argtypes = [ctypes.POINTER(wintypes.DWORD), self._proto, wintypes.DWORD, wintypes.DWORD]
        u.DdeCreateStringHandleW.restype = ctypes.c_void_p
        u.DdeCreateStringHandleW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, ctypes.c_int]
        u.DdeNameService.restype = ctypes.c_void_p
        u.DdeNameService.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
        u.DdeCmpStringHandles.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        u.DdeCreateDataHandle.restype = ctypes.c_void_p
        u.DdeCreateDataHandle.argtypes = [wintypes.DWORD, ctypes.c_char_p, wintypes.DWORD, wintypes.DWORD,
                                          ctypes.c_void_p, wintypes.UINT, wintypes.UINT]
        u.DdePostAdvise.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
        u.DdeFreeStringHandle.argtypes = [wintypes.DWORD, ctypes.c_void_p]
        u.DdeUninitialize.argtypes = [wintypes.DWORD]
        self._callback = self._proto(self._on_dde)   # referência mantida: o Windows chama de volta
        inst = wintypes.DWORD(0)
        code = u.DdeInitializeW(ctypes.byref(inst), self._callback, self.CBF_FAIL_POKES | self.CBF_FAIL_EXECUTES, 0)
        if code != 0:
            raise OSError(f"DdeInitialize falhou (código {code})")
        self.inst = inst.value
        self.h_service = u.DdeCreateStringHandleW(self.inst, SERVICE, self.CP_WINUNICODE)
        self.h_topic = u.DdeCreateStringHandleW(self.inst, TOPIC, self.CP_WINUNICODE)
        self.h_item = u.DdeCreateStringHandleW(self.inst, ITEM, self.CP_WINUNICODE)
        if not u.DdeNameService(self.inst, self.h_service, None, self.DNS_REGISTER):
            self.stop()
            raise OSError("O nome DDE Orbitron não pôde ser registrado (o Orbitron está aberto?)")
        self.started = True
        self.log("DDE: servidor Orbitron/Tracking/TrackingData ativo (WiSpDDE e drivers DDE)")

    def _same(self, a, b):
        return bool(a) and self._u.DdeCmpStringHandles(a, b) == 0

    def _data(self):
        raw = self.text.encode("ascii", "replace") + b"\0"
        return self._u.DdeCreateDataHandle(self.inst, raw, len(raw), 0, self.h_item, self.CF_TEXT, 0)

    def _on_dde(self, kind, fmt, conv, hsz1, hsz2, data, d1, d2):
        try:
            if kind == self.XTYP_CONNECT:
                return 1 if self._same(hsz1, self.h_topic) else 0
            if kind == self.XTYP_ADVSTART:
                return 1 if self._same(hsz1, self.h_topic) and self._same(hsz2, self.h_item) else 0
            if kind in (self.XTYP_REQUEST, self.XTYP_ADVREQ):
                if self._same(hsz1, self.h_topic) and self._same(hsz2, self.h_item) and fmt == self.CF_TEXT:
                    return self._data()
        except Exception:   # pragma: no cover - um erro aqui não pode derrubar o programa
            pass
        return 0

    def update(self, text: str):
        if text == self.text:
            return
        self.text = text
        if self.started:
            self._u.DdePostAdvise(self.inst, self.h_topic, self.h_item)

    def stop(self):
        if self.inst is None:
            return
        u = self._u
        try:
            if self.started:
                u.DdeNameService(self.inst, self.h_service, None, self.DNS_UNREGISTER)
            for h in (self.h_service, self.h_topic, self.h_item):
                if h:
                    u.DdeFreeStringHandle(self.inst, h)
            u.DdeUninitialize(self.inst)
        finally:
            self.inst, self.started = None, False
            self.log("DDE: servidor desligado")
