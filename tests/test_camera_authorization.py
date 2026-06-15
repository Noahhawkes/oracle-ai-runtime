"""Tests for bounded in-memory camera authorization (LOOK ONCE gate)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import camera_authorization as ca  # noqa: E402


def setup_function(_):
    ca._reset_for_tests()


def test_create_then_validate_ok():
    rec = ca.create_authorization("sess-1", "dev-A")
    ok, reason = ca.validate(rec["authorization_id"], "sess-1", "dev-A")
    assert ok and reason == "ok"


def test_missing_authorization_rejected():
    ok, reason = ca.validate(None, "sess-1", "dev-A")
    assert not ok and reason == "unknown_authorization"


def test_unknown_authorization_rejected():
    ok, reason = ca.validate("cam-auth-doesnotexist", "sess-1", "dev-A")
    assert not ok and reason == "unknown_authorization"


def test_invalidated_authorization_rejected():
    rec = ca.create_authorization("sess-1", "dev-A")
    assert ca.invalidate(rec["authorization_id"]) is True
    ok, reason = ca.validate(rec["authorization_id"], "sess-1", "dev-A")
    assert not ok and reason == "authorization_invalidated"


def test_session_mismatch_rejected():
    rec = ca.create_authorization("sess-1", "dev-A")
    ok, reason = ca.validate(rec["authorization_id"], "sess-OTHER", "dev-A")
    assert not ok and reason == "session_mismatch"


def test_device_mismatch_rejected_when_both_known():
    rec = ca.create_authorization("sess-1", "dev-A")
    ok, reason = ca.validate(rec["authorization_id"], "sess-1", "dev-B")
    assert not ok and reason == "device_mismatch"


def test_device_lenient_when_one_side_unknown():
    # Authorization created without a device id; later request also lacks one.
    rec = ca.create_authorization("sess-1", None)
    ok, reason = ca.validate(rec["authorization_id"], "sess-1", "dev-A")
    assert ok and reason == "ok"


def test_invalidate_session_kills_all():
    a = ca.create_authorization("sess-1", "dev-A")
    b = ca.create_authorization("sess-1", "dev-B")
    assert ca.invalidate_session("sess-1") == 2
    assert ca.validate(a["authorization_id"], "sess-1", "dev-A")[0] is False
    assert ca.validate(b["authorization_id"], "sess-1", "dev-B")[0] is False
