import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _patch(monkeypatch, tmp_path):
    import storage_census as sc

    approved = tmp_path / "approved"
    unapproved = tmp_path / "unapproved_mirror"
    onedrive = tmp_path / "onedrive"
    for d in (approved, unapproved, onedrive):
        d.mkdir(parents=True, exist_ok=True)

    # Approved-root content.
    (approved / "oracle_notes.txt").write_text("hello", encoding="utf-8")
    (approved / "random.txt").write_text("nothing special", encoding="utf-8")
    (approved / "oracle_key.txt").write_text("should-never-be-read", encoding="utf-8")
    (approved / ".env").write_text("SECRET=should-never-be-read", encoding="utf-8")
    nm = approved / "node_modules"
    nm.mkdir()
    (nm / "oracle_excluded.txt").write_text("excluded", encoding="utf-8")

    # Roots that must NOT be scanned without approval.
    (unapproved / "oracle_mirror_doc.txt").write_text("mirror", encoding="utf-8")
    (onedrive / "oracle_onedrive_doc.txt").write_text("cloud", encoding="utf-8")

    monkeypatch.setattr(sc, "DEFAULT_APPROVED_ROOT", approved)
    monkeypatch.setattr(sc, "KNOWN_CANDIDATE_ROOTS", [unapproved])
    monkeypatch.setattr(sc, "detect_onedrive_roots", lambda: [onedrive])
    monkeypatch.setattr(sc, "STORAGE_DIR", tmp_path / "state" / "storage")
    monkeypatch.setattr(sc, "SOURCES_DIR", tmp_path / "state" / "sources")
    monkeypatch.setattr(sc, "RECEIPTS_DIR", tmp_path / "state" / "receipts")
    monkeypatch.setattr(sc, "ROOTS_STATE_FILE", tmp_path / "state" / "storage" / "roots.json")
    # pytest's tmp_path lives under C:\Users\noahh\AppData (an excluded prefix in
    # production). Neutralize the absolute-prefix exclusion for the sandbox so the
    # temp roots can be scanned; EXCLUDED_DIR_NAMES (node_modules, etc.) still applies.
    monkeypatch.setattr(sc, "EXCLUDED_ABS_PREFIXES", [])
    return sc, {"approved": approved, "unapproved": unapproved, "onedrive": onedrive}


def test_default_excluded_prefixes_block_system_folders():
    import storage_census as sc

    assert sc._is_excluded_dir(r"C:\Windows\System32") is True
    assert sc._is_excluded_dir(r"C:\Users\noahh\AppData\Local\Temp") is True
    assert sc._is_excluded_dir(r"C:\Oracle\state") is False


def test_governance_module_is_loaded(monkeypatch, tmp_path):
    sc, _ = _patch(monkeypatch, tmp_path)

    gov = sc.load_governance()

    assert gov is not None
    assert "governance.py" in gov["source"]
    assert gov["approval_required"] is True  # existing governance default
    assert "noah_sovereignty_pct" in gov


def test_fails_closed_when_governance_unavailable(monkeypatch, tmp_path):
    sc, _ = _patch(monkeypatch, tmp_path)
    monkeypatch.setattr(sc, "load_governance", lambda: None)

    census = sc.run_census()
    roots = sc.roots_payload()

    assert census["blocked"] is True
    assert census["message"] == "Storage Census blocked: governance state unavailable."
    assert roots["blocked"] is True
    assert census["governance_loaded"] is False


def test_only_approved_roots_scanned(monkeypatch, tmp_path):
    sc, roots = _patch(monkeypatch, tmp_path)

    res = sc.run_census()
    manifest = json.loads(Path(res["latest_path"]).read_text(encoding="utf-8"))
    paths = [e["path"] for e in manifest["entries"]]

    assert any("oracle_notes.txt" in p for p in paths)
    assert any("random.txt" in p for p in paths)
    # Unapproved + OneDrive roots are never scanned.
    assert not any("unapproved_mirror" in p for p in paths)
    assert not any("oracle_onedrive_doc" in p for p in paths)
    # Excluded directory pruned.
    assert not any("node_modules" in p for p in paths)
    assert res["approved_roots_scanned"] == [str(roots["approved"])]


def test_onedrive_detected_but_not_scanned(monkeypatch, tmp_path):
    sc, roots = _patch(monkeypatch, tmp_path)

    payload = sc.roots_payload()
    not_scanned_paths = [r["path"] for r in payload["known_roots_not_scanned"]]

    assert str(roots["onedrive"]) in payload["onedrive_roots_detected"]
    assert str(roots["onedrive"]) in not_scanned_paths
    assert str(roots["onedrive"]) not in payload["approved_roots"]


def test_drive_mirror_detected_but_not_scanned(monkeypatch, tmp_path):
    sc, roots = _patch(monkeypatch, tmp_path)

    payload = sc.roots_payload()
    not_scanned_paths = [r["path"] for r in payload["known_roots_not_scanned"]]

    assert str(roots["unapproved"]) in not_scanned_paths
    assert str(roots["unapproved"]) not in payload["approved_roots"]


