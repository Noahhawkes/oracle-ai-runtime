from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
KEEPER_PATH = ROOT / "tools" / "witness" / "oracle_keeper.py"


def _load_keeper():
    spec = importlib.util.spec_from_file_location("oracle_keeper_under_test", KEEPER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_keeper_health_uses_real_runtime_endpoint():
    keeper = _load_keeper()

    assert keeper.RUNTIME_HOST == "127.0.0.1"
    assert keeper.RUNTIME_PORT == 7781
    assert keeper.HEALTH == "http://127.0.0.1:7781/health"


def test_keeper_does_not_launch_duplicate_when_port_is_occupied(monkeypatch, tmp_path):
    keeper = _load_keeper()
    launched: list[bool] = []

    monkeypatch.setattr(keeper, "LOG", tmp_path / "keeper.log")
    monkeypatch.setattr(keeper, "server_alive", lambda: False)
    monkeypatch.setattr(keeper, "server_port_open", lambda: True)
    monkeypatch.setattr(keeper, "launch_server", lambda: launched.append(True))
    monkeypatch.setattr(keeper, "ensure_watcher", lambda name, script: None)
    monkeypatch.setattr(keeper, "heartbeat", lambda server_ok: None)

    class StopFlag:
        def exists(self) -> bool:
            return False

    monkeypatch.setattr(keeper, "STOP_FLAG", StopFlag())

    def stop_after_iteration(_seconds):
        raise SystemExit

    monkeypatch.setattr(keeper.time, "sleep", stop_after_iteration)

    with pytest.raises(SystemExit):
        keeper.main()

    assert launched == []
    assert "not launching duplicate" in (tmp_path / "keeper.log").read_text(encoding="utf-8")
