"""Smoke test: every displayed runtime port matches the configured runtime port.

The runtime binds one port (oracle_server). Operational receipts, health
checks, and SourceMap runtime strings must report THAT port — not a stale
hardcoded 7777. This test pins the configured port to a known value and proves
the displayed surfaces report it (and never the stale literal), while the
preview/dev port (7778) is left untouched.

No LLM, no network, no server boot.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import runtime_config  # noqa: E402


def _reset_env():
    os.environ.pop("ORACLE_PORT", None)
    os.environ.pop("ORACLE_HOST", None)


def test_default_runtime_port_is_7781_preview_untouched():
    _reset_env()
    assert runtime_config.runtime_port() == 7781
    assert runtime_config.DEFAULT_RUNTIME_PORT == 7781
    # Preview/dev must stay on its own fixed port.
    assert runtime_config.PREVIEW_PORT == 7778
    assert runtime_config.PREVIEW_PORT != runtime_config.runtime_port()


def test_set_runtime_port_overrides_everywhere():
    try:
        runtime_config.set_runtime_port(9000)
        assert runtime_config.runtime_port() == 9000
        assert runtime_config.runtime_authority() == "localhost:9000"
        assert runtime_config.runtime_base_url(host="127.0.0.1") == "http://127.0.0.1:9000"
    finally:
        _reset_env()


def test_set_runtime_port_rejects_invalid():
    import pytest

    with pytest.raises(ValueError):
        runtime_config.set_runtime_port(0)
    with pytest.raises(ValueError):
        runtime_config.set_runtime_port(99999)
    _reset_env()


def test_operational_state_string_reports_configured_port():
    import operational_state as ops

    try:
        runtime_config.set_runtime_port(7781)
        text = ops.summarize_operational_state()
        assert f"localhost:{runtime_config.runtime_port()}" in text
        assert "localhost:7777" not in text

        # And it tracks an override rather than any baked-in literal.
        runtime_config.set_runtime_port(8123)
        text2 = ops.summarize_operational_state()
        assert "localhost:8123" in text2
        assert "localhost:7781" not in text2
    finally:
        _reset_env()


def test_operational_state_runtime_dict_carries_port():
    import operational_state as ops

    try:
        runtime_config.set_runtime_port(7781)
        rt = ops.build_operational_state()["verified"]["runtime"]
        assert rt["runtime_port"] == runtime_config.runtime_port()
        # The stale port-named key must be gone.
        assert "localhost_7777" not in rt
    finally:
        _reset_env()


def test_capability_broker_health_probe_uses_configured_port():
    import capability_broker as cb

    try:
        runtime_config.set_runtime_port(8200)
        available, meta = cb._available_web()
        assert meta["port"] == 8200
        assert isinstance(available, bool)
    finally:
        _reset_env()


def test_runtime_diagnostics_reports_configured_port():
    # Importing oracle_server must not boot the server (env guard set above).
    import oracle_server

    try:
        runtime_config.set_runtime_port(8300)
        diag = oracle_server._runtime_diagnostics()
        assert diag["server"]["port"] == 8300
        assert diag["server"]["host"] == runtime_config.runtime_host()
    finally:
        _reset_env()
