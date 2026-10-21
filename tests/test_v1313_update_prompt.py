"""v1.3.13: ao detectar versão nova, pergunta se deseja atualizar."""
import time
from types import SimpleNamespace

from sat_tool import app as app_module
from sat_tool.app import MainWindow


class FakeBox:
    """Substitui QMessageBox registrando o diálogo e a resposta escolhida."""
    instances = []
    answer = "now"

    Question = AcceptRole = RejectRole = 0

    def __init__(self, parent):
        self.buttons = {}
        self.text = ""
        FakeBox.instances.append(self)

    def setIcon(self, *_):
        pass

    def setWindowTitle(self, *_):
        pass

    def setText(self, text):
        self.text = text

    def addButton(self, label, _role):
        button = object()
        self.buttons[label] = button
        return button

    def exec(self):
        return 0

    def clickedButton(self):
        return self.buttons["Atualizar agora" if FakeBox.answer == "now" else "Depois"]


class FakeConfig:
    def __init__(self):
        self.values = {"update_prompt_snooze": {}}
        self.saved = 0

    def save(self):
        self.saved += 1


def fake_window():
    win = SimpleNamespace(pending_jobs=set(), config=FakeConfig(), _update_prompted_version=None,
                          available_update=None, requested=[], logs=[])
    win.request_update = lambda manual=False: win.requested.append(manual)
    win.log = win.logs.append
    win.UPDATE_PROMPT_SNOOZE_SECONDS = MainWindow.UPDATE_PROMPT_SNOOZE_SECONDS
    win.maybe_prompt_update = lambda data: MainWindow.maybe_prompt_update(win, data)
    return win


def setup(monkeypatch):
    FakeBox.instances.clear()
    monkeypatch.setattr(app_module, "QMessageBox", FakeBox)
    monkeypatch.setattr(app_module.QApplication, "activeModalWidget", staticmethod(lambda: None))


def test_update_now_starts_the_version_button_flow(monkeypatch):
    setup(monkeypatch)
    FakeBox.answer = "now"
    win = fake_window()
    win.maybe_prompt_update(SimpleNamespace(version="9.9.9"))
    assert "Deseja atualizar agora?" in FakeBox.instances[0].text
    assert win.requested == [True]
    # A mesma versão não é perguntada de novo na sessão.
    win.maybe_prompt_update(SimpleNamespace(version="9.9.9"))
    assert len(FakeBox.instances) == 1


def test_later_snoozes_same_version_for_24_hours(monkeypatch):
    setup(monkeypatch)
    FakeBox.answer = "later"
    win = fake_window()
    win.maybe_prompt_update(SimpleNamespace(version="9.9.9"))
    assert win.requested == [] and win.config.saved == 1
    assert win.config.values["update_prompt_snooze"]["version"] == "9.9.9"
    win._update_prompted_version = None  # nova sessão
    win.maybe_prompt_update(SimpleNamespace(version="9.9.9"))
    assert len(FakeBox.instances) == 1
    # Versão mais nova pergunta de novo; adiamento vencido também.
    win.maybe_prompt_update(SimpleNamespace(version="9.9.10"))
    assert len(FakeBox.instances) == 2
    win._update_prompted_version = None
    win.config.values["update_prompt_snooze"] = {"version": "9.9.9", "at": time.time() - 25 * 3600}
    win.maybe_prompt_update(SimpleNamespace(version="9.9.9"))
    assert len(FakeBox.instances) == 3


def test_no_prompt_during_download_or_over_another_dialog(monkeypatch):
    setup(monkeypatch)
    win = fake_window()
    win.pending_jobs.add("update-download")
    win.maybe_prompt_update(SimpleNamespace(version="9.9.9"))
    assert FakeBox.instances == []
    win.pending_jobs.clear()
    later = []
    monkeypatch.setattr(app_module.QApplication, "activeModalWidget", staticmethod(lambda: object()))
    monkeypatch.setattr(app_module.QTimer, "singleShot", staticmethod(lambda ms, fn: later.append(ms)))
    win.maybe_prompt_update(SimpleNamespace(version="9.9.9"))
    assert FakeBox.instances == [] and later == [5000]
