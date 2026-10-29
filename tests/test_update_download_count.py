"""Atualização baixada pelo app soma no contador de downloads do site."""
import unittest
from types import SimpleNamespace

from sat_tool import updater


def manifest(**extra):
    entry = {"name": "PT2VHF-Sat-Tool-v9.0.0-Win11-x64-Setup.exe",
             "url": "https://www.pt2vhf.com/downloads/sat-tool/PT2VHF-Sat-Tool-v9.0.0-Win11-x64-Setup.exe",
             "size": 1000, "sha256": "a" * 64, **extra}
    return {"schema": 1, "product": "sat", "source": updater.ORIGIN, "status": "available",
            "version": "9.0.0", "files": [entry]}


class DownloadCount(unittest.TestCase):
    def test_counter_key_comes_from_the_site_manifest(self):
        up = updater.select_release(manifest(counterKey="win-setup", category="windows-installer"), "1.0.0", "Win11-x64", "Setup")
        self.assertEqual(up.counter_key, "win-setup")
        up = updater.select_release(manifest(category="windows-installer"), "1.0.0", "Win11-x64", "Setup")
        self.assertEqual(up.counter_key, "windows-installer")

    def test_posts_count_and_never_breaks_update(self):
        up = updater.select_release(manifest(counterKey="win-setup"), "1.0.0", "Win11-x64", "Setup")
        calls = []

        def post(url, **kw):
            calls.append((url, kw["data"]))
            return SimpleNamespace(status_code=204)
        self.assertTrue(updater.record_download_count(up, post=post))
        self.assertEqual(calls, [("https://www.pt2vhf.com/download.php",
                                  {"action": "count", "product": "sat", "category": "win-setup"})])

        def broken(url, **kw):
            raise OSError("offline")
        self.assertFalse(updater.record_download_count(up, post=broken))

    def test_not_counted_outside_the_packaged_app(self):
        up = updater.select_release(manifest(counterKey="win-setup"), "1.0.0", "Win11-x64", "Setup")
        self.assertFalse(updater.record_download_count(up))


if __name__ == "__main__":
    unittest.main()
