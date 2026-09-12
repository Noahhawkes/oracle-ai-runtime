"""Smoke tests for Noah.Physical Trusted Build Mode (core/trusted_build.py).

Proves low-risk LOCAL actions auto-approve when trusted mode is on, while
destructive/external/secret/safety actions still require Guard, and that the
mode can be turned off. No LLM, no network, isolated state file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import trusted_build as tb  # noqa: E402


def _isolate(tmp_path):
    tb._STATE_FILE = tmp_path / "trusted_build_state.json"


def test_safe_local_manifest_write_auto_approves(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    d = tb.decide("write_manifest", str(tb.RUNTIME_ROOT / "intake" / "manifests" / "m.json"))
    assert d.auto_approved is True and d.guarded is False


def test_safe_local_code_file_creation_auto_approves(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    d = tb.decide("create_code_file", str(tb.RUNTIME_ROOT / "core" / "new_feature.py"))
    assert d.auto_approved is True


def test_delete_still_requires_guard(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    d = tb.decide("delete", str(tb.RUNTIME_ROOT / "core" / "new_feature.py"))
    assert d.guarded is True and d.auto_approved is False


def test_env_access_still_blocks(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    d = tb.decide("edit_code_file", str(tb.RUNTIME_ROOT / ".env"))
    assert d.guarded is True
    # Editing safety/approval code is likewise guarded even in trusted mode.
    d2 = tb.decide("edit_code_file", str(tb.RUNTIME_ROOT / "core" / "approval_center.py"))
    assert d2.guarded is True


def test_external_network_actions_require_guard(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(True)
    assert tb.decide("network").guarded is True
    assert tb.decide("external_api").guarded is True
    assert tb.decide("git_push").guarded is True
    assert tb.decide("change_safe_sleep").guarded is True
    # Outside the runtime root is always guarded.
    assert tb.decide("edit_code_file", "C:\\Users\\noahh\\x.py").guarded is True


def test_trusted_mode_can_be_turned_off(tmp_path):
    _isolate(tmp_path)
    tb.set_trusted_build(False)
    assert tb.is_trusted_build() is False
    # With trusted mode off, a low-risk local action falls back to Guard.
    d = tb.decide("write_manifest", str(tb.RUNTIME_ROOT / "intake" / "manifests" / "m.json"))
    assert d.guarded is True


def test_module_smoke_runner_passes(tmp_path):
    _isolate(tmp_path)
    assert tb.run_smoke_tests() == 0
