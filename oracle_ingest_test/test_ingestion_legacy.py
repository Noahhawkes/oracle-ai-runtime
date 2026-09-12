import pytest
import json
import shutil
from pathlib import Path
import ingest_engine as ie

@pytest.fixture(autouse=True)
def setup_and_teardown():
    if ie.WORKSPACE_DIR.exists():
        shutil.rmtree(ie.WORKSPACE_DIR)
    ie.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if ie.WORKSPACE_DIR.exists():
        shutil.rmtree(ie.WORKSPACE_DIR)

def test_valid_txt_ingest_creates_receipt():
    src_file = ie.WORKSPACE_DIR / "source.txt"
    src_file.write_text("Hello World", encoding="utf-8")
    receipt = ie.ingest_raw_artifact("destination.txt", str(src_file))
    assert receipt["receipt_type"] == "raw_artifact_ingested"
    assert "receipt_id" in receipt
    assert "artifact_id" in receipt

def test_sha256_matches_vaulted_file():
    src_file = ie.WORKSPACE_DIR / "source.txt"
    content = "Cryptographic integrity check payload."
    src_file.write_text(content, encoding="utf-8")
    receipt = ie.ingest_raw_artifact("dest.txt", str(src_file))
    vaulted_file = Path(receipt["vault_path"])
    assert vaulted_file.exists()
    assert ie.calculate_sha256(vaulted_file) == receipt["sha256"]

def test_typos_and_line_breaks_preserved_exactly():
    src_file = ie.WORKSPACE_DIR / "source.txt"
    raw_text = "Thiz contains a typpo.\n\nAnd multiple line breks   with space."
    src_file.write_text(raw_text, encoding="utf-8")
    receipt = ie.ingest_raw_artifact("dest.txt", str(src_file))
    vaulted_text = Path(receipt["vault_path"]).read_text(encoding="utf-8")
    assert vaulted_text == raw_text

def test_missing_source_creates_open_hole_json():
    missing_path = ie.WORKSPACE_DIR / "nonexistent.txt"
    hole_record = ie.ingest_raw_artifact("dest.txt", str(missing_path))
    assert hole_record["basis_label"] == "ABSENT_DATA_HOLE"
    assert hole_record["hole_type"] == "missing_source_file"
    assert hole_record["status"] == "open"
    hole_file = ie.OPEN_HOLES_DIR / f"{hole_record['hole_id']}.json"
    assert hole_file.exists()

def test_unsafe_target_filename_creates_open_hole():
    src_file = ie.WORKSPACE_DIR / "source.txt"
    src_file.write_text("Safe content", encoding="utf-8")
    hole_record = ie.ingest_raw_artifact("../escaped.txt", str(src_file))
    assert hole_record["basis_label"] == "ABSENT_DATA_HOLE"
    assert hole_record["hole_type"] == "unsafe_target_path"

def test_directory_source_creates_open_hole():
    src_dir = ie.WORKSPACE_DIR / "sub_folder"
    src_dir.mkdir()
    hole_record = ie.ingest_raw_artifact("dest.txt", str(src_dir))
    assert hole_record["basis_label"] == "ABSENT_DATA_HOLE"
    assert hole_record["hole_type"] == "source_not_file"

def test_corrupt_ledger_json_is_backed_up_and_does_not_crash():
    ie.LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    ie.LEDGER_FILE.write_text("{invalid_json_corrupted", encoding="utf-8")
    src_file = ie.WORKSPACE_DIR / "source.txt"
    src_file.write_text("Data stream", encoding="utf-8")
    receipt = ie.ingest_raw_artifact("dest.txt", str(src_file))
    assert receipt["receipt_type"] == "raw_artifact_ingested"
    backups = list(ie.LEDGER_DIR.glob("provenance_ledger.corrupt.*.bak.json"))
    assert len(backups) == 1

def test_canon_status_remains_false():
    src_file = ie.WORKSPACE_DIR / "source.txt"
    src_file.write_text("Standard payload", encoding="utf-8")
    receipt = ie.ingest_raw_artifact("dest.txt", str(src_file))
    assert receipt["canon_status"] is False

def test_transformation_chain_is_empty_for_raw_artifact():
    src_file = ie.WORKSPACE_DIR / "source.txt"
    src_file.write_text("Raw untransformed text.", encoding="utf-8")
    receipt = ie.ingest_raw_artifact("dest.txt", str(src_file))
    assert receipt["transformation_chain"] == []

def test_atomic_write_leaves_a_valid_json_ledger():
    src_file = ie.WORKSPACE_DIR / "source.txt"
    src_file.write_text("Validation string", encoding="utf-8")
    ie.ingest_raw_artifact("dest.txt", str(src_file))
    assert ie.LEDGER_FILE.exists()
    with ie.LEDGER_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
