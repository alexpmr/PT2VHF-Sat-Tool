"""Interface do rotor (v1.7.0): aba Configurações → Rotor, barra na aba Operação e rastreamento.

Mixin da janela principal. Toda comunicação serial roda em segundo plano (self.background);
a interface só agenda e mostra resultados. Movimento automático somente após o operador clicar
"Rastrear passagem"; PARAR sempre visível enquanto o rotor estiver habilitado.
"""
from __future__ import annotations

import time
from datetime import timedelta

from .qt_compat import (Qt, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox, QCheckBox,
                        QDoubleSpinBox, QMessageBox, QWidget)
from .rotor import GS232Rotor, PROFILES, RotorProfile, needs_move, plan_pass, probe_port, to_rotor

ROTOR_DEFAULTS = {
    "rotor_enabled": False, "rotor_port": "", "rotor_baud": 9600, "rotor_profile": "g5400b",
    "rotor_az_max": 450.0, "rotor_el_max": 180.0, "rotor_north_offset": 0.0, "rotor_park_az": 0.0,
    "rotor_park_el": 0.0, "rotor_tolerance": 4.0, "rotor_min_interval": 2.0, "rotor_prepos_s": 180.0,
}


class RotorUiMixin:
    # ------------------------------------------------------------------ estado
    def rotor_init(self):
        self.rotor = GS232Rotor(self.log)
        self.rotor_tracking = False
        self.rotor_plan = None
        self.rotor_plan_pass = None
        self.rotor_target = None
        self.rotor_last_read = 0.0

    def rotor_cfg(self, key):
        return self.config.values.get(key, ROTOR_DEFAULTS[key])

    def rotor_profile(self) -> RotorProfile:
        base = PROFILES.get(str(self.rotor_cfg("rotor_profile")), PROFILES["g5400b"])
        return RotorProfile(name=base.name, az_max=float(self.rotor_cfg("rotor_az_max")),
                            el_max=float(self.rotor_cfg("rotor_el_max")),
                            north_offset=float(self.rotor_cfg("rotor_north_offset")),
                            park_az=float(self.rotor_cfg("rotor_park_az")), park_el=float(self.rotor_cfg("rotor_park_el")),
                            tolerance=float(self.rotor_cfg("rotor_tolerance")),
                            min_interval_s=float(self.rotor_cfg("rotor_min_interval")))

    # ------------------------------------------------------------------ Configurações → Rotor
    def build_rotor_settings(self, layout):
        from .app import group, label  # helpers de layout da janela principal
        box, bv = group("ROTOR DE ANTENA · GS-232 (ex.: Yaesu G-5400B + ERC-M pela USB)")
        self.rotor_enable = QCheckBox("Habilitar controle de rotor")
        self.rotor_enable.setChecked(bool(self.rotor_cfg("rotor_enabled")))
        bv.addWidget(self.rotor_enable)
        grid = QGridLayout(); grid.setColumnStretch(1, 1)
        self.rotor_port = QComboBox(); self.rotor_port.setEditable(True)
        self.rotor_refresh = QPushButton("↻ Portas")
        self.rotor_detect = QPushButton("Detectar (só leitura)")
        self.rotor_detect.setToolTip("Procura o controlador GS-232 lendo a posição (C2) em cada porta; não move o rotor")
        prow = QHBoxLayout(); prow.addWidget(self.rotor_port, 1); prow.addWidget(self.rotor_refresh); prow.addWidget(self.rotor_detect)
        self.rotor_baud = QComboBox()
        for b in ("1200", "4800", "9600", "19200", "38400", "57600", "115200"):
            self.rotor_baud.addItem(b)
        self.rotor_baud.setCurrentText(str(int(self.rotor_cfg("rotor_baud"))))
        self.rotor_model = QComboBox()
        for code, prof in PROFILES.items():
            self.rotor_model.addItem(prof.name, code)
        self.rotor_model.setCurrentIndex(max(0, self.rotor_model.findData(str(self.rotor_cfg("rotor_profile")))))

        def spin(lo, hi, value, suffix, step=1.0):
            w = QDoubleSpinBox(); w.setRange(lo, hi); w.setDecimals(0 if step >= 1 else 1)
            w.setSingleStep(step); w.setSuffix(suffix); w.setValue(float(value)); return w
        self.rotor_az_max = spin(360, 450, self.rotor_cfg("rotor_az_max"), " °")
        self.rotor_el_max = spin(90, 180, self.rotor_cfg("rotor_el_max"), " °")
        self.rotor_offset = spin(-180, 180, self.rotor_cfg("rotor_north_offset"), " °")
        self.rotor_park_az = spin(0, 450, self.rotor_cfg("rotor_park_az"), " °")
        self.rotor_park_el = spin(0, 180, self.rotor_cfg("rotor_park_el"), " °")
        self.rotor_tol = spin(1, 20, self.rotor_cfg("rotor_tolerance"), " °")
        self.rotor_interval = spin(1, 30, self.rotor_cfg("rotor_min_interval"), " s")
        self.rotor_prepos = spin(30, 900, self.rotor_cfg("rotor_prepos_s"), " s")
        rows = (("Porta COM (USB do ERC-M)", prow), ("Velocidade", self.rotor_baud), ("Rotor", self.rotor_model),
                ("Azimute máximo (360 ou 450)", self.rotor_az_max), ("Elevação máxima (90 ou 180)", self.rotor_el_max),
                ("Correção do norte", self.rotor_offset), ("Estacionar em azimute", self.rotor_park_az),
                ("Estacionar em elevação", self.rotor_park_el), ("Tolerância (só move acima disto)", self.rotor_tol),
                ("Intervalo mínimo entre comandos", self.rotor_interval), ("Pré-posicionar antes do AOS", self.rotor_prepos))
        for i, (txt, w) in enumerate(rows):
            grid.addWidget(label(txt), i, 0)
            if isinstance(w, QHBoxLayout):
                grid.addLayout(w, i, 1)
            else:
                grid.addWidget(w, i, 1)
        bv.addLayout(grid)
        actions = QHBoxLayout()
        self.rotor_save_btn = QPushButton("Salvar rotor"); self.rotor_save_btn.setObjectName("primary")
        self.rotor_connect_btn = QPushButton("Conectar")
        self.rotor_read_btn = QPushButton("Ler posição")
        for w in (self.rotor_save_btn, self.rotor_connect_btn, self.rotor_read_btn):
            actions.addWidget(w)
        bv.addLayout(actions)
        self.rotor_settings_status = label("Rotor desconectado")
        bv.addWidget(self.rotor_settings_status)
        bv.addWidget(label(
            "Protocolo GS-232 (A/B) direto pela porta COM — o ERC-M emula o GS-232. Configure no programa do ERC o "
            "tipo de rotor Yaesu e calibre os dois eixos. O Sat Tool nunca move a antena só por selecionar um "
            "satélite: o rastreamento começa no botão 'Rastrear passagem' da aba Operação; PARAR fica sempre visível. "
            "Elevação até 180° permite o modo flip (passa por cima sem dar a volta no batente)."))
        layout.addWidget(box)
        layout.addStretch(1)
        self.rotor_refresh.clicked.connect(self.rotor_update_ports)
        self.rotor_detect.clicked.connect(self.rotor_autodetect)
        self.rotor_save_btn.clicked.connect(self.rotor_save)
        self.rotor_connect_btn.clicked.connect(self.rotor_toggle_connection)
        self.rotor_read_btn.clicked.connect(lambda: self.rotor_request_read(force=True))
        self.rotor_model.currentIndexChanged.connect(self.rotor_apply_model)
        self.rotor_enable.toggled.connect(lambda *_: self.rotor_save())
        self.rotor_update_ports()

    def rotor_apply_model(self, *_):
        prof = PROFILES.get(self.rotor_model.currentData() or "g5400b")
        if prof:
            self.rotor_az_max.setValue(prof.az_max)
            self.rotor_el_max.setValue(prof.el_max)

    def rotor_update_ports(self):
        try:
            from .cat import available_ports
            ports = available_ports()
        except Exception:
            ports = []
        current = str(self.rotor_cfg("rotor_port") or self.rotor_port.currentText())
        self.rotor_port.clear()
        self.rotor_port.addItems(ports)
        if current:
            if self.rotor_port.findText(current) < 0:
                self.rotor_port.addItem(current)
            self.rotor_port.setCurrentText(current)

    def rotor_save(self):
        v = self.config.values
        v.update(rotor_enabled=self.rotor_enable.isChecked(), rotor_port=self.rotor_port.currentText().strip(),
                 rotor_baud=int(self.rotor_baud.currentText()), rotor_profile=self.rotor_model.currentData() or "g5400b",
                 rotor_az_max=self.rotor_az_max.value(), rotor_el_max=self.rotor_el_max.value(),
                 rotor_north_offset=self.rotor_offset.value(), rotor_park_az=self.rotor_park_az.value(),
                 rotor_park_el=self.rotor_park_el.value(), rotor_tolerance=self.rotor_tol.value(),
                 rotor_min_interval=self.rotor_interval.value(), rotor_prepos_s=self.rotor_prepos.value())
        self.config.save()
        self.rotor_bar.setVisible(bool(v["rotor_enabled"]))
        if not v["rotor_enabled"]:
            self.rotor_stop("rotor desabilitado")
            self.background("rotor-close", self.rotor.close)
        self.rotor_settings_status.setText("Configurações do rotor salvas")

    def rotor_autodetect(self):
        try:
            from .cat import available_ports
            ports = available_ports()
        except Exception:
            ports = []
        busy = {self.ports.currentText()} if getattr(self.radio, "connected", False) else set()
        baud = int(self.rotor_baud.currentText())
        self.rotor_settings_status.setText("Procurando controlador GS-232 (somente leitura)…")

        def task():
            for port in ports:
                if port in busy:
                    continue
                pos = probe_port(port, baud)
                if pos is not None:
                    return port, pos
            return None
        self.background("rotor-detect", task)

    def rotor_toggle_connection(self):
        if self.rotor.connected:
            self.rotor_stop("desconectar")
            self.background("rotor-close", self.rotor.close)
            return
        self.rotor_save()
        port, baud = str(self.rotor_cfg("rotor_port")), int(self.rotor_cfg("rotor_baud"))
        if not port:
            QMessageBox.information(self, "Rotor", "Escolha a porta COM do rotor (ou use Detectar).")
            return
        self.rotor_settings_status.setText(f"Conectando ao rotor em {port}…")
        self.background("rotor-connect", lambda: self.rotor.connect(port, baud))

    # ------------------------------------------------------------------ barra da aba Operação
    def build_rotor_bar(self, layout):
        from .app import label
        self.rotor_bar = QWidget()
        row = QHBoxLayout(self.rotor_bar); row.setContentsMargins(0, 0, 0, 0)
        self.rotor_label = label("ROTOR · desconectado")
        self.rotor_label.setStyleSheet("font-size:12px;font-weight:800;color:#f0c186")
        self.rotor_track_btn = QPushButton("Rastrear passagem")
        self.rotor_track_btn.setCheckable(True)
        self.rotor_track_btn.setToolTip("Pré-posiciona no AOS, acompanha a passagem do satélite selecionado e estaciona no LOS")
        self.rotor_park_btn = QPushButton("Estacionar")
        self.rotor_stop_btn = QPushButton("PARAR")
        self.rotor_stop_btn.setStyleSheet("font-weight:900;color:#fff;background:#a32626;border:1px solid #e05656;padding:4px 14px")
        self.rotor_stop_btn.setToolTip("Interrompe imediatamente azimute e elevação (GS-232 'S')")
        row.addWidget(self.rotor_label, 1)
        for w in (self.rotor_track_btn, self.rotor_park_btn, self.rotor_stop_btn):
            row.addWidget(w)
        layout.addWidget(self.rotor_bar)
        self.rotor_bar.setVisible(bool(self.rotor_cfg("rotor_enabled")))
        self.rotor_track_btn.toggled.connect(self.rotor_toggle_tracking)
        self.rotor_park_btn.clicked.connect(self.rotor_park)
        self.rotor_stop_btn.clicked.connect(lambda: self.rotor_stop("PARAR pelo operador"))

    def rotor_toggle_tracking(self, on):
        if on:
            if not self.rotor.connected:
                self.rotor_track_btn.setChecked(False)
                QMessageBox.information(self, "Rotor", "Conecte o rotor em Configurações → Rotor antes de rastrear.")
                return
            if self.sat is None:
                self.rotor_track_btn.setChecked(False)
                return
            self.rotor_tracking = True
            self.rotor_plan = None
            self.rotor_plan_pass = None
            self.log("Rotor: rastreamento ligado pelo operador (" + str(self.sat_combo.currentText()) + ")")
        else:
            if self.rotor_tracking:
                self.rotor_stop("rastreamento desligado")

    def rotor_stop(self, reason=""):
        was = self.rotor_tracking
        self.rotor_tracking = False
        self.rotor_plan = None
        if getattr(self, "rotor_track_btn", None) is not None and self.rotor_track_btn.isChecked():
            self.rotor_track_btn.blockSignals(True); self.rotor_track_btn.setChecked(False); self.rotor_track_btn.blockSignals(False)
        if self.rotor.connected:
            self.pending_jobs.discard("rotor-stop")
            self.background("rotor-stop", self.rotor.stop)
        if reason and (was or "PARAR" in reason):
            self.log("Rotor: parado (" + reason + ")")

    def rotor_park(self):
        if not self.rotor.connected:
            return
        self.rotor_stop("estacionar")
        prof = self.rotor_profile()
        self.background("rotor-move", lambda: self.rotor.park(prof))

    def rotor_request_read(self, force=False):
        if self.rotor.connected and (force or time.monotonic() - self.rotor_last_read >= 1.0):
            self.rotor_last_read = time.monotonic()
            self.background("rotor-read", self.rotor.read_position)

    # ------------------------------------------------------------------ laço (chamado pelo tick de 1 s)
    def rotor_make_plan(self, event, station):
        from .core import position
        track = []
        t = event["aos"]
        while t <= event["los"]:
            p = position(self.sat, station, when=t, ts=self.ts)
            track.append((t.timestamp(), p["azimuth"], p["elevation"]))
            t += timedelta(seconds=10)
        return plan_pass(track, self.rotor_profile())

    def rotor_tick(self, now):
        if not bool(self.rotor_cfg("rotor_enabled")) or not self.rotor.connected:
            if getattr(self, "rotor_label", None) is not None and not self.rotor.connected:
                self.rotor_label.setText("ROTOR · desconectado · Configurações → Rotor")
            return
        self.rotor_request_read()
        pos = self.rotor.position
        text = "ROTOR · " + (f"AZ {pos[0]:.0f}° EL {pos[1]:.0f}°" if pos else "AZ — EL —")
        if hasattr(self, "lcd"):
            self.lcd.set_state(rotor=(f"ROT {pos[0]:.0f}/{pos[1]:.0f}" if pos else ""))
        if not self.rotor_tracking or self.sat is None:
            self.rotor_label.setText(text + " · parado")
            return
        if self.rotor.failures >= 3:
            self.rotor_stop("sem resposta do controlador")
            QMessageBox.warning(self, "Rotor", "O controlador do rotor parou de responder. Rastreamento interrompido.")
            return
        event = getattr(self, "next_candidate", None)
        if event is None:
            self.rotor_label.setText(text + " · sem passagem prevista")
            return
        prof = self.rotor_profile()
        key = (event.get("id"), event["aos"])
        try:
            station = self.saved_station()
            if self.rotor_plan is None or self.rotor_plan_pass != key:
                self.rotor_plan = self.rotor_make_plan(event, station)
                self.rotor_plan_pass = key
                self.log(f"Rotor: plano da passagem = {self.rotor_plan['mode']}")
            from .core import position
            if now >= event["los"]:
                self.rotor_label.setText(text + " · LOS: estacionando")
                self.rotor_park()
                return
            if now < event["aos"]:
                if (event["aos"] - now).total_seconds() > float(self.rotor_cfg("rotor_prepos_s")):
                    self.rotor_label.setText(text + f" · aguardando AOS (modo {self.rotor_plan['mode']})")
                    return
                target = self.rotor_plan["track"][0] if self.rotor_plan["track"] else None
                phase = "pré-posicionado no AOS"
            else:
                p = position(self.sat, station, when=now + timedelta(seconds=2), ts=self.ts)
                target = to_rotor(p["azimuth"], p["elevation"], self.rotor_plan, prof,
                                  when=(now + timedelta(seconds=2)).timestamp(), current_az=pos[0] if pos else None)
                phase = "rastreando"
        except Exception as exc:
            self.rotor_label.setText(text + " · erro: " + str(exc)[:80])
            return
        if target is None:
            return
        self.rotor_target = target
        self.rotor_label.setText(text + f" · {phase} → AZ {target[0]:.0f}° EL {target[1]:.0f}° ({self.rotor_plan['mode']})")
        if needs_move(target, pos, prof) and time.monotonic() - self.rotor.last_command_at >= prof.min_interval_s:
            self.background("rotor-move", lambda: self.rotor.move(target[0], target[1], prof))

    # ------------------------------------------------------------------ resultados dos trabalhos
    def rotor_result(self, key, data) -> bool:
        if not key.startswith("rotor-"):
            return False
        if key == "rotor-connect":
            self.rotor_connect_btn.setText("Desconectar")
            self.rotor_settings_status.setText(f"Rotor conectado · AZ {data[0]:.0f}° EL {data[1]:.0f}°")
            self.rotor_bar.setVisible(True)
        elif key == "rotor-close":
            self.rotor_connect_btn.setText("Conectar")
            self.rotor_settings_status.setText("Rotor desconectado")
        elif key == "rotor-detect":
            if data:
                port, pos = data
                self.rotor_port.setCurrentText(port)
                self.rotor_settings_status.setText(f"Controlador GS-232 encontrado em {port} · AZ {pos[0]:.0f}° EL {pos[1]:.0f}°")
            else:
                self.rotor_settings_status.setText("Nenhum controlador GS-232 respondeu. Confira cabo USB, driver e velocidade.")
        elif key == "rotor-read" and data:
            self.rotor_settings_status.setText(f"Posição lida · AZ {data[0]:.0f}° EL {data[1]:.0f}°")
        return True

    def rotor_failed(self, key, message) -> bool:
        if not key.startswith("rotor-"):
            return False
        if key == "rotor-connect":
            self.rotor_settings_status.setText("Rotor não conectou: " + message[:160])
            self.rotor.close()
        elif key == "rotor-move":
            self.rotor_stop("falha ao mover: " + message[:80])
        elif key == "rotor-read":
            self.rotor_label.setText("ROTOR · sem leitura de posição (" + message[:60] + ")")
        return True

    def rotor_shutdown(self):
        """Ao fechar o programa: PARAR e fechar a porta (síncrono, rápido)."""
        try:
            self.rotor_tracking = False
            self.rotor.stop()
            self.rotor.close()
        except Exception:
            pass
