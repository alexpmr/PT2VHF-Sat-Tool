"""v1.5.0: CAT autodetectado — porta/velocidade aleatórias, porta ocupada, outros aparelhos."""
import threading

from sat_tool import cat_scan, rigs


class FakePort:
    def __init__(self, kind, baud, want_baud, stop, want_stop):
        self.kind, self.ok = kind, (baud == want_baud and stop == want_stop)
        self.out, self.writes = b"", []
    def reset_input_buffer(self): self.out = b""
    def write(self, data):
        self.writes.append(bytes(data))
        if not self.ok:
            self.out = b"\x07garbage"
        elif self.kind == "ts" and data == b"ID;":
            self.out = b"ID019;"
        elif self.kind == "ft" and data == b"\x00\x00\x00\x00\x03":
            self.out = rigs.bcd_frequency(145_900_000) + b"\x08"
        elif self.kind == "gps":
            self.out = b"$GPGGA,123519,4807.038,N*47\r\n"
    def read(self, n):
        out, self.out = self.out[:n], self.out[n:]
        return out
    def close(self): pass


def factory_for(table):
    opened = []
    def factory(port, baud, stop):
        spec = table[port]
        if spec == "busy":
            raise PermissionError("could not open port: Access is denied")
        p = FakePort(spec[0], baud, spec[1], stop, spec[2])
        opened.append((port, baud, p))
        return p
    factory.opened = opened
    return factory


def test_finds_ts2000_on_random_port_and_speed_skipping_busy_and_gps():
    f = factory_for({"COM3": "busy", "COM4": ("gps", 9600, 1), "COM7": ("ts", 19200, 1)})
    found, report = cat_scan.scan(["COM3", "COM4", "COM7"], serial_factory=f)
    assert (found.model, found.port, found.baud, found.stopbits) == ("TS-2000", "COM7", 19200, 1)
    assert any("ocupada" in r for r in report) and any("COM4" in r for r in report)
    # somente comandos de identificação foram enviados (sem PTT)
    sent = {w for _, _, p in f.opened for w in p.writes}
    assert sent <= {b"ID;", b"\x00\x00\x00\x00\x03"}


def test_finds_ft817_and_prefers_saved_port():
    f = factory_for({"/dev/ttyUSB0": ("ft", 38400, 2), "/dev/ttyUSB1": ("gps", 4800, 1)})
    found, _ = cat_scan.scan(["/dev/ttyUSB1", "/dev/ttyUSB0"], preferred=("/dev/ttyUSB0", 38400), serial_factory=f)
    assert (found.model, found.port, found.baud) == ("FT-817", "/dev/ttyUSB0", 38400)
    assert f.opened[0][0] == "/dev/ttyUSB0"


def test_no_radio_and_cancel():
    f = factory_for({"COM1": ("gps", 9600, 1)})
    found, report = cat_scan.scan(["COM1"], serial_factory=f)
    assert found is None and report
    ev = threading.Event(); ev.set()
    assert cat_scan.scan(["COM1"], cancel=ev, serial_factory=f) == (None, ["Varredura cancelada"])
