import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _patch_paths(monkeypatch, tmp_path):
    import profile_capsule as capsule

    monkeypatch.setattr(capsule, "STATE_ROOT", tmp_path)
    monkeypatch.setattr(capsule, "CAPSULE_DIR", tmp_path / "profile_candidates")
    monkeypatch.setattr(capsule, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(
        capsule,
        "LATEST_PATH",
        tmp_path / "profile_candidates" / "substrate_independent_identity_governance_latest.json",
    )
    return capsule


def test_substrate_identity_governance_candidate_is_local_only(monkeypatch, tmp_path):
    capsule = _patch_paths(monkeypatch, tmp_path)

    result = capsule.ensure_substrate_identity_governance_candidate(notes="test")
    candidate = result["candidate"]
    receipt = result["receipt"]

    assert result["created"] is True
    assert Path(candidate["candidate_path"]).exists()
    assert Path(candidate["latest_path"]).exists()
    assert Path(receipt["receipt_path"]).exists()
    assert candidate["status"] == "candidate_only"
    assert candidate["durable_memory_promoted"] is False
    assert candidate["profile_injection_allowed"] is False
    assert candidate["source_boundary"]["drive_searched"] is False
    assert candidate["drive_files_opened"] == 0
    assert candidate["onedrive_files_opened"] == 0
    assert candidate["cloud_api_calls"] == 0
    assert candidate["git_commits"] == 0
    assert candidate["git_pushes"] == 0
    assert receipt["durable_memory_promotions"] == 0
    assert receipt["claim_boundary"]["simulation_proof_claimed"] is False
    assert receipt["claim_boundary"]["gravity_proof_claimed"] is False
    assert receipt["claim_boundary"]["consciousness_proof_claimed"] is False


def test_profile_capsule_blocks_overclaim_language(monkeypatch, tmp_path):
    capsule = _patch_paths(monkeypatch, tmp_path)

    candidate = capsule.ensure_substrate_identity_governance_candidate()["candidate"]

    blocked = set(candidate["blocked_runtime_claims"])
    assert "proof of simulation reality" in blocked
    assert "proof of gravity theory" in blocked
    assert "proof of machine consciousness" in blocked
    assert "completed physics discovery" in blocked
    assert "durable memory approval" in blocked


def test_profile_capsule_status_and_format(monkeypatch, tmp_path):
    capsule = _patch_paths(monkeypatch, tmp_path)

    before = capsule.status_payload(create=False)
    after = capsule.status_payload(create=True, notes="format test")
    text = capsule.format_profile_capsule(after["candidate"])

    assert before["available"] is False
    assert after["available"] is True
    assert after["governance"]["durable_memory_promoted"] is False
    assert "PROFILE CAPSULE" in text
    assert "candidate only" in text
    assert "no proof of simulation" in text

