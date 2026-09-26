import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _patch_paths(monkeypatch, tmp_path):
    import sourcemap_witness_governance as gov

    monkeypatch.setattr(gov, "GOVERNANCE_DIR", tmp_path / "governance")
    monkeypatch.setattr(gov, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(gov, "SOURCES_LATEST", tmp_path / "sources" / "oracle_source_manifest_latest.json")
    monkeypatch.setattr(gov, "COMPANION_PROFILE", tmp_path / "companion" / "companion_profile.json")
    monkeypatch.setattr(gov, "GOVERNANCE_PATH", tmp_path / "governance" / "sourcemap_witness_governance.json")
    monkeypatch.setattr(
        gov,
        "_set_watch_off",
        lambda data: data.update({"current_watch_state": "watch_off", "current_storage_tier": "do_not_store"}),
    )
    return gov


def test_default_watch_state_is_off(monkeypatch, tmp_path):
    gov = _patch_paths(monkeypatch, tmp_path)

    status = gov.status_payload()

    assert status["current_watch_state"] == "watch_off"
    assert status["current_storage_tier"] == "do_not_store"
    assert status["governance"]["default_watch_state"] == "watch_off"
    assert status["governance_path"].endswith("sourcemap_witness_governance.json")


def test_metadata_only_requires_explicit_selection(monkeypatch, tmp_path):
    gov = _patch_paths(monkeypatch, tmp_path)

    before = gov.load_governance()
    result = gov.handle_command("metadata_only", why_it_mattered="explicit test")

    assert before["current_watch_state"] == "watch_off"
    assert result["governance"]["current_watch_state"] == "metadata_only"
    assert result["governance"]["current_storage_tier"] == "link_only"
    assert result["receipt"]["operation"] == "metadata_only_enabled"
    assert Path(result["receipt"]["receipt_path"]).exists()


def test_preserve_this_writes_receipt_proposal_without_raw_storage(monkeypatch, tmp_path):
    gov = _patch_paths(monkeypatch, tmp_path)

    result = gov.handle_command(
        "preserve_this",
        source_reference="special OBS session",
        linked_path=r"C:\Users\noahh\OneDrive\Videos\session.mkv",
        why_it_mattered="continuity artifact",
    )
    receipt = result["receipt"]

    assert result["action_taken"] == "receipt_proposal_before_storage"
    assert receipt["operation"] == "preserve_this_proposal"
    assert receipt["storage_tier"] == "receipt_only"
    assert "raw source was not stored" in receipt["what_was_stored"]
    assert receipt["what_was_copied"] == "Nothing."
    assert receipt["files_moved"] == 0
    assert receipt["files_deleted"] == 0
    assert receipt["files_renamed"] == 0
    assert receipt["files_synced"] == 0
    assert receipt["cloud_uploads"] == 0
    assert receipt["git_commits"] == 0
    assert receipt["git_pushes"] == 0
    assert "store_raw_source_with_approval" in receipt["approval_required_for_next_step"]


def test_forget_this_marks_forget_requested_without_deleting(monkeypatch, tmp_path):
    gov = _patch_paths(monkeypatch, tmp_path)

    result = gov.handle_command(
        "forget_this",
        source_reference="private source",
        why_it_mattered="operator requested forget",
    )
    receipt = result["receipt"]

    assert result["action_taken"] == "marked_forget_requested_no_delete"
    assert result["governance"]["current_watch_state"] == "forget_requested"
    assert receipt["evidence_state"] == "FORGET_REQUESTED"
    assert receipt["storage_tier"] == "do_not_store"
    assert receipt["files_deleted"] == 0
    assert "human_review_required" in receipt["approval_required_for_next_step"]


def test_show_me_what_you_know_lists_references_without_inventing_content(monkeypatch, tmp_path):
    gov = _patch_paths(monkeypatch, tmp_path)
    gov.SOURCES_LATEST.parent.mkdir(parents=True, exist_ok=True)
    gov.SOURCES_LATEST.write_text(json.dumps({"source_count": 3, "sources": []}), encoding="utf-8")

    known = gov.show_me_what_you_know()

    assert known["governance_loaded"] is True
    assert known["source_manifest_source_count"] == 3
    assert "metadata only" in known["uncertainty"]
    assert "not treated as understood content" in known["uncertainty"]


def test_receipt_schema_zero_action_counts(monkeypatch, tmp_path):
    gov = _patch_paths(monkeypatch, tmp_path)

    receipt = gov.write_receipt(
        operation="schema_test",
        governance_state="receipt_only",
        storage_tier="receipt_only",
        evidence_state="DISCOVERED",
    )

    assert Path(receipt["receipt_path"]).exists()
    assert receipt["files_moved"] == 0
    assert receipt["files_deleted"] == 0
    assert receipt["files_renamed"] == 0
    assert receipt["files_synced"] == 0
    assert receipt["cloud_uploads"] == 0
    assert receipt["git_commits"] == 0
    assert receipt["git_pushes"] == 0


def test_sourcemap_ui_contains_witness_governance_panel():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "SourceMap Witness Governance" in html
    assert "gov-watch-state" in html
    assert "Do not watch" in html
    assert "Metadata only" in html
    assert "Preserve this" in html
    assert "Forget this" in html
    assert "Show me what you know" in html
