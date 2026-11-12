"""Interface do rotor (v1.7.0; v1.7.1: Configurações → Rotores e faixa ROTOR na Operação).

Mixin da janela principal. Toda comunicação serial roda em segundo plano (self.background);
a interface só agenda e mostra resultados. Movimento automático somente após o operador clicar
"Rastrear passagem"; PARAR sempre visível enquanto o rotor estiver habilitado.
"""
from __future__ import annotations

import time
from datetime import timedelta

from .qt_compat import (Qt, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox, QCheckBox,
                        QDoubleSpinBox, QMessageBox, QWidget, QPlainTextEdit)
from .rotor import (GS232Rotor, PROFILES, RotorProfile, needs_move, plan_pass, probe_port, to_rotor,
                    calibrated_north_offset, jog_target)

PREFERENCES = {"auto": "Automático (normal se couber, senão flip)", "normal": "Sempre normal (nunca flip)",
               "flip": "Preferir flip (passa por cima)"}
ROTOR_LOG_LINES = 400

ROTOR_DEFAULTS = {
    "rotor_enabled": False, "rotor_port": "", "rotor_baud": 9600, "rotor_profile": "g5400b",
    "rotor_az_max": 450.0, "rotor_el_max": 180.0, "rotor_north_offset": 0.0, "rotor_park_az": 0.0,
    "rotor_park_el": 0.0, "rotor_tolerance": 4.0, "rotor_min_interval": 2.0, "rotor_prepos_s": 180.0,
    "rotor_min_el": 0.0, "rotor_preference": "auto", "rotor_jog_step": 5.0,
}


