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

import ai_lockbox  # noqa: E402
import capability_broker  # noqa: E402
import file_recall  # noqa: E402
import oracle_server as srv  # noqa: E402


class _Capability:
    def __init__(self, component: str, status: str, blocker: str = "") -> None:
        self.component = component
        self.current_status = status
        self.blocker = blocker


def test_diagnostic_status_answers_capability_writer_and_recall_fields(monkeypatch):
    monkeypatch.setattr(
        capability_broker,
        "discover_capabilities",
        lambda **_: [
            _Capability("ORACLE web UI", "verified"),
            _Capability("OBS integration", "degraded", "socket refused"),
            _Capability("GitHub access", "blocked", "gh missing"),
        ],
    )
    monkeypatch.setattr(
        ai_lockbox,
        "status_payload",
        lambda: {
            "capsule_count": 145,
            "receipt_count": 12,
            "manifest_path": r"C:\Oracle\ORACLE.AI-runtime\Memory\ai_lockbox\manifest.jsonl",
        },
    )
    monkeypatch.setattr(
        srv,
        "_self_prompt_status_payload",
        lambda: {
            "current_state": "SANDBOX_AUTONOMOUS_ENABLED",
            "approved": True,
            "loop_enabled": True,
            "journal_path": r"C:\Oracle\ORACLE.AI-runtime\sandbox\workbench\oracle_self_prompt_journal.ai",
            "last_receipt_path": r"C:\Oracle\ORACLE.AI-runtime\sandbox\receipts\latest.json",
            "novelty_status": "near_duplicate_suppressed",
            "journal_entry_count": 15,
        },
    )

    text = srv._diagnostic_status_response(
        {"detected_lane": "talk_lane", "action_type": "read_only_status"},
        "Report current mode, visible Writer state, Recall count, capability broker totals, blocked capabilities, and degraded capabilities.",
    )

    assert "capability_broker_totals: verified=1 degraded=1 blocked=1 total=3" in text
    assert "blocked_capabilities: GitHub access" in text
    assert "degraded_capabilities: OBS integration" in text
    assert "ai_lockbox_capsule_count: 145" in text
    assert "writer_state: SANDBOX_AUTONOMOUS_ENABLED" in text
    assert "latest_self_prompt_novelty_status: near_duplicate_suppressed" in text
    assert "files_mutated: 0" in text


def test_diagnostic_status_answers_exact_read_only_roots(monkeypatch):
    monkeypatch.setattr(
        file_recall,
        "self_check",
        lambda: {"allowed_roots": [r"C:\Oracle\ORACLE.AI-runtime", r"G:\My Drive"]},
    )

    text = srv._diagnostic_status_response(
        {"detected_lane": "talk_lane", "action_type": "read_only_status"},
        "ROUND 003 / EXACT READ-ONLY FILE ROOTS. Report exact read-only file roots.",
    )

    assert "read_only_root_1: C:\\Oracle\\ORACLE.AI-runtime" in text
    assert "read_only_root_2: G:\\My Drive" in text
    assert "external_action: false" in text


def test_diagnostic_status_answers_sandbox_journal_without_writing(monkeypatch):
    monkeypatch.setattr(
        srv,
        "_self_prompt_status_payload",
        lambda: {
            "current_state": "SANDBOX_AUTONOMOUS_ENABLED",
            "approved": True,
            "loop_enabled": True,
            "journal_path": r"C:\Oracle\ORACLE.AI-runtime\sandbox\workbench\oracle_self_prompt_journal.ai",
            "last_receipt_path": r"C:\Oracle\ORACLE.AI-runtime\sandbox\receipts\latest.json",
            "novelty_status": "new",
            "journal_entry_count": 16,
        },
    )

    text = srv._diagnostic_status_response(
        {"detected_lane": "talk_lane", "action_type": "read_only_status"},
        "Report the current sandbox self-prompt journal path, whether Writer is enabled, whether sandbox candidate writes are allowed, and latest receipt.",
    )

    assert "writer_enabled: True" in text
    assert "sandbox_candidate_writes_allowed: True" in text
    assert "sandbox_self_prompt_journal_path: C:\\Oracle\\ORACLE.AI-runtime\\sandbox\\workbench\\oracle_self_prompt_journal.ai" in text
    assert "latest_self_prompt_receipt: C:\\Oracle\\ORACLE.AI-runtime\\sandbox\\receipts\\latest.json" in text
    assert "files_mutated: 0" in text
