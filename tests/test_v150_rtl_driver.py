"""v1.5.0: RTL-SDR reconhecido (regressão do buffer ctypes) e plug and play do driver."""
import ctypes
import json

from sat_tool import rtl_driver, sdr


class FakeLib:
    """Imita a librtlsdr com os argtypes do pyrtlsdr: buffers devem ser POINTER(c_ubyte)."""
    def __init__(self, count=1):
        self.count = count
        f = lambda *a: 0
        self._strings = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_ubyte),
                                         ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte))(self._fill)
    def _fill(self, index, m, p, s):
        for buf, text in ((m, b"Realtek"), (p, b"RTL2838UHIDIR"), (s, b"00000001")):
            for i, ch in enumerate(text + b"\0"):
                buf[i] = ch
        return 0
    def rtlsdr_get_device_count(self): return self.count
    def rtlsdr_get_device_name(self, i): return b"Generic RTL2832U OEM"
    def rtlsdr_get_device_usb_strings(self, i, m, p, s): return self._strings(i, m, p, s)


def test_detect_lists_connected_dongle_with_serial(monkeypatch):
    monkeypatch.setattr(sdr, "_librtlsdr", lambda: FakeLib())
    devices, message = sdr.detect_devices()
    assert message == "" and len(devices) == 1
    assert devices[0].name == "Generic RTL2832U OEM" and devices[0].serial == "00000001"


def test_serial_failure_keeps_device(monkeypatch):
    lib = FakeLib()
    def boom(*a): raise TypeError("expected LP_c_ubyte instance instead of c_char_Array_256")
    lib.rtlsdr_get_device_usb_strings = boom
    monkeypatch.setattr(sdr, "_librtlsdr", lambda: lib)
    devices, _ = sdr.detect_devices()
    assert len(devices) == 1 and devices[0].serial == ""


def test_windows_pnp_parsing_and_interface0_only():
    data = [
        {"InstanceId": "USB\\VID_0BDA&PID_2838\\00000001", "Service": "usbccgp", "Status": "OK"},
        {"InstanceId": "USB\\VID_0BDA&PID_2838&MI_00\\7&1", "Service": "RTL2832UUSB", "Status": "OK"},
        {"InstanceId": "USB\\VID_0BDA&PID_2838&MI_01\\7&2", "Service": "", "Status": "Error"},
        {"InstanceId": "USB\\VID_046D&PID_C52B\\x", "Service": "HidUsb"},
    ]
    ifaces = rtl_driver.parse_pnp_json(json.dumps(data))
    assert [(i.mi, i.service) for i in ifaces] == [(0, "RTL2832UUSB"), (1, "")]
    pending = rtl_driver.windows_needs_winusb(ifaces)
    assert [i.mi for i in pending] == [0]  # interface 1 nunca é tocada
    ok = rtl_driver.parse_pnp_json(json.dumps({"InstanceId": "USB\\VID_0BDA&PID_2838&MI_00\\7", "Service": "WinUSB"}))
    assert rtl_driver.windows_needs_winusb(ok) == []


def test_wdi_arguments_winusb_interface0(tmp_path):
    args = rtl_driver.wdi_arguments("2838", tmp_path)
    assert args[args.index("-t") + 1] == "0" and args[args.index("-i") + 1] == "0"
    assert args[args.index("-v") + 1] == "0x0BDA" and args[args.index("-p") + 1] == "0x2838"


def test_linux_setup_detection(tmp_path):
    rules = tmp_path / "rules"; rules.mkdir()
    module = tmp_path / "dvb_usb_rtl28xxu"; module.mkdir()
    reasons = rtl_driver.linux_needs_setup((rules,), module)
    assert len(reasons) == 2
    (rules / "20-rtl.rules").write_text(rtl_driver.RULES_TEXT)
    module.rmdir()
    assert rtl_driver.linux_needs_setup((rules,), module) == []
    usb = tmp_path / "usb" / "1-1"; usb.mkdir(parents=True)
    (usb / "idVendor").write_text("0bda\n"); (usb / "idProduct").write_text("2838\n")
    assert rtl_driver.linux_usb_present(tmp_path / "usb")
    assert "dvb_usb_rtl28xxu" in rtl_driver.linux_setup_script()
