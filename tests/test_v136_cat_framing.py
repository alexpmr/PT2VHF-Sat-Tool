"""v1.3.6: TS-2000 COM1 fragmentation observed on 2026-10-16.

Read-only query responses may arrive as "F", then "A00436799891;".
No CAT write or PTT may be retransmitted by the parser.
"""
import pytest
from sat_tool.cat import TS2000, RadioState


class SplitCAT:
    is_open = True
    timeout = 0.01

    def __init__(self, overrides=None):
        self.overrides = overrides or {}
        self.commands = []
        self.queue = []
        self.down = 436050000
        self.up = 145950000
        self.sub = 147120000

    def reset_input_buffer(self):
        self.queue = []

    def flush(self):
        pass

    def close(self):
        self.is_open = False

    def write(self, raw):
        command = raw.decode("ascii")
        self.commands.append(command)
        if command == "FA;":
            self.queue = [b"F", ("A%011d;" % self.down).encode("ascii")]
        elif command == "FB;":
            self.queue = [b"FB", ("%011d;" % self.up).encode("ascii")]
        elif command == "FC;":
            self.queue = [b"F", ("C%011d;" % self.sub).encode("ascii")]
        elif command == "SA;":
            self.queue = [b"?;", b"S", b"A1010000;"]
        elif command == "MD;":
            self.queue = [b"M", b"D4;"]
        elif command.startswith("FA") and command.endswith(";"):
            self.down = int(command[2:-1])
        elif command.startswith("FB") and command.endswith(";"):
            self.up = int(command[2:-1])
        else:
            raise AssertionError("Unexpected CAT write " + command)
        if command in self.overrides:
            self.queue = list(self.overrides[command])

    def read_until(self, delimiter):
        assert delimiter == b";"
        return self.queue.pop(0) if self.queue else b""


def radio(overrides=None):
    serial = SplitCAT(overrides)
    rig = TS2000()
    rig.port = serial
    rig.state = RadioState(connected=True, model="Kenwood TS-2000", sat=True)
    rig._last_optional_poll = 10**20
    return rig, serial


def test_split_frames_reassemble_to_complete_sa_fa_fb_fc_md():
    rig, serial = radio()
    st = rig.poll()
    assert st.sat is True
    assert st.downlink == 436050000
    assert st.uplink == st.vfo_b == 145950000
    assert st.sub_receiver == 147120000
    assert st.mode == "FM"
    assert serial.commands == ["SA;", "FA;", "FB;", "FC;", "MD;"]


def test_fragmented_cat_readback_confirms_tune_without_write_replay():
    rig, serial = radio()
    st = rig.set_frequencies(145848361, 436799908)
    assert st.downlink == 436799908 and st.uplink == 145848361
    assert serial.commands.count("FA00436799908;") == 1
    assert serial.commands.count("FB00145848361;") == 1
    assert not any(c.startswith(("FC0", "TX", "RX", "SA1")) for c in serial.commands)


def test_incomplete_reply_never_claims_success():
    rig, serial = radio({"FA;": [b"F", b"A00436799"]})
    with pytest.raises(TimeoutError, match="Sem resposta CAT completa para FA"):
        rig.poll()
    assert serial.commands == ["SA;", "FA;"]


def test_unrelated_complete_reply_is_not_accepted_for_fa():
    rig, serial = radio({"FA;": [b"MD4;FA00436050000;"]})
    assert rig.poll().downlink == 436050000
