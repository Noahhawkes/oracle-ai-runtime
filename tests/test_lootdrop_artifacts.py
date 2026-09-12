import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _patch_paths(monkeypatch, tmp_path):
    import lootdrop_artifacts as loot

    monkeypatch.setattr(loot, "ARTIFACTS_DIR", tmp_path / "artifacts" / "lootdrops")
    monkeypatch.setattr(loot, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(loot, "LEDGER_PATH", tmp_path / "ledger" / "mindcoin_ledger.jsonl")
    return loot


def test_status_loads_without_prior_lootdrops(monkeypatch, tmp_path):
    loot = _patch_paths(monkeypatch, tmp_path)

    status = loot.status_payload()

    assert status["latest_lootdrop"] is None
    assert status["mindcoin_total"] == 0
    assert status["ledger"]["event_count"] == 0
    assert "nonfinancial" in status["nonfinancial_notice"]


def test_lootdrop_json_writes_expected_schema(monkeypatch, tmp_path):
    loot = _patch_paths(monkeypatch, tmp_path)

    artifact = loot.write_lootdrop_artifact()
    path = Path(artifact["artifact_path"])
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert path.exists()
    assert saved["title"] == "Myrmidon\u2019s Signet of Thread Authority"
    assert saved["artifact_type"] == "game_drop"
    assert saved["evidence_state"] == "HUMAN_CONFIRMED"
    assert saved["human_authority"] == "Noah.Physical"
    assert saved["symbolic_stats"]["strength"] == 10
    assert saved["symbolic_stats"]["agility"] == 7
    assert saved["symbolic_stats"]["stamina"] == 17
    assert saved["symbolic_stats"]["requires_level"] == 53
    assert saved["mindcoin_award"]["points"] == 53
    assert saved["mindcoin_award"]["bonus_continuity_xp"] == 420
    assert saved["nonfinancial"] is True
    assert saved["nontransferable"] is True


def test_receipt_writes_zero_action_counts(monkeypatch, tmp_path):
    loot = _patch_paths(monkeypatch, tmp_path)

    artifact = loot.write_lootdrop_artifact()
    receipt = loot.write_lootdrop_receipt(artifact)
    saved = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))

    assert saved["lootdrop_id"] == artifact["lootdrop_id"]
    assert saved["files_moved"] == 0
    assert saved["files_deleted"] == 0
    assert saved["files_renamed"] == 0
    assert saved["files_synced"] == 0
    assert saved["files_uploaded"] == 0
    assert saved["git_commits"] == 0
    assert saved["git_pushes"] == 0


def test_mindcoin_ledger_appends_jsonl_event(monkeypatch, tmp_path):
    loot = _patch_paths(monkeypatch, tmp_path)

    artifact = loot.write_lootdrop_artifact()
    receipt = loot.write_lootdrop_receipt(artifact)
    event = loot.award_mindcoin_for_lootdrop(artifact, receipt)
    rows = [json.loads(line) for line in loot.LEDGER_PATH.read_text(encoding="utf-8").splitlines()]
    summary = loot.ledger_summary()

    assert event["points"] == 53
    assert event["bonus_continuity_xp"] == 420
    assert event["nonfinancial"] is True
    assert event["nontransferable"] is True
    assert len(rows) == 1
    assert summary["mindcoin_total"] == 53
    assert summary["bonus_continuity_xp_total"] == 420


def test_create_manual_lootdrop_writes_artifact_receipt_and_ledger(monkeypatch, tmp_path):
    loot = _patch_paths(monkeypatch, tmp_path)

    result = loot.create_manual_lootdrop()

    assert Path(result["artifact"]["artifact_path"]).exists()
    assert Path(result["receipt"]["receipt_path"]).exists()
    assert loot.LEDGER_PATH.exists()
    assert result["ledger"]["mindcoin_total"] == 53


def test_sourcemap_ui_contains_lootdrop_panel():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "LootDrops" in html
    assert "loot-latest" in html
    assert "Create manual LootDrop" in html
    assert "Write LootDrop receipt" in html
    assert "Award MindCoin" in html
    assert "nonfinancial, nontransferable" in html
