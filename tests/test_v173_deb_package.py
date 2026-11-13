"""Backlog 12/11/2026: pacote .deb para Ubuntu/Linux Mint."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="dpkg-deb só existe no Linux Debian/Ubuntu")
def test_build_deb_layout(tmp_path):
    app = tmp_path / "PT2VHF-Sat-Tool-v1.2.3"
    (app / "_internal").mkdir(parents=True)
    exe = app / "PT2VHF-Sat-Tool-v1.2.3"
    exe.write_text("#!/bin/sh\necho ok\n"); exe.chmod(0o755)
    (app / "_internal" / "x.so").write_bytes(b"x")
    out = tmp_path / "out"
    subprocess.run([sys.executable, str(ROOT / "scripts/build_deb.py"), "--version", "1.2.3",
                    "--app-dir", str(app), "--out", str(out)], check=True)
    deb = out / "PT2VHF-Sat-Tool-v1.2.3-Linux-x64.deb"
    assert deb.read_bytes()[:8] == b"!<arch>\n"
    info = subprocess.run(["dpkg-deb", "-f", str(deb)], capture_output=True, text=True, check=True).stdout
    assert "Package: pt2vhf-sat-tool" in info and "Version: 1.2.3" in info and "Architecture: amd64" in info
    assert "libasound2 | libasound2t64" in info and "libxcb-cursor0" in info
    files = subprocess.run(["dpkg-deb", "-c", str(deb)], capture_output=True, text=True, check=True).stdout
    for path in ("./opt/pt2vhf-sat-tool/PT2VHF-Sat-Tool-v1.2.3", "./usr/share/applications/pt2vhf-sat-tool.desktop",
                 "./usr/lib/udev/rules.d/60-pt2vhf-rtl-sdr.rules", "./etc/modprobe.d/pt2vhf-blacklist-rtl-sdr.conf",
                 "./usr/bin/pt2vhf-sat-tool -> /opt/pt2vhf-sat-tool/PT2VHF-Sat-Tool-v1.2.3"):
        assert path in files, path
    assert "root/root" in files and list(out.iterdir()) == [deb]   # pasta de montagem removida


def test_deb_is_built_validated_and_published():
    wf = (ROOT / ".github/workflows/windows.yml").read_text(encoding="utf-8")
    assert "scripts/build_deb.py" in wf and "Linux-x64.deb" in wf and "apt-get install -y -q \"./$deb\"" in wf
    site = (ROOT / "scripts/publish_sat_to_site.py").read_text(encoding="utf-8")
    assert '"Linux-x64.deb"' in site and 'b"!<arch>\\n"' in site
