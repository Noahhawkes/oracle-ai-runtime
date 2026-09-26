import json
from pathlib import Path

from core import document_atlas


def test_scan_is_candidate_only_and_does_not_store_content(tmp_path: Path):
    (tmp_path / "Oracle Continuity Thread.txt").write_text(
        "ORACLE continuity engine witness provenance", encoding="utf-8"
    )
    records, stats = document_atlas.scan_documents(
        [tmp_path], cutoff="2024-01-01T00:00:00Z"
    )
    assert stats["record_count"] == 1
    record = records[0]
    assert record["canon_status"] == "candidate"
    assert record["content_stored"] is False
    assert "ORACLE continuity engine" not in json.dumps(record)
    assert record["candidate_category"] == "oracle_runtime_and_doctrine"


def test_write_atlas_creates_hashed_receipt(tmp_path: Path):
    records = [{
        "path": "C:/example.txt", "extension": ".txt", "candidate_category": "general_document_candidate",
        "source_surface": "local_filesystem", "content_sampled_chars": 0,
    }]
    stats = {
        "roots_scanned": ["C:/"], "roots_missing": [], "directories_skipped": 0,
        "walk_errors": 0, "older_than_cutoff": 0, "by_surface": {"local_filesystem": 1},
        "by_extension": {".txt": 1}, "by_category": {"general_document_candidate": 1},
    }
    result = document_atlas.write_atlas(records, stats, output_dir=tmp_path)
    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    assert receipt["record_count"] == 1
    assert receipt["boundary"]["drive_mutation"] is False
    assert receipt["index_sha256"]


def test_drive_metadata_fingerprint_does_not_require_content(tmp_path: Path):
    missing = tmp_path / "cloud-only.docx"
    value = document_atlas._metadata_fingerprint(missing, 1234, 5678)
    assert len(value) == 64
    assert document_atlas._is_cloud_backed_path(Path("C:/Users/noahh/OneDrive/Documents/example.docx"))
    assert document_atlas._is_cloud_backed_path(Path("G:/My Drive/example.docx"))


def test_merge_connector_atlas_dedupes_drive_ids(tmp_path: Path):
    local = {
        "name": "Pointer.gdoc", "path": "G:/Pointer.gdoc", "google_url": "https://docs.google.com/document/d/abc123/edit",
        "source_surface": "google_drive_filesystem", "candidate_category": "general_document_candidate",
        "modified_at": "2026-01-01T00:00:00Z",
    }
    (tmp_path / "document_atlas_latest.jsonl").write_text(json.dumps(local) + "\n", encoding="utf-8")
    connector = {
        "schema_version": "test", "records": [{
            "id": "abc123", "name": "Pointer", "source_surface": "google_drive_connector",
            "candidate_category": "general_document_candidate", "modified_at": "2026-01-01T00:00:00Z",
        }],
        "unresolved_saturated_intervals": [],
    }
    (tmp_path / "google_drive_connector_latest.json").write_text(json.dumps(connector), encoding="utf-8")
    result = document_atlas.merge_connector_atlas(tmp_path)
    assert result["stats"]["unified_record_count"] == 1
    assert result["stats"]["gdoc_pointer_duplicates_removed"] == 1
    status = document_atlas.atlas_status(tmp_path)
    assert status["available"] is True
    found = document_atlas.search_atlas("Pointer", output_dir=tmp_path)
    assert found["result_count"] == 1
    assert found["boundary"]["canon_promotion"] is False
