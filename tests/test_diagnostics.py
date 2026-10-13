"""Selftest should capture import failure before GUI startup."""
import json
from sat_tool.diagnostics import run_self_test

def test_failure_report(tmp_path, monkeypatch):
    import builtins
    original = builtins.__import__
    def fail_numpy(name, *args, **kwargs):
        if name == 'numpy':
            raise ImportError('simulated native DLL failure')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',fail_numpy)
    path = tmp_path / 'result.json'
    assert run_self_test(str(path),'PySide6') == 1
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['status'] == 'failed'
    assert 'simulated native DLL failure' in data['error']
