"""v1.4.0: FT-817/818 (CAT 5 bytes) e rigctld com equipamentos simulados; nunca aciona PTT."""
import pytest

from sat_tool import rigs


class FakeFT817:
    """Simula a porta serial do FT-817: registra comandos e responde leituras."""
    def __init__(self, tx=False):
        self.writes, self.pending, self.tx = [], b"", tx
        self.freq = rigs.bcd_frequency(145_800_000)
    def reset_input_buffer(self): self.pending = b""
    def write(self, data):
        self.writes.append(bytes(data))
        op = data[4]
        if op == 0x03: self.pending = self.freq + b"\x08"
        elif op == 0xF7: self.pending = bytes([0x00 if self.tx else 0xFF])
        elif op == 0x01: self.freq = data[:4]
    def read(self, n):
        out, self.pending = self.pending[:n], self.pending[n:]
        return out
    def close(self): pass


def test_bcd_frequency_examples():
    assert rigs.bcd_frequency(435_637_710) == bytes([0x43, 0x56, 0x37, 0x71])
    assert rigs.parse_bcd_frequency(bytes([0x14, 0x59, 0x65, 0x77])) == 145_965_770
    with pytest.raises(ValueError):
        rigs.bcd_frequency(1_200_000_000)


def test_ft817_rx_and_split_tx_toggles_vfo_and_never_ptt():
    fake = FakeFT817()
    rig = rigs.FT817()
    rig.connect("COMX", 9600, serial_factory=lambda: fake)
    assert rig.read_frequency() == (145_800_000, "FM")
    fake.writes.clear()
    assert rig.set_rx(435_637_710, "USB")
    assert rig.set_tx(145_965_770, "LSB", same_rig_rx=True)
    ops = [w[4] for w in fake.writes]
    assert 0x02 in ops and ops.count(0x81) == 2           # split ligado, VFO B e volta
    assert bytes([0x00, 0, 0, 0, 0x07]) in fake.writes      # LSB
    assert bytes([0x01, 0, 0, 0, 0x07]) in fake.writes      # USB
    assert not {0x08, 0x88} & set(ops)                      # PTT nunca comandado


def test_ft817_holds_frequency_while_transmitting():
    fake = FakeFT817(tx=True)
    rig = rigs.FT817()
    rig.connect("COMX", 9600, serial_factory=lambda: fake)
    fake.writes.clear()
    assert rig.set_tx(145_900_000, "FM") is False
    assert [w[4] for w in fake.writes] == [0xF7]


class FakeSocket:
    def __init__(self):
        self.sent, self.out = [], b""
    def settimeout(self, t): pass
    def sendall(self, data):
        cmd = data.decode().strip()
        self.sent.append(cmd)
        self.out += (b"145800000\n" if cmd == "f" else b"0\n" if cmd == "t" else b"RPRT 0\n")
    def recv(self, n):
        out, self.out = self.out[:n], self.out[n:]
        return out
    def close(self): pass


def test_rigctld_rx_and_split_tx():
    sock = FakeSocket()
    rig = rigs.Rigctld()
    rig.connect(sock_factory=lambda: sock)
    rig.set_rx(435_640_000, "USB")
    rig.set_tx(145_960_000, "LSB", same_rig_rx=True)
    assert sock.sent[1:] == ["F 435640000", "M USB 2400", "t", "S 1 VFOB", "I 145960000", "X LSB 2400"]


def test_dispatcher_threshold_and_interval():
    d = rigs.DopplerDispatcher(threshold_hz=10, min_interval_s=0.5)
    assert d.due("rx", 100, "FM", now=0)
    d.mark("rx", 100, "FM", now=0)
    assert not d.due("rx", 105, "FM", now=1)
    assert not d.due("rx", 200, "FM", now=0.2)
    assert d.due("rx", 200, "FM", now=1)
    assert d.due("rx", 100, "USB", now=0.1)


def test_normalize_mode_from_satnogs_names():
    assert rigs.normalize_mode("FM") == "FM"
    assert rigs.normalize_mode("AFSK") == "PKT"
    assert rigs.normalize_mode("SSB") == "USB"
    assert rigs.normalize_mode("CW") == "CW"
