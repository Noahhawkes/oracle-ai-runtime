import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _patch_paths(monkeypatch, tmp_path):
    import file_intake as fi

    monkeypatch.setattr(fi, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(fi, "UPLOADS_DIR", tmp_path / "inbox" / "uploads")
    monkeypatch.setattr(fi, "FOLDER_UPLOADS_DIR", tmp_path / "inbox" / "folder_uploads")
    monkeypatch.setattr(fi, "MANIFESTS_DIR", tmp_path / "inbox" / "manifests")
    monkeypatch.setattr(fi, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(fi, "SOURCES_DIR", tmp_path / "sources")
    return fi


def _file(fi, name, data=b"hello", rel=None):
    return fi.FileInput(filename=name, data=data, relative_path=rel)


def test_single_file_upload(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "notes.txt", b"hello world")])

    assert result["ok"] is True
    entries = result["manifest"]["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["original_filename"] == "notes.txt"
    assert entry["status"] == "received"
    assert entry["size_bytes"] == 11
    assert entry["extension"] == ".txt"
    assert entry["sha256"]
    assert entry["source_surface"] == "local_ui_upload"
    assert entry["source_authority"] == "Noah.Physical"
    stored = Path(entry["stored_path"])
    assert stored.exists()
    assert stored.read_bytes() == b"hello world"


def test_multiple_file_upload(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([
        _file(fi, "a.txt", b"a"),
        _file(fi, "b.md", b"bb"),
        _file(fi, "c.json", b"ccc"),
    ])

    assert result["manifest"]["counts"]["total_files"] == 3
    assert result["manifest"]["counts"]["received"] == 3
    assert result["manifest"]["total_bytes"] == 6
    for entry in result["manifest"]["entries"]:
        assert Path(entry["stored_path"]).exists()


def test_folder_upload_preserves_relative_paths(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake(
        [
            _file(fi, "root.txt", b"r", rel="project/root.txt"),
            _file(fi, "deep.txt", b"d", rel="project/sub/deep.txt"),
        ],
        is_folder=True,
    )

    entries = {e["original_filename"]: e for e in result["manifest"]["entries"]}
    assert entries["root.txt"]["relative_path"] == "project/root.txt"
    assert entries["deep.txt"]["relative_path"] == "project/sub/deep.txt"
    assert result["manifest"]["counts"]["folders"] == 1
    deep = Path(entries["deep.txt"]["stored_path"])
    assert deep.exists()
    assert deep.parts[-3:] == ("project", "sub", "deep.txt")


def test_manifest_creation(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "x.txt")])

    manifest_path = Path(result["manifest_path"])
    latest_path = Path(result["latest_path"])
    assert manifest_path.exists()
    assert latest_path.exists()
    saved = json.loads(latest_path.read_text(encoding="utf-8"))
    assert saved["manifest_kind"] == "oracle_local_intake"
    assert saved["source_authority"] == "Noah.Physical"
    assert saved["intake_batch_id"]


def test_receipt_creation(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "x.txt")])

    receipt_path = Path(result["receipt_path"])
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["action"] == "local_file_intake"
    assert receipt["files_received_count"] == 1
    assert receipt["manifest_path"] == result["manifest_path"]


def test_dangerous_extension_quarantine(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "malware.exe", b"MZ...")])

    entry = result["manifest"]["entries"][0]
    assert entry["status"] == "quarantined"
    assert "dangerous_extension" in entry["risk_flags"]
    # Dangerous file content must never be written to disk.
    assert entry["stored_path"] is None
    assert result["manifest"]["counts"]["quarantined"] == 1
    assert result["manifest"]["counts"]["received"] == 0


def test_credential_risk_filename_detection(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([
        _file(fi, ".env", b"SECRET=should-never-be-read"),
        _file(fi, "Alive \U0001f5dd.txt", b"token=should-never-be-read"),
        _file(fi, "my_password_list.csv", b"pw"),
    ])

    for entry in result["manifest"]["entries"]:
        assert "credential_risk" in entry["risk_flags"]
        assert entry["status"] == "quarantined"
        assert entry["stored_path"] is None  # contents never stored
    assert result["manifest"]["credential_risk_detected"] is True
    assert result["receipt"]["credential_risk_message"] == (
        "credential-risk file detected, rotation/quarantine required"
    )
    # The secret value must not appear anywhere in the manifest/receipt.
    blob = json.dumps(result)
    assert "should-never-be-read" not in blob
    assert "SECRET=" not in blob


def test_conversation_reset_remains_false(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "x.txt")])

    assert result["manifest"]["conversation_reset"] is False
    assert result["receipt"]["conversation_reset"] is False