def test_approve_root_then_scanned(monkeypatch, tmp_path):
    sc, roots = _patch(monkeypatch, tmp_path)

    approve = sc.approve_root(str(roots["onedrive"]))
    assert approve["ok"] is True
    res = sc.run_census()
    paths = [e["path"] for e in json.loads(Path(res["latest_path"]).read_text(encoding="utf-8"))["entries"]]
    assert any("oracle_onedrive_doc" in p for p in paths)


def test_oracle_related_classification(monkeypatch, tmp_path):
    sc, _ = _patch(monkeypatch, tmp_path)

    assert sc.is_oracle_related("oracle_notes.txt", "C:/x/oracle_notes.txt") is True
    assert sc.is_oracle_related("MindCoin_ledger.jsonl", "x") is True
    assert sc.is_oracle_related("vacation.jpg", "C:/photos/vacation.jpg") is False
    assert sc.classify("mindcoin_ledger.jsonl", "x", ".jsonl") == "mindcoin_ledger"
    assert sc.classify("source_map.json", "x", ".json") == "sourcemap_manifest"


def test_credential_risk_detection(monkeypatch, tmp_path):
    sc, _ = _patch(monkeypatch, tmp_path)

    res = sc.run_census()
    manifest = json.loads(Path(res["latest_path"]).read_text(encoding="utf-8"))
    cred = [e for e in manifest["entries"] if "credential_risk" in e["risk_flags"]]

    assert manifest["counts"]["credential_risk"] >= 2  # .env and oracle_key.txt
    for e in cred:
        assert e["sha256"] is None  # credential contents never read/hashed
    # Secret value must never appear anywhere in census artifacts.
    blob = json.dumps(manifest)
    assert "should-never-be-read" not in blob
    assert "SECRET=" not in blob


def test_manifest_creation(monkeypatch, tmp_path):
    sc, _ = _patch(monkeypatch, tmp_path)

    res = sc.run_census()
    assert Path(res["manifest_path"]).exists()
    assert Path(res["latest_path"]).exists()
    assert Path(res["report_path"]).exists()
    manifest = json.loads(Path(res["latest_path"]).read_text(encoding="utf-8"))
    assert manifest["census_kind"] == "oracle_storage_census"
    assert manifest["governance_loaded"] is True


def test_receipt_creation(monkeypatch, tmp_path):
    sc, _ = _patch(monkeypatch, tmp_path)

    res = sc.run_census()
    receipt = json.loads(Path(res["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["action"] == "storage_census"
    assert receipt["governance_loaded"] is True
    assert receipt["governance_source"].endswith("governance.py")
    assert receipt["files_seen_count"] >= 3


def test_sourcemap_candidate_creation(monkeypatch, tmp_path):
    sc, _ = _patch(monkeypatch, tmp_path)

    res = sc.run_census()
    candidates = json.loads(Path(res["candidates_latest_path"]).read_text(encoding="utf-8"))

    assert candidates["auto_merged_into_canonical_sourcemap"] is False
    assert candidates["status"] == "candidate_pending_noah_approval"
    names = [c["filename"] for c in candidates["candidates"]]
    assert "oracle_notes.txt" in names
    # Credential-risk files are never offered as candidates.
    assert "oracle_key.txt" not in names
    for c in candidates["candidates"]:
        assert c["status"] == "candidate_pending_noah_approval"


def test_no_mutation_flags_all_false(monkeypatch, tmp_path):
    sc, roots = _patch(monkeypatch, tmp_path)

    res = sc.run_census()
    manifest = json.loads(Path(res["latest_path"]).read_text(encoding="utf-8"))
    receipt = json.loads(Path(res["receipt_path"]).read_text(encoding="utf-8"))

    for record in (manifest, receipt):
        assert record["content_ingested"] is False
        assert record["cloud_upload"] is False
        assert record["drive_modified"] is False
        assert record["onedrive_modified"] is False
        assert record["git_commit"] is False
        assert record["git_push"] is False
        assert record["deleted_files"] is False
        assert record["moved_files"] is False
        assert record["renamed_files"] is False
        assert record["conversation_reset"] is False

    # Read-only: scanned files still exist untouched.
    assert (roots["approved"] / "oracle_notes.txt").exists()
    assert (roots["approved"] / ".env").exists()


def test_handle_command_fails_closed(monkeypatch, tmp_path):
    sc, _ = _patch(monkeypatch, tmp_path)
    monkeypatch.setattr(sc, "load_governance", lambda: None)

    assert sc.handle_command("roots") == "Storage Census blocked: governance state unavailable."


def test_storage_census_ui_panel_present():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "Storage Census" in html
    assert "/api/storage-census/roots" in html
    assert "/api/storage-census/scan-approved" in html
