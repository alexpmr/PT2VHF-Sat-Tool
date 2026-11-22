"""v1.9.4 (pedido 21/11/2026): CAT ICOM e Yaesu para satélite.

- ICOM IC-9700/910/9100/820/821/970 com RX e TX no mesmo rádio: SUB = RX, MAIN = TX (o split VFO A/B não cruza
  145/435 MHz nesses rádios); modo satélite ligado por CI-V onde existe.
- Yaesu FT-847: modo SAT nativo (SAT RX 11/17, SAT TX 21/27), CAT ON antes de tudo.
- Yaesu CAT texto (FT-991/991A…): FA/FB de 9 dígitos, MD0x, nunca PTT.
"""
from sat_tool import rigs
from test_v190_radios_dde_forecast import FakeCiv


class DualCiv(FakeCiv):
    """IC-9700: guarda frequência e modo por banda selecionada (07 D0 = MAIN, 07 D1 = SUB)."""

    def __init__(self):
        super().__init__(address=0xA2, transmitting=False)
        self.band, self.bands, self.sat = "MAIN", {"MAIN": [0, 0], "SUB": [0, 0]}, False

    def write(self, frame):
        cmd, payload = frame[4], frame[5:-1]
        if frame[2] == self.address:
            if cmd == 0x07 and payload in (b"\xD0", b"\xD1"):
                self.band = "MAIN" if payload == b"\xD0" else "SUB"
            elif cmd == 0x05:
                self.bands[self.band][0] = rigs.parse_civ_frequency(payload)
            elif cmd == 0x06:
                self.bands[self.band][1] = payload[0]
            elif cmd == 0x16 and payload == b"\x5A\x01":
                self.sat = True
        super().write(frame)


def _ptt_frames(written):
    return [f for f in written if f[4] == 0x1C and len(f) > 7 and f[6] == 0x01]


def test_icom_9700_same_rig_uses_sub_for_rx_main_for_tx_and_sat_mode():
    bus = DualCiv()
    rig = rigs.Icom(address=rigs.ICOM_ADDRESSES["IC-9700"])
    rig.connect("COM3", 19200, serial_factory=lambda: bus)
    assert rig.model == "IC-9700" and rig.dual_band and rig.name.startswith("ICOM IC-9700")
    rig.use_same_rig(True)
    assert rig.set_rx(435_795_120, "FM") and rig.set_tx(145_850_340, "FM", same_rig_rx=True)
    assert bus.bands["SUB"] == [435_795_120, 0x05] and bus.bands["MAIN"] == [145_850_340, 0x05]
    assert bus.sat and not any(f[4] == 0x0F for f in bus.written)       # sem split VFO A/B
    # SSB linear invertido: LSB no uplink, USB no downlink
    rig.set_rx(145_960_000, "USB"); rig.set_tx(435_640_000, "LSB", same_rig_rx=True)
    assert bus.bands["SUB"] == [145_960_000, 0x01] and bus.bands["MAIN"] == [435_640_000, 0x00]
    assert not _ptt_frames(bus.written)


def test_icom_single_band_rig_keeps_vfo_split():
    bus = FakeCiv(transmitting=False)
    rig = rigs.Icom(address=0x56)       # IC-746
    rig.connect("COM3", 9600, serial_factory=lambda: bus)
    rig.use_same_rig(True)
    assert not rig.dual_band
    rig.set_tx(145_850_000, "FM", same_rig_rx=True)
    assert any(f[4] == 0x0F and f[5] == 0x01 for f in bus.written)     # SPLIT ON como antes
    assert not any(f[4] == 0x07 and f[5] in (0xD0, 0xD1) for f in bus.written)


class FakeFT847:
    def __init__(self):
        self.out, self.cmds = b"", []
        self.freq = {0x01: None, 0x11: None, 0x21: None}
        self.mode = {0x07: None, 0x17: None, 0x27: None}

    def reset_input_buffer(self):
        self.out = b""

    def write(self, data):
        data = bytes(data); self.cmds.append(data); op = data[4]
        if op in self.freq:
            self.freq[op] = rigs.parse_bcd_frequency(data)
        elif op in self.mode:
            self.mode[op] = data[0]
        elif op in (0x03, 0x13, 0x23):
            self.out += rigs.bcd_frequency(145_800_000) + b"\x08"

    def read(self, n):
        d, self.out = self.out[:n], self.out[n:]
        return d

    def close(self):
        pass


