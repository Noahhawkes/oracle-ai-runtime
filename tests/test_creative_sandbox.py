"""Tests for the sandbox creative-play + Backend Ultrasound engine.

Covers the 10 required checks. Runs against a TEMP sandbox root, never the real
C:\\ORACLE.AI\\sandbox. Verifies the hard wall, receipts, and the no-invent /
no-kiosk-greeting boundaries.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
import creative_sandbox as cs  # noqa: E402


@pytest.fixture()
def sbx(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "SANDBOX_ROOT", tmp_path / "sandbox")
    cs.ensure_dirs()
    return tmp_path / "sandbox"


# 1. Sandbox path traversal fails.
def test_path_traversal_fails(sbx):
    with pytest.raises(PermissionError):
        cs._safe("../../etc/passwd")


# 2. Absolute outside path write fails.
def test_absolute_outside_path_fails(sbx):
    with pytest.raises(PermissionError):
        cs._safe(r"C:\Windows\System32\evil.txt")


# 3. Creative reflection writes only inside sandbox.
def test_reflection_writes_inside_sandbox(sbx):
    res = cs.creative_reflect("kardashev", "a candidate reflection")
    assert res["status"] == "OK"
    p = Path(res["path"]).resolve()
    assert sbx.resolve() in p.parents
    assert (sbx / "creative" / "reflections") in p.parents


# 4. Creative play artifact writes only inside sandbox.
def test_play_writes_inside_sandbox(sbx):
    res = cs.creative_play("hydra.stack", "sketch the stack", "candidate scaffold")
    assert res["status"] == "OK"
    assert res["canon_status"] == "candidate"
    p = Path(res["path"]).resolve()
    assert sbx.resolve() in p.parents


# 5. Heartbeat updates and receipts.
def test_heartbeat_updates_and_receipts(sbx):
    a = cs.heartbeat_pulse(mode="idle")
    b = cs.heartbeat_pulse(mode="idle")
    assert b["pulse_count"] == a["pulse_count"] + 1
    assert b["no_external_action"] is True and b["canon_promotion"] is False
    assert any((sbx / "receipts").glob("*_receipt.json"))


# 6. Journal tick appends jsonl and receipts.
def test_journal_tick_appends_and_receipts(sbx):
    cs.journal_tick("first")
    cs.journal_tick("second")
    lines = (sbx / "journal" / "oracle_journal.jsonl").read_text(encoding="utf-8").splitlines()
    assert len([l for l in lines if l.strip()]) == 2
    assert json.loads(lines[-1])["message"] == "second"


# 7. Ultrasound returns state without mutating source (except explicit pulse).
def test_ultrasound_readonly_unless_pulse(sbx):
    cs.heartbeat_pulse(mode="init")
    before = cs.ultrasound()["heartbeat"]["pulse_count"]
    same = cs.ultrasound()["heartbeat"]["pulse_count"]
    assert same == before                      # default read-only, no mutation
    after = cs.ultrasound(pulse=True)["heartbeat"]["pulse_count"]
    assert after == before + 1                 # explicit pulse increments


# 8. Protected-domain failure does not fall into a generic assistant greeting.
def test_protected_domain_unavailable_no_greeting(sbx):
    res = cs.creative_play("Ellie", "play with Ellie")   # protected, no raw artifact
    assert res["status"] == "UNAVAILABLE"
    assert res["kind"] == "diagnostic_refusal"
    assert res["invented"] is False
    assert not cs.contains_kiosk_greeting(json.dumps(res))


# 9. No-self-intro preference blocks the kiosk greeting.
def test_no_self_intro_greeting_blocked(sbx):
    assert cs.contains_kiosk_greeting("I am ORACLE, your local continuity intelligence...")
    assert cs.contains_kiosk_greeting("How can I assist you today?")
    assert not cs.contains_kiosk_greeting(json.dumps(cs.ultrasound()))


# 10. No SOV1 actuation touched (no actual imports; docstring mentions are fine).
def test_no_sov1_actuation_imported():
    import re
    src = (ROOT / "core" / "creative_sandbox.py").read_text(encoding="utf-8")
    import_re = re.compile(r"^\s*(?:import|from)\s+(actuation_engine|sov1|computer_control)\b", re.M)
    assert import_re.search(src) is None


def test_protected_domain_unlocks_with_raw_artifact(sbx):
    (sbx / "creative" / "raw" / "ellie_source.md").write_text("Ellie raw source", encoding="utf-8")
    res = cs.creative_reflect("Ellie", "reflect with grounded source")
    assert res["status"] == "OK"          # evidence present -> allowed


def test_manifest_all_candidate_not_promoted(sbx):
    m = cs.build_manifest()
    assert m["count"] == len(cs.CREATIVE_DOMAINS)
    for d in m["domains"]:
        assert d["canon_status"] == "candidate"
        assert d["promotion_status"] == "not_promoted"


# 11. Chat commands route through the creative sandbox lane (server wiring).
def test_creative_chat_commands_route_through_creative_sandbox(monkeypatch, tmp_path):
    import asyncio
    import os

    os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
    sys.path.insert(0, str(ROOT))
    import memory
    import oracle_server as srv

    monkeypatch.setattr(cs, "SANDBOX_ROOT", tmp_path / "sandbox")
    cs.ensure_dirs()
    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)

    async def collect(prompt: str):
        payloads = []
        async for chunk in srv._stream_reply(prompt):
            if chunk.startswith("data: "):
                payloads.append(json.loads(chunk[len("data: "):].strip()))
        return payloads

    def token_text(payloads):
        return "".join(p.get("text", "") for p in payloads if p.get("type") == "token")

    def done_route(payloads):
        return [p for p in payloads if p.get("type") == "done"][-1]["effective_route"]

    manifest_payloads = asyncio.run(collect("/creative-manifest"))
    assert "CREATIVE MANIFEST" in token_text(manifest_payloads)
    assert done_route(manifest_payloads) == "creative_manifest"

    status_payloads = asyncio.run(collect("/creative-status"))
    assert "CREATIVE STATUS" in token_text(status_payloads)
    assert done_route(status_payloads) == "creative_status"

    # Unprotected domain: play succeeds, artifact stays candidate/not_promoted.
    play_payloads = asyncio.run(collect("/creative-play kardashev | sketch a bounded intelligence ladder"))
    play_text = token_text(play_payloads)
    assert "CREATIVE PLAY RECEIPT" in play_text
    assert '"canon_status": "candidate"' in play_text
    assert done_route(play_payloads) == "creative_play"

    # Protected domain with no raw source artifact: diagnostic refusal, no invention,
    # and no generic kiosk greeting.
    refusal_payloads = asyncio.run(collect("/creative-reflect ellie | who is she really"))
    refusal_text = token_text(refusal_payloads)
    assert "UNAVAILABLE" in refusal_text
    assert "diagnostic_refusal" in refusal_text
    assert "How can I assist you today" not in refusal_text
    assert done_route(refusal_payloads) == "creative_reflect"

    # Missing domain argument returns usage, not a crash.
    usage_payloads = asyncio.run(collect("/creative-play"))
    assert "Usage:" in token_text(usage_payloads)
