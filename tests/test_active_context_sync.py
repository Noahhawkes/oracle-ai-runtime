import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _patch_paths(monkeypatch, tmp_path):
    import active_context_sync as ctx

    monkeypatch.setattr(ctx, "RUNTIME_ROOT", ROOT)
    monkeypatch.setattr(ctx, "STATE_ROOT", tmp_path)
    monkeypatch.setattr(ctx, "CONTEXT_DIR", tmp_path / "context")
    monkeypatch.setattr(ctx, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(ctx, "SOURCES_LATEST", tmp_path / "sources" / "oracle_source_manifest_latest.json")
    monkeypatch.setattr(ctx, "GAME_CAPTURES_DIR", tmp_path / "game" / "captures")
    monkeypatch.setattr(ctx, "MINDCOIN_LEDGER", tmp_path / "ledger" / "mindcoin_ledger.jsonl")
    monkeypatch.setattr(ctx, "COMPANION_DIR", tmp_path / "companion")
    monkeypatch.setattr(ctx, "GOVERNANCE_DIR", tmp_path / "governance")
    monkeypatch.setattr(ctx, "ROUTING_DIR", tmp_path / "routing")
    monkeypatch.setattr(ctx, "LOOTDROP_DIR", tmp_path / "artifacts" / "lootdrops")
    monkeypatch.setattr(ctx, "LATEST_CONTEXT", tmp_path / "context" / "active_context_latest.json")
    return ctx


def test_missing_files_are_handled_gracefully(monkeypatch, tmp_path):
    ctx = _patch_paths(monkeypatch, tmp_path)

    snapshot = ctx.build_snapshot()

    assert snapshot["conversation_reset"] is False
    assert snapshot["source_manifest_id"] is None
    assert any("source manifest missing" in item for item in snapshot["unknowns"])


def test_refresh_writes_snapshot_latest_and_receipt(monkeypatch, tmp_path):
    ctx = _patch_paths(monkeypatch, tmp_path)
    ctx.SOURCES_LATEST.parent.mkdir(parents=True)
    ctx.SOURCES_LATEST.write_text(
        json.dumps(
            {
                "manifest_id": "manifest-test",
                "source_count": 2,
                "sources": [
                    {
                        "source_id": "runtime",
                        "full_path": r"C:\Oracle\ORACLE.AI-runtime",
                        "canonical_status": "ratified_runtime",
                        "evidence_state": "METADATA_READ",
                    },
                    {
                        "source_id": "drive",
                        "full_path": r"G:\My Drive\HawkesNest LLC\ORACLE.AI",
                        "canonical_status": "mirror",
                        "evidence_state": "DISCOVERED",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    ctx.RECEIPTS_DIR.mkdir(parents=True)
    (ctx.RECEIPTS_DIR / "boot_receipt_test.json").write_text(
        json.dumps({"receipt_id": "receipt-1", "operation": "boot", "timestamp": "2026-06-19T00:00:00Z"}),
        encoding="utf-8",
    )

    result = ctx.refresh_active_context(notes="test refresh")
    snapshot_path = Path(result["snapshot_path"])
    latest_path = Path(result["latest_context_path"])
    receipt_path = Path(result["receipt"]["receipt_path"])

    assert snapshot_path.exists()
    assert latest_path.exists()
    assert receipt_path.exists()
    assert result["conversation_reset"] is False
    assert result["snapshot"]["source_manifest_id"] == "manifest-test"
    assert result["snapshot"]["drive_linked_sources"][0]["canonical_allowed"] is False
    assert "G:\\My Drive" in result["snapshot"]["drive_linked_sources"][0]["full_path"]


def test_context_diff_detects_new_items(monkeypatch, tmp_path):
    ctx = _patch_paths(monkeypatch, tmp_path)
    previous = {
        "snapshot_id": "old",
        "sources": [{"source_id": "a", "full_path": "a", "canonical_status": "linked_source"}],
        "latest_receipts": [],
        "latest_game_captures": [],
        "latest_lootdrops": [],
        "pending_tasks": [],
        "governance_state": {},
    }
    current = {
        "snapshot_id": "new",
        "sources": [
            {"source_id": "a", "full_path": "a", "canonical_status": "linked_source"},
            {"source_id": "b", "full_path": "b", "canonical_status": "linked_source"},
        ],
        "latest_receipts": [{"receipt_id": "r1", "path": "r1.json"}],
        "latest_game_captures": [{"path": "capture.png"}],
        "latest_lootdrops": [{"lootdrop_id": "l1", "path": "loot.json"}],
        "pending_tasks": [{"task_id": "t1", "path": "task.json"}],
        "governance_state": {"current_watch_state": "metadata_only"},
        "active_warnings": ["warn"],
        "unknowns": ["unknown"],
    }

    diff = ctx.build_diff(previous, current)

    assert len(diff["new_sources"]) == 1
    assert len(diff["new_receipts"]) == 1
    assert len(diff["new_game_captures"]) == 1
    assert len(diff["new_lootdrops"]) == 1
    assert len(diff["new_pending_tasks"]) == 1
    assert len(diff["new_governance_changes"]) == 1
    assert diff["new_items_detected"] == 6
    assert diff["conversation_reset"] is False


def test_receipt_has_zero_action_counts(monkeypatch, tmp_path):
    ctx = _patch_paths(monkeypatch, tmp_path)
    snapshot = ctx.build_snapshot()
    diff = ctx.build_diff(None, snapshot)
    receipt = ctx.write_sync_receipt(snapshot, diff, notes="receipt test")
    saved = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))

    assert saved["operation"] == "active_context_sync"
    assert saved["conversation_reset"] is False
    assert saved["files_moved"] == 0
    assert saved["files_deleted"] == 0
    assert saved["files_renamed"] == 0
    assert saved["files_synced"] == 0
    assert saved["cloud_uploads"] == 0
    assert saved["cloud_api_calls"] == 0
    assert saved["git_commits"] == 0
    assert saved["git_pushes"] == 0
    assert saved["recordings_created"] == 0