def test_ft847_sat_mode_full_duplex():
    radio = FakeFT847()
    rig = rigs.FT847()
    rig.connect("COM4", 57600, serial_factory=lambda: radio)
    assert radio.cmds[0] == b"\x00\x00\x00\x00\x00"                      # CAT ON primeiro
    rig.use_same_rig(True)
    assert rig.set_rx(435_795_120, "FM") and rig.set_tx(145_850_340, "FM", same_rig_rx=True)
    assert b"\x00\x00\x00\x00\x4E" in radio.cmds                         # SAT ON
    assert radio.freq[0x11] == 435_795_120 and radio.freq[0x21] == 145_850_340
    assert radio.mode[0x17] == 0x08 and radio.mode[0x27] == 0x08
    rig.set_rx(145_960_000, "USB"); rig.set_tx(435_640_000, "LSB", same_rig_rx=True)
    assert radio.mode[0x17] == 0x01 and radio.mode[0x27] == 0x00
    assert radio.freq[0x01] is None                                       # VFO principal intocado
    rig.disconnect()
    assert radio.cmds[-1] == b"\x00\x00\x00\x00\x80"                     # CAT OFF


def test_ft847_alone_uses_main_vfo():
    radio = FakeFT847(); rig = rigs.FT847()
    rig.connect("COM4", 57600, serial_factory=lambda: radio)
    rig.set_rx(145_800_000, "FM")
    assert radio.freq[0x01] == 145_800_000 and b"\x00\x00\x00\x00\x4E" not in radio.cmds


class FakeYaesuText:
    def __init__(self, tx="0"):
        self.out, self.sent, self.tx = b"", "", tx
        self.fa, self.fb, self.md = 145_800_000, 0, "4"

    def reset_input_buffer(self):
        self.out = b""

    def write(self, data):
        text = data.decode(); self.sent += text
        for cmd in filter(None, text.split(";")):
            if cmd == "FA":
                self.out += f"FA{self.fa:09d};".encode()
            elif cmd == "MD0":
                self.out += f"MD0{self.md};".encode()
            elif cmd == "ID":
                self.out += b"ID0670;"
            elif cmd == "TX":
                self.out += f"TX{self.tx};".encode()
            elif cmd.startswith("FA"):
                self.fa = int(cmd[2:])
            elif cmd.startswith("FB"):
                self.fb = int(cmd[2:])
            elif cmd.startswith("MD0"):
                self.md = cmd[3]

    def read(self, n):
        d, self.out = self.out[:n], self.out[n:]
        return d

    def close(self):
        pass


def test_yaesu_text_ft991a_rx_vfo_a_tx_vfo_b_no_ptt():
    radio = FakeYaesuText()
    rig = rigs.YaesuText()
    rig.connect("COM5", 38400, serial_factory=lambda: radio)
    assert rig.name == "FT-991A"
    rig.use_same_rig(True)
    assert rig.set_rx(435_795_120, "FM") and rig.set_tx(145_850_340, "FM", same_rig_rx=True)
    assert radio.fa == 435_795_120 and radio.fb == 145_850_340
    assert "FA435795120;MD04;" in radio.sent and "FB145850340;" in radio.sent and "SV;MD04;SV;" in radio.sent
    n = radio.sent.count("SV;")
    rig.set_tx(145_850_400, "FM", same_rig_rx=True)
    assert radio.sent.count("SV;") == n                                  # modo igual: não troca A/B de novo
    for ptt in ("TX1;", "TX2;"):
        assert ptt not in radio.sent


def test_yaesu_text_waits_while_transmitting():
    radio = FakeYaesuText(tx="1"); rig = rigs.YaesuText()
    rig.connect("COM5", 38400, serial_factory=lambda: radio)
    assert rig.set_rx(435_000_000, "FM") is False and radio.fa == 145_800_000


def test_new_rigs_are_offered_in_the_equipment_list():
    assert {"FT-847", "YAESU", "ICOM", "FT-817"} <= set(rigs.RIG_MODELS)
    assert rigs.icom_model_for_address(0xA2) == "IC-9700" and rigs.icom_model_for_address(0x60) == "IC-910"
