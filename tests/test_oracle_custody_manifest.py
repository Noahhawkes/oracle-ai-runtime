import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import oracle_custody_sweep as sweep  # noqa: E402


def _rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_oracle_custody_sweep_writes_metadata_only_manifest(tmp_path):
    root = tmp_path / "scan"
    root.mkdir()
    (root / "Rendered Reality notes.md").write_text("continuity witness", encoding="utf-8")
    (root / "plain.txt").write_text("SOV1 and UserPath are mapped here.", encoding="utf-8")
    (root / "private_finance.txt").write_text("no marker here", encoding="utf-8")
    (root / "oracle_duplicate_a.md").write_text("ORACLE duplicate payload", encoding="utf-8")
    (root / "oracle_duplicate_b.md").write_text("ORACLE duplicate payload", encoding="utf-8")

    receipt = sweep.run_sweep([root], output_dir=tmp_path / "out")
    manifest_path = Path(receipt["manifest_path"])
    rows = _rows(manifest_path)

    assert manifest_path.exists()
    assert len(rows) == 4
    assert receipt["artifact_count"] == 4
    assert receipt["duplicate_group_count"] == 1
    assert receipt["rules"]["cloud_upload"] is False
    assert receipt["rules"]["git_push"] is False
    assert receipt["rules"]["execution"] is False

    for row in rows:
        for field in sweep.REQUIRED_FIELDS:
            assert field in row
        assert row["custody_status"] == "observed"
        assert row["copy_status"] == "not_copied"
        assert row["store_status"] == "indexed"
        assert row["canon_status"] == "candidate"
        assert row["promotion_status"] == "not_promoted"
        assert row["sha256"]
        assert "content" not in row
        assert "raw_text" not in row


def test_oracle_custody_sweep_does_not_index_private_files_without_markers(tmp_path):
    root = tmp_path / "scan"
    root.mkdir()
    private = root / "family" / "medical_notes.txt"
    private.parent.mkdir()
    private.write_text("routine private note without project markers", encoding="utf-8")
    marked = root / "family" / "ORACLE medical boundary.md"
    marked.write_text("ORACLE marker makes this a high-sensitivity candidate.", encoding="utf-8")

    receipt = sweep.run_sweep([root], output_dir=tmp_path / "out")
    rows = _rows(Path(receipt["manifest_path"]))

    assert len(rows) == 1
    assert rows[0]["filename"] == "ORACLE medical boundary.md"
    assert rows[0]["sensitivity"] == "high"
    assert rows[0]["copy_status"] == "not_copied"


def test_marker_matching_supports_path_and_content_aliases():
    assert "ORACLE.AI" in sweep.text_matches_markers("C:/ORACLE1.AI/memory")
    assert "Rendered Reality" in sweep.text_matches_markers("rendered_reality_source")
    assert "Legacy.GI" in sweep.text_matches_markers("legacy gi archive")