class RotorUiMixin:
    # ------------------------------------------------------------------ estado
    def rotor_init(self):
        self.rotor_log_lines = []
        self.rotor = GS232Rotor(self.rotor_log)
        self.rotor_tracking = False
        self.rotor_auto = True          # v1.7.2: rastreamento automático armado (pausado pelo PARADO/Esc/F12)
        self.rotor_parked_pass = None
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
                            min_el=float(self.rotor_cfg("rotor_min_el")),
                            min_interval_s=float(self.rotor_cfg("rotor_min_interval")))

    def rotor_log(self, text):
        """Log do rotor (TX/RX GS-232, falhas, watchdog): vai para LOGs e para o quadro em Configurações → Rotores."""
        self.log(text)
        stamp = time.strftime("%H:%M:%S")
        self.rotor_log_lines.append(f"{stamp}  {text}")
        del self.rotor_log_lines[:-ROTOR_LOG_LINES]
        view = getattr(self, "rotor_log_view", None)
        if view is not None:
            view.appendPlainText(f"{stamp}  {text}")

    # ------------------------------------------------------------------ Configurações → Rotores
    def build_rotor_settings(self, layout):
        """v1.7.1: toda a configuração e todos os ajustes de rotor numa só aba (sem aba principal separada)."""
        from .app import group, label  # helpers de layout da janela principal
        from .rotor_widgets import RotorCompass

        def spin(lo, hi, value, suffix, step=1.0):
            w = QDoubleSpinBox(); w.setRange(lo, hi); w.setDecimals(0 if step >= 1 else 1)
            w.setSingleStep(step); w.setSuffix(suffix); w.setValue(float(value)); return w

        def form(rows):
            grid = QGridLayout()
            for i, (txt, w) in enumerate(rows):
                grid.addWidget(label(txt), i, 0)
                (grid.addLayout if isinstance(w, QHBoxLayout) else grid.addWidget)(w, i, 1)
            return grid

        # --- conexão
        box, bv = group("CONEXÃO · GS-232 (ex.: Yaesu G-5400B + ERC-M pela USB)")
        self.rotor_enable = QCheckBox("Habilitar controle de rotor (mostra a faixa ROTOR na aba Operação)")
        self.rotor_enable.setChecked(bool(self.rotor_cfg("rotor_enabled")))
        bv.addWidget(self.rotor_enable)
        self.rotor_port = QComboBox(); self.rotor_port.setEditable(True)
        self.rotor_refresh = QPushButton("↻ Portas")
        self.rotor_detect = QPushButton("Detectar (só leitura)")
        self.rotor_detect.setToolTip("Procura o controlador GS-232 lendo a posição (C2) em cada porta; não move o rotor")
        prow = QHBoxLayout(); prow.addWidget(self.rotor_port, 1); prow.addWidget(self.rotor_refresh); prow.addWidget(self.rotor_detect)
        self.rotor_baud = QComboBox()
        for b in ("1200", "4800", "9600", "19200", "38400", "57600", "115200"):
            self.rotor_baud.addItem(b)
        self.rotor_baud.setCurrentText(str(int(self.rotor_cfg("rotor_baud"))))
        self.rotor_protocol = QComboBox(); self.rotor_protocol.addItem("Yaesu GS-232A/B", "gs232")
        self.rotor_protocol.setToolTip("Hamlib rotctld, EasyComm e SPID Rot2Prog entram em versões futuras")
        self.rotor_model = QComboBox()
        for code, prof in PROFILES.items():
            self.rotor_model.addItem(prof.name, code)
        self.rotor_model.setCurrentIndex(max(0, self.rotor_model.findData(str(self.rotor_cfg("rotor_profile")))))
        bv.addLayout(form((("Porta COM (USB do ERC-M)", prow), ("Velocidade", self.rotor_baud),
                           ("Protocolo", self.rotor_protocol), ("Controlador / perfil", self.rotor_model))))
        actions = QHBoxLayout()
        self.rotor_save_btn = QPushButton("Salvar rotor"); self.rotor_save_btn.setObjectName("primary")
        self.rotor_connect_btn = QPushButton("Conectar")
        self.rotor_read_btn = QPushButton("Ler posição")
        for w in (self.rotor_save_btn, self.rotor_connect_btn, self.rotor_read_btn):
            actions.addWidget(w)
        bv.addLayout(actions)
        self.rotor_settings_status = label("Rotor desconectado")
        bv.addWidget(self.rotor_settings_status)
        layout.addWidget(box)

        # --- limites e calibração
        lim, lv = group("LIMITES E CALIBRAÇÃO")
        self.rotor_az_max = spin(360, 450, self.rotor_cfg("rotor_az_max"), " °")
        self.rotor_el_max = spin(90, 180, self.rotor_cfg("rotor_el_max"), " °")
        self.rotor_offset = spin(-180, 180, self.rotor_cfg("rotor_north_offset"), " °")
        lv.addLayout(form((("Azimute máximo (360 ou 450)", self.rotor_az_max),
                           ("Elevação máxima (90, ou 180 para flip)", self.rotor_el_max),
                           ("Correção do norte", self.rotor_offset))))
        cal = QHBoxLayout()
        self.rotor_true_az = spin(0, 359, 0, " °")
        self.rotor_true_az.setToolTip("Direção real para onde a antena aponta agora (referência visual, bússola, torre)")
        self.rotor_calibrate_btn = QPushButton("Calibrar norte pela posição atual")
        self.rotor_calibrate_btn.setToolTip("Lê a posição (C2) e calcula a correção do norte para que a leitura "
                                            "coincida com a direção real informada")
        self.rotor_test_btn = QPushButton("Teste curto (+10° AZ e volta)")
        self.rotor_test_btn.setToolTip("Movimento supervisionado: sobe 10° em azimute e volta; PARAR interrompe")
        cal.addWidget(label("A antena aponta de fato para")); cal.addWidget(self.rotor_true_az)
        cal.addWidget(self.rotor_calibrate_btn); cal.addWidget(self.rotor_test_btn)
        lv.addLayout(cal)
        lv.addWidget(label("Calibração guiada: leve a antena até uma referência conhecida (ex.: norte verdadeiro "
                           "ou fim de curso 0°), confira a leitura ao vivo abaixo e clique Calibrar. O teste curto "
                           "confirma o sentido de giro e os batentes."))
        layout.addWidget(lim)

        # --- rastreamento
        trk, tv = group("AJUSTES DE RASTREAMENTO")
        self.rotor_tol = spin(1, 20, self.rotor_cfg("rotor_tolerance"), " °")
        self.rotor_interval = spin(1, 30, self.rotor_cfg("rotor_min_interval"), " s")
        self.rotor_prepos = spin(30, 900, self.rotor_cfg("rotor_prepos_s"), " s")
        self.rotor_park_az = spin(0, 450, self.rotor_cfg("rotor_park_az"), " °")
        self.rotor_park_el = spin(0, 180, self.rotor_cfg("rotor_park_el"), " °")
        self.rotor_min_el = spin(0, 30, self.rotor_cfg("rotor_min_el"), " °")
        self.rotor_pref = QComboBox()
        for code, name in PREFERENCES.items():
            self.rotor_pref.addItem(name, code)
        self.rotor_pref.setCurrentIndex(max(0, self.rotor_pref.findData(str(self.rotor_cfg("rotor_preference")))))
        tv.addLayout(form((("Tolerância (só move acima disto)", self.rotor_tol),
                           ("Intervalo mínimo entre comandos", self.rotor_interval),
                           ("Pré-posicionar antes do AOS", self.rotor_prepos),
                           ("Estacionar em azimute", self.rotor_park_az),
                           ("Estacionar em elevação", self.rotor_park_el),
                           ("Máscara de horizonte do rotor", self.rotor_min_el),
                           ("Preferência normal/flip", self.rotor_pref))))
        layout.addWidget(trk)

        # --- ajuste manual / teste
        man, mv = group("AJUSTE MANUAL E TESTE")
        row = QHBoxLayout()
        self.rotor_settings_compass = RotorCompass(size=110)
        row.addWidget(self.rotor_settings_compass)
        col = QVBoxLayout()
        goto = QHBoxLayout()
        self.rotor_goto_az = spin(0, 450, 0, " °"); self.rotor_goto_el = spin(0, 180, 0, " °")
        self.rotor_goto_btn = QPushButton("Ir para AZ/EL")
        goto.addWidget(label("AZ")); goto.addWidget(self.rotor_goto_az)
        goto.addWidget(label("EL")); goto.addWidget(self.rotor_goto_el); goto.addWidget(self.rotor_goto_btn)
        col.addLayout(goto)
        jog = QHBoxLayout()
        self.rotor_jog_step = spin(1, 45, self.rotor_cfg("rotor_jog_step"), " °")
        jog.addWidget(label("Passo")); jog.addWidget(self.rotor_jog_step)
        self.rotor_jog_buttons = {}
        for key, txt, tip in (("left", "◀ AZ−", "Gira para a esquerda"), ("right", "AZ+ ▶", "Gira para a direita"),
                              ("down", "▼ EL−", "Abaixa"), ("up", "EL+ ▲", "Levanta")):
            b = QPushButton(txt); b.setToolTip(tip); self.rotor_jog_buttons[key] = b; jog.addWidget(b)
        col.addLayout(jog)
        manual_actions = QHBoxLayout()
        self.rotor_settings_park = QPushButton("Estacionar")
        self.rotor_settings_stop = QPushButton("PARAR")
        self.rotor_settings_stop.setStyleSheet("font-weight:900;color:#fff;background:#a32626;border:1px solid #e05656;padding:4px 14px")
        manual_actions.addWidget(self.rotor_settings_park); manual_actions.addWidget(self.rotor_settings_stop)
        col.addLayout(manual_actions)
        self.rotor_live = label("Posição ao vivo: —")
        self.rotor_live.setStyleSheet("font-size:14px;font-weight:800;color:#5af08a")
        col.addWidget(self.rotor_live)
        row.addLayout(col)
        mv.addLayout(row)
        layout.addWidget(man)

        # --- log
        lg, lgv = group("LOG DO ROTOR")
        self.rotor_log_view = QPlainTextEdit(); self.rotor_log_view.setReadOnly(True)
        self.rotor_log_view.setMaximumBlockCount(ROTOR_LOG_LINES); self.rotor_log_view.setMinimumHeight(120)
        self.rotor_log_view.setPlainText("\n".join(self.rotor_log_lines))
        lgv.addWidget(self.rotor_log_view)
        lgv.addWidget(label("Com o rotor conectado, o Sat Tool rastreia sozinho o satélite selecionado quando ele está acima do horizonte (pré-posiciona antes do AOS e estaciona no LOS). O botão RASTREANDO/PARADO da aba Operação para o rotor e pausa o automático (Esc/F12). O ERC-M emula o GS-232: configure nele o tipo de rotor Yaesu. Elevação até 180° permite o flip."))
        layout.addWidget(lg)
        layout.addStretch(1)

        self.rotor_refresh.clicked.connect(self.rotor_update_ports)
        self.rotor_detect.clicked.connect(self.rotor_autodetect)
        self.rotor_save_btn.clicked.connect(self.rotor_save)
        self.rotor_connect_btn.clicked.connect(self.rotor_toggle_connection)
        self.rotor_read_btn.clicked.connect(lambda: self.rotor_request_read(force=True))
        self.rotor_model.currentIndexChanged.connect(self.rotor_apply_model)
        self.rotor_enable.toggled.connect(lambda *_: self.rotor_save())
        self.rotor_calibrate_btn.clicked.connect(self.rotor_calibrate)
        self.rotor_test_btn.clicked.connect(self.rotor_short_test)
        self.rotor_goto_btn.clicked.connect(lambda: self.rotor_manual_move(self.rotor_goto_az.value(), self.rotor_goto_el.value()))
        for key, (daz, delv) in (("left", (-1, 0)), ("right", (1, 0)), ("down", (0, -1)), ("up", (0, 1))):
            self.rotor_jog_buttons[key].clicked.connect(lambda _=False, a=daz, e=delv: self.rotor_jog(a, e))
        self.rotor_settings_park.clicked.connect(self.rotor_park)
        self.rotor_settings_stop.clicked.connect(lambda: self.rotor_stop("PARAR pelo operador"))
        self.rotor_update_ports()

    # ------------------------------------------------------------------ ajustes manuais
    def rotor_manual_move(self, az, el):
        if not self.rotor.connected:
            QMessageBox.information(self, "Rotor", "Conecte o rotor antes de movê-lo.")
            return
        self.rotor_stop("ajuste manual")
        prof = self.rotor_profile()
        self.rotor_log(f"Rotor: ajuste manual → AZ {az:.0f}° EL {el:.0f}°")
        self.background("rotor-move", lambda: self.rotor.move(az, el, prof))

    def rotor_jog(self, d_az, d_el):
        step = self.rotor_jog_step.value()
        target = jog_target(self.rotor.position, d_az * step, d_el * step, self.rotor_profile())
        if target is None:
            self.rotor_settings_status.setText("Leia a posição antes de usar as setas")
            return
        self.rotor_manual_move(*target)

    def rotor_calibrate(self):
        pos = self.rotor.position
        if not self.rotor.connected or pos is None:
            QMessageBox.information(self, "Rotor", "Conecte o rotor e leia a posição antes de calibrar.")
            return
        new = calibrated_north_offset(pos[0], self.rotor_true_az.value(), self.rotor_offset.value())
        self.rotor_offset.setValue(new)
        self.rotor_save()
        self.rotor_log(f"Rotor: calibração do norte · leitura {pos[0]:.0f}° = real {self.rotor_true_az.value():.0f}° "
                       f"→ correção {new:+.0f}°")
        self.rotor_settings_status.setText(f"Norte calibrado: correção {new:+.0f}°")

    def rotor_short_test(self):
        pos = self.rotor.position
        if not self.rotor.connected or pos is None:
            QMessageBox.information(self, "Rotor", "Conecte o rotor e leia a posição antes do teste.")
            return
        prof = self.rotor_profile()
        start = pos
        there = jog_target(pos, 10 if pos[0] + 10 <= prof.az_max else -10, 0, prof)
        self.rotor_stop("teste curto")
        self.rotor_log(f"Rotor: teste curto AZ {start[0]:.0f}° → {there[0]:.0f}° → {start[0]:.0f}°")

        def task():
            self.rotor.move(there[0], there[1], prof)
            for _ in range(30):            # até ~30 s; PARAR (stop) interrompe no controlador
                time.sleep(1.0)
                p = self.rotor.read_position()
                if abs(p[0] - there[0]) <= prof.tolerance:
                    break
            return self.rotor.move(start[0], start[1], prof)
        self.background("rotor-move", task)

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
                 rotor_min_interval=self.rotor_interval.value(), rotor_prepos_s=self.rotor_prepos.value(),
                 rotor_min_el=self.rotor_min_el.value(), rotor_preference=self.rotor_pref.currentData() or "auto",
                 rotor_jog_step=self.rotor_jog_step.value())
        self.config.save()
        self.rotor_bar.setVisible(bool(v["rotor_enabled"]))
        for sc in getattr(self, "rotor_shortcuts", []):
            sc.setEnabled(bool(v["rotor_enabled"]))
        self.rotor_refresh_bar_title()
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

    # ------------------------------------------------------------------ botão ROTOR do topo (v1.7.2)
    TOP_STYLES = {
        "off": "color:#ffe7e7;background:#783437;border:1px solid #db565e",
        "busy": "color:#ffe4b0;background:#755225;border:1px solid #e0aa55",
        "on": "color:#ddfff0;background:#12533f;border:1px solid #36b88a",
    }

    def build_rotor_top_button(self, header):
        """Botão ROTOR ao lado de CAT e SDR: liga/desliga (conecta/desconecta) o controlador do rotor."""
        self.rotor_top_btn = QPushButton("ROTOR")
        self.rotor_top_btn.clicked.connect(self.rotor_top_clicked)
        header.addWidget(self.rotor_top_btn)
        self.rotor_set_top("off")

    def rotor_set_top(self, state):
        btn = getattr(self, "rotor_top_btn", None)
        if btn is None:
            return
        from .app import top_button_style
        btn.setStyleSheet(top_button_style(self.TOP_STYLES[state]))
        port = str(self.rotor_cfg("rotor_port")) or "sem porta"
        btn.setToolTip({"off": "Rotor desligado · clique para conectar o controlador",
                        "busy": "Rotor conectando · " + port,
                        "on": "Rotor conectado · " + port + " · clique para desconectar"}[state])
        btn.setEnabled(state != "busy")

    def rotor_top_clicked(self):
        self.rotor_toggle_connection()

    def rotor_toggle_connection(self):
        if self.rotor.connected:
            self.rotor_stop("desconectar")
            self.rotor_set_top("busy")
            self.background("rotor-close", self.rotor.close)
            return
        # v1.7.2 (bug 12/11): conectar com "Habilitar" desmarcado salvava o rotor como desabilitado, o que
        # agendava o fechamento da porta logo após abri-la e parava a leitura de posição (faixa em
        # DESCONECTADO e gauges parados). Conectar = rotor habilitado.
        if not self.rotor_enable.isChecked():
            self.rotor_enable.blockSignals(True)
            self.rotor_enable.setChecked(True)
            self.rotor_enable.blockSignals(False)
        self.rotor_save()
        port, baud = str(self.rotor_cfg("rotor_port")), int(self.rotor_cfg("rotor_baud"))
        if not port:
            QMessageBox.information(self, "Rotor", "Escolha a porta COM do rotor (ou use Detectar).")
            return
        self.rotor_settings_status.setText(f"Conectando ao rotor em {port}…")
        self.rotor_set_top("busy")
        self.background("rotor-connect", lambda: self.rotor.connect(port, baud))

    # ------------------------------------------------------------------ faixa ROTOR da aba Operação
    def build_rotor_bar(self, layout):
        """v1.7.1 (mockup aprovado): mini-bússola real × alvo, AZ/EL grandes, status, plano AOS→LOS,
        Rastrear/Estacionar/PARAR/Configurar… e seletor do rotor ativo. Só aparece com rotor habilitado."""
        from .app import label
        from .rotor_widgets import RotorCompass
        self.rotor_bar = QWidget()
        self.rotor_bar.setObjectName("rotorBar")
        self.rotor_bar.setStyleSheet("#rotorBar{border:1px solid #2c5d86;border-radius:4px}")
        outer = QVBoxLayout(self.rotor_bar); outer.setContentsMargins(6, 3, 6, 3); outer.setSpacing(2)
        self.rotor_title = label("ROTOR")
        self.rotor_title.setStyleSheet("font-size:11px;font-weight:800;color:#6cc7ff")
        outer.addWidget(self.rotor_title)
        row = QHBoxLayout(); row.setSpacing(10)
        self.rotor_compass = RotorCompass(size=76)
        row.addWidget(self.rotor_compass)
        pos_col = QVBoxLayout(); pos_col.setSpacing(0)
        self.rotor_pos_label = label("AZ —°  EL —°")
        self.rotor_pos_label.setStyleSheet("font-size:20px;font-weight:900;color:#5af08a")
        self.rotor_target_label = label("Alvo: —")
        self.rotor_target_label.setStyleSheet("font-size:11px;color:#f5c542")
        pos_col.addWidget(self.rotor_pos_label); pos_col.addWidget(self.rotor_target_label)
        row.addLayout(pos_col)
        st_col = QVBoxLayout(); st_col.setSpacing(2)
        chips = QHBoxLayout(); chips.setSpacing(4)
        self.rotor_state_chip = label("DESCONECTADO")
        self.rotor_mode_chip = label("")
        for chip in (self.rotor_state_chip, self.rotor_mode_chip):
            chips.addWidget(chip)
        chips.addStretch(1)
        st_col.addLayout(chips)
        # compatibilidade: rotor_label continua sendo a linha de status em texto
        self.rotor_label = label("ROTOR · desconectado")
        self.rotor_label.setStyleSheet("font-size:11px;color:#c5dbe7")
        st_col.addWidget(self.rotor_label)
        row.addLayout(st_col, 1)
        btn_col = QVBoxLayout(); btn_col.setSpacing(2)
        buttons = QHBoxLayout()
        self.rotor_park_btn = QPushButton("Estacionar")
        # v1.7.2: sem "Rastrear passagem"; o rotor rastreia sozinho o satélite selecionado acima do horizonte.
        # PARAR virou o estado: verde RASTREANDO / vermelho PARADO; o clique para (ou retoma) o automático.
        self.rotor_stop_btn = QPushButton("PARADO")
        self.rotor_stop_btn.setMinimumWidth(118)
        self.rotor_config_btn = QPushButton("Configurar…")
        self.rotor_config_btn.setToolTip("Configurações → Rotores")
        for w in (self.rotor_park_btn, self.rotor_stop_btn, self.rotor_config_btn):
            buttons.addWidget(w)
        btn_col.addLayout(buttons)
        sel = QHBoxLayout()
        sel.addWidget(label("Rotor ativo:"))
        self.rotor_active = QComboBox()
        for code, prof in PROFILES.items():
            self.rotor_active.addItem(prof.name, code)
        self.rotor_active.setCurrentIndex(max(0, self.rotor_active.findData(str(self.rotor_cfg("rotor_profile")))))
        self.rotor_active.setToolTip("Perfil/controlador em uso (os limites salvos em Configurações → Rotores)")
        sel.addWidget(self.rotor_active)
        hint = label("Esc / F12 = PARAR"); hint.setStyleSheet("font-size:10px;color:#ff9a9a")
        sel.addWidget(hint); sel.addStretch(1)
        btn_col.addLayout(sel)
        row.addLayout(btn_col)
        outer.addLayout(row)
        layout.addWidget(self.rotor_bar)
        self.rotor_bar.setVisible(bool(self.rotor_cfg("rotor_enabled")))
        self.rotor_park_btn.clicked.connect(self.rotor_park_manual)
        self.rotor_stop_btn.clicked.connect(self.rotor_state_clicked)
        self.rotor_set_state_button(False)
        self.rotor_config_btn.clicked.connect(lambda: self.open_settings("Rotores"))
        self.rotor_active.currentIndexChanged.connect(self.rotor_change_active)
        self.rotor_set_chips("DESCONECTADO", "")
        self.rotor_refresh_bar_title()
        from .qt_compat import QShortcut, QKeySequence
        self.rotor_shortcuts = []
        for key in ("Esc", "F12"):
            sc = QShortcut(QKeySequence(key), self)
            # Esc só na janela principal (diálogos e menus mantêm o Esc deles); F12 em qualquer janela do app
            sc.setContext(Qt.WindowShortcut if key == "Esc" else Qt.ApplicationShortcut)
            sc.activated.connect(self.rotor_shortcut_stop)
            sc.setEnabled(bool(self.rotor_cfg("rotor_enabled")))  # sem rotor, Esc/F12 ficam livres
            self.rotor_shortcuts.append(sc)

    def rotor_shortcut_stop(self):
        """Esc/F12: PARAR, só enquanto houver rotor habilitado (sem confirmação)."""
        if bool(self.rotor_cfg("rotor_enabled")):
            self.rotor_set_auto(False, "PARAR pelo operador (atalho)")

    def rotor_change_active(self, *_):
        code = self.rotor_active.currentData() or "g5400b"
        if code == self.rotor_cfg("rotor_profile"):
            return
        self.rotor_stop("troca do rotor ativo")
        self.rotor_model.setCurrentIndex(max(0, self.rotor_model.findData(code)))  # aplica limites do perfil
        self.rotor_save()

    def rotor_refresh_bar_title(self):
        prof = PROFILES.get(str(self.rotor_cfg("rotor_profile")), PROFILES["g5400b"])
        port = str(self.rotor_cfg("rotor_port") or "sem porta")
        if getattr(self, "rotor_title", None) is not None:
            self.rotor_title.setText(f"ROTOR · {prof.name} via {port}")
        if getattr(self, "rotor_active", None) is not None:
            self.rotor_active.blockSignals(True)
            self.rotor_active.setCurrentIndex(max(0, self.rotor_active.findData(str(self.rotor_cfg("rotor_profile")))))
            self.rotor_active.blockSignals(False)

    CHIP_STYLES = {
        "RASTREANDO": "#1d6b3a", "PRÉ-POSICIONANDO": "#6b5a1d", "ESTACIONADO": "#2c4f6b", "PARADO": "#33414f",
        "DESCONECTADO": "#5a2a2a", "ERRO": "#a32626", "AGUARDANDO AOS": "#2c4f6b",
    }

    def rotor_set_chips(self, state, mode):
        bg = self.CHIP_STYLES.get(state, "#33414f")
        self.rotor_state_chip.setText("● " + state)
        self.rotor_state_chip.setStyleSheet(f"font-size:11px;font-weight:800;color:#fff;background:{bg};"
                                            "border-radius:3px;padding:1px 6px")
        self.rotor_mode_chip.setVisible(bool(mode))
        self.rotor_mode_chip.setText("MODO " + mode.upper() if mode else "")
        self.rotor_mode_chip.setStyleSheet("font-size:11px;font-weight:800;color:#f5c542;background:#3a3010;"
                                           "border-radius:3px;padding:1px 6px")

    def rotor_show_position(self, pos):
        from .rotor_widgets import RotorCompass
        off = float(self.rotor_cfg("rotor_north_offset"))  # coordenadas do rotor → direção real
        real = RotorCompass.pointing(pos[0] - off, pos[1]) if pos else None
        # v1.7.2: o número grande mostra a mesma direção dos gauges (para onde a antena aponta); a leitura
        # crua do controlador (até 450°/180°, com flip) fica no tooltip e em Configurações → Rotores.
        raw = f"AZ {pos[0]:.0f}°  EL {pos[1]:.0f}°" if pos else "AZ —°  EL —°"
        text = f"AZ {real[0]:.0f}°  EL {real[1]:.0f}°" if real else raw
        self.rotor_pos_label.setText(text)
        self.rotor_pos_label.setToolTip("Direção da antena · leitura do controlador (GS-232 C2): " + raw)
        tgt = RotorCompass.pointing(self.rotor_target[0] - off, self.rotor_target[1]) if self.rotor_target else None
        flip = bool(self.rotor_plan and self.rotor_plan.get("mode") == "flip")
        self.rotor_compass.set_values(real, tgt, flip)
        if getattr(self, "rotor_settings_compass", None) is not None:
            self.rotor_settings_compass.set_values(real, tgt, flip)
            self.rotor_live.setText("Posição ao vivo: " + text + ("" if text == raw else f"  (controlador {raw})"))

    # ------------------------------------------------------------------ rastreamento automático (v1.7.2)
    def rotor_set_state_button(self, tracking):
        btn = getattr(self, "rotor_stop_btn", None)
        if btn is None:
            return
        from .i18n import translated
        loc = self.ui_language() if hasattr(self, "ui_language") else "pt-BR"
        tr = lambda t: translated(t, loc)
        if tracking:
            btn.setText(tr("RASTREANDO"))
            btn.setStyleSheet("font-weight:900;color:#ddfff0;background:#12533f;border:1px solid #36b88a;padding:4px 14px")
            btn.setToolTip(tr("Rastreando o satélite selecionado · clique (ou Esc/F12) para parar o rotor"))
        else:
            btn.setText(tr("PARADO"))
            btn.setStyleSheet("font-weight:900;color:#ffe7e7;background:#783437;border:1px solid #db565e;padding:4px 14px")
            btn.setToolTip(tr("Rotor parado · rastreia sozinho quando o satélite selecionado estiver acima do horizonte"
                              if self.rotor_auto else
                              "Rastreamento automático pausado pelo operador · clique para retomar"))

    def rotor_state_clicked(self):
        """RASTREANDO → para o rotor e pausa o automático; PARADO pausado → retoma o automático."""
        if self.rotor_auto:
            self.rotor_set_auto(False, "parado pelo operador")
        else:
            self.rotor_set_auto(True)

    def rotor_set_auto(self, on, reason=""):
        self.rotor_auto = bool(on)
        if on:
            self.rotor_plan = None
            self.rotor_plan_pass = None
            self.log("Rotor: rastreamento automático retomado")
        else:
            self.rotor_stop(reason or "PARAR pelo operador")
        self.rotor_set_state_button(self.rotor_tracking and self.rotor_auto)

    def rotor_toggle_tracking(self, on):
        """Compatibilidade (controle pela rede 'rotor_track'): liga/pausa o rastreamento automático."""
        self.rotor_set_auto(bool(on), "rastreamento desligado")

    def rotor_stop(self, reason=""):
        was = self.rotor_tracking
        self.rotor_tracking = False
        self.rotor_plan = None
        self.rotor_set_state_button(False)
        if self.rotor.connected:
            self.pending_jobs.discard("rotor-stop")
            self.background("rotor-stop", self.rotor.stop)
        if reason and (was or "PARAR" in reason):
            self.log("Rotor: parado (" + reason + ")")

    def rotor_park_manual(self):
        """Estacionar pelo operador: pausa o automático (senão o próximo segundo voltaria ao satélite)."""
        if self.rotor_auto:
            self.rotor_set_auto(False, "estacionar pelo operador")
        self.rotor_park()

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
        return plan_pass(track, self.rotor_profile(), str(self.rotor_cfg("rotor_preference")))

    def rotor_tick(self, now):
        if not bool(self.rotor_cfg("rotor_enabled")) or not self.rotor.connected:
            if getattr(self, "rotor_label", None) is not None and not self.rotor.connected:
                self.rotor_label.setText("Desconectado · Configurar… → Rotores")
                self.rotor_set_chips("DESCONECTADO", "")
            return
        self.rotor_request_read()
        pos = self.rotor.position
        text = "Posição " + (f"AZ {pos[0]:.0f}° EL {pos[1]:.0f}°" if pos else "AZ — EL —")
        self.rotor_show_position(pos)
        self.rotor_update_target_label()
        if hasattr(self, "lcd"):
            self.lcd.set_state(rotor=(f"ROT {pos[0]:.0f}/{pos[1]:.0f}" if pos else ""))
        if not self.rotor_auto or self.sat is None:
            self.rotor_tracking = False
            self.rotor_set_state_button(False)
            self.rotor_label.setText(text + (" · rastreamento automático pausado (clique em PARADO para retomar)"
                                             if not self.rotor_auto else " · nenhum satélite selecionado"))
            parked = pos is not None and abs(pos[0] - self.rotor_profile().park_az) <= 2 and abs(pos[1] - self.rotor_profile().park_el) <= 2
            self.rotor_set_chips("ESTACIONADO" if parked else "PARADO", "")
            return
        if self.rotor.failures >= 3:
            self.rotor_set_auto(False, "sem resposta do controlador")
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
            mode = self.rotor_plan["mode"]
            plan_txt = (f"Plano: AOS {event['aos'].astimezone().strftime('%H:%M')} → LOS "
                        f"{event['los'].astimezone().strftime('%H:%M')} · {mode}")
            if now >= event["los"]:
                self.rotor_tracking = False
                self.rotor_set_state_button(False)
                self.rotor_set_chips("ESTACIONADO", mode)
                self.rotor_label.setText(text + " · LOS: estacionando")
                if self.rotor_parked_pass != key:   # estaciona uma vez por passagem
                    self.rotor_parked_pass = key
                    self.rotor_park()
                return
            if now < event["aos"]:
                if (event["aos"] - now).total_seconds() > float(self.rotor_cfg("rotor_prepos_s")):
                    self.rotor_tracking = False
                    self.rotor_set_state_button(False)
                    self.rotor_set_chips("AGUARDANDO AOS", mode)
                    self.rotor_label.setText(plan_txt)
                    return
                target = self.rotor_plan["track"][0] if self.rotor_plan["track"] else None
                phase = "pré-posicionado no AOS"
                self.rotor_set_chips("PRÉ-POSICIONANDO", mode)
            else:
                p = position(self.sat, station, when=now + timedelta(seconds=2), ts=self.ts)
                target = to_rotor(p["azimuth"], p["elevation"], self.rotor_plan, prof,
                                  when=(now + timedelta(seconds=2)).timestamp(), current_az=pos[0] if pos else None)
                phase = "rastreando"
                self.rotor_set_chips("RASTREANDO", mode)
        except Exception as exc:
            self.rotor_set_chips("ERRO", "")
            self.rotor_label.setText(text + " · erro: " + str(exc)[:80])
            return
        if target is None:
            return
        if not self.rotor_tracking:
            self.log(f"Rotor: rastreamento automático de {self.sat_combo.currentText()} ({phase})")
        self.rotor_tracking = True
        self.rotor_set_state_button(True)
        self.rotor_target = target
        self.rotor_label.setText(plan_txt + f" · {phase}")
        if needs_move(target, pos, prof) and time.monotonic() - self.rotor.last_command_at >= prof.min_interval_s:
            self.background("rotor-move", lambda: self.rotor.move(target[0], target[1], prof))

    def rotor_update_target_label(self):
        try:
            if self.sat is None:
                raise ValueError
            from .core import position
            p = position(self.sat, self.saved_station(), ts=self.ts)
            self.rotor_target_label.setText(f"Alvo ({self.sat.name[:18]}): AZ {p['azimuth']:.0f}°  EL {p['elevation']:.0f}°")
            if not self.rotor_tracking:
                self.rotor_compass.set_values(self.rotor_compass.real, (p["azimuth"], max(0.0, p["elevation"])),
                                              self.rotor_compass.flip)
        except Exception:
            self.rotor_target_label.setText("Alvo: —")

    def rotor_map_payload(self, station):
        """Linha verde no mapa com a direção da antena (posição real do rotor), quando houver rotor ativo."""
        pos = getattr(self.rotor, "position", None)
        if not bool(self.rotor_cfg("rotor_enabled")) or not self.rotor.connected or pos is None:
            return None
        from .rotor import antenna_line
        from .rotor_widgets import RotorCompass
        az, el = RotorCompass.pointing(pos[0] - float(self.rotor_cfg("rotor_north_offset")), pos[1])
        return {"az": az, "el": el, "line": antenna_line(station.lat, station.lon, az)}

    # ------------------------------------------------------------------ resultados dos trabalhos
    def rotor_result(self, key, data) -> bool:
        if not key.startswith("rotor-"):
            return False
        if key == "rotor-connect":
            self.rotor_refresh_bar_title()
            self.rotor_connect_btn.setText("Desconectar")
            self.rotor_settings_status.setText(f"Rotor conectado · AZ {data[0]:.0f}° EL {data[1]:.0f}°")
            self.rotor_bar.setVisible(True)
            self.rotor_set_top("on")
            self.rotor_auto = True   # conectar arma o rastreamento automático
            self.rotor_set_state_button(False)
            self.rotor_set_chips("PARADO", "")
            self.rotor_label.setText("Conectado · " + str(self.rotor_cfg("rotor_port")))
            if data:
                self.rotor_show_position(data)
        elif key == "rotor-close":
            self.rotor_set_top("off")
            self.rotor_set_chips("DESCONECTADO", "")
            self.rotor_label.setText("Desconectado · Configurar… → Rotores")
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
            self.rotor_show_position(data)
        return True

    def rotor_failed(self, key, message) -> bool:
        if not key.startswith("rotor-"):
            return False
        if key == "rotor-connect":
            self.rotor_settings_status.setText("Rotor não conectou: " + message[:160])
            self.rotor.close()
            self.rotor_set_top("off")
        elif key == "rotor-close":
            self.rotor_set_top("on" if self.rotor.connected else "off")
        elif key == "rotor-move":
            self.rotor_set_chips("ERRO", "")
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