def test_cloud_upload_remains_false(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "x.txt")])

    assert result["manifest"]["cloud_upload"] is False
    assert result["receipt"]["cloud_upload"] is False


def test_drive_untouched(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "x.txt")])

    assert result["manifest"]["drive_modified"] is False
    assert result["receipt"]["drive_modified"] is False
    # Everything written stays inside the patched (tmp) state root.
    assert str(tmp_path) in result["manifest_path"]
    assert str(tmp_path) in result["receipt_path"]


def test_git_untouched(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "x.txt")])

    for record in (result["manifest"], result["receipt"]):
        assert record["git_commit"] is False
        assert record["git_push"] is False
        assert record["deleted_files"] is False
        assert record["moved_existing_files"] is False
        assert record["renamed_existing_files"] is False


def test_path_traversal_is_quarantined(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake(
        [_file(fi, "evil.txt", b"x", rel="../../escape/evil.txt")],
        is_folder=True,
    )

    entry = result["manifest"]["entries"][0]
    assert "path_traversal" in entry["risk_flags"]
    assert entry["status"] == "quarantined"
    assert entry["stored_path"] is None


def test_oversize_file_rejected(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(fi, "MAX_INDIVIDUAL_BYTES", 4)

    result = fi.run_intake([_file(fi, "big.txt", b"toolong")])

    entry = result["manifest"]["entries"][0]
    assert entry["status"] == "rejected"
    assert "oversize_file" in entry["risk_flags"]
    assert entry["stored_path"] is None


def test_batch_count_limit_rejects_whole_batch(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(fi, "MAX_FILE_COUNT", 2)

    result = fi.run_intake([_file(fi, "a.txt"), _file(fi, "b.txt"), _file(fi, "c.txt")])

    assert result["ok"] is False
    assert result["manifest"]["batch_rejected"] is True
    assert "exceeds max" in result["manifest"]["batch_reject_reason"]
    # Nothing stored on a rejected batch, but a receipt still exists.
    assert all(e["stored_path"] is None for e in result["manifest"]["entries"])
    assert Path(result["receipt_path"]).exists()


def test_promotion_requires_approval_and_skips_quarantined(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([
        _file(fi, "good.txt", b"ok"),
        _file(fi, "secret_token.txt", b"x"),
    ])
    entries = {e["original_filename"]: e for e in result["manifest"]["entries"]}

    # A clean file can be promoted; promotion does not load content into memory.
    ok = fi.promote_intake(entries["good.txt"]["intake_id"])
    assert ok["ok"] is True
    assert ok["status"] == "promoted"
    assert ok["content_loaded_into_memory"] is False

    # A credential-risk (quarantined) file is refused without explicit override.
    refused = fi.promote_intake(entries["secret_token.txt"]["intake_id"])
    assert refused["ok"] is False
    assert "override" in refused["error"]

    review = fi.review_intake()
    assert review["promotion_requires_approval"] is True
    assert review["by_status"]["promoted"] == 1


def test_quarantine_intake_updates_status(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "doc.txt", b"x")])
    intake_id = result["manifest"]["entries"][0]["intake_id"]

    out = fi.quarantine_intake(intake_id)
    assert out["ok"] is True
    assert out["status"] == "quarantined"
    review = fi.review_intake()
    assert review["by_status"].get("quarantined") == 1


def test_oracle_response_line_matches_doctrine(monkeypatch, tmp_path):
    fi = _patch_paths(monkeypatch, tmp_path)

    result = fi.run_intake([_file(fi, "a.txt"), _file(fi, "b.txt")])
    line = result["oracle_response"]

    assert "Local intake complete" in line
    assert "I did not upload, sync, commit, push, delete, move, rename" in line
    assert "Review intake before promotion?" in line


def test_intake_ui_panel_present():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "ORACLE Intake" in html
    assert "Add Files" in html
    assert "Add Folder" in html
    assert "Review Intake" in html
    assert "Clear Intake View" in html
    assert "Show Intake Manifest" in html
    assert "/api/intake/files" in html
    assert "/api/intake/folder" in html
