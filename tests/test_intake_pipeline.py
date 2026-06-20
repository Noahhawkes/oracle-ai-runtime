"""Smoke tests for governed ORACLE file intake (core/intake_pipeline.py).

Proves: secrets are flagged by path/type and never copied/hashed; safe files
are staged by copy with full manifest fields; cloud stubs are skipped; the run
is idempotent (same SHA-256 never stages twice); originals are never modified;
promotion is copy-only after approval. No network, isolated temp dirs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import intake_pipeline as ip  # noqa: E402


def _redirect(tmp_path):
    """Point all intake outputs at a temp area so tests never touch real intake."""
    base = tmp_path / "intake"
    ip.INTAKE = base
    ip.STAGING = base / "staging"
    ip.MANIFESTS = base / "manifests"
    ip.QUARANTINE = base / "quarantine"
    ip.APPROVED = base / "approved"
    ip.SOURCE_MAPS = tmp_path / "Memory" / "source_maps"
    ip.STAGED_INDEX = ip.MANIFESTS / "staged_index.json"
    ip.PENDING_PROMOTIONS = ip.MANIFESTS / "pending_promotions.json"
    ip.LATEST_MANIFEST = ip.MANIFESTS / "intake_manifest_latest.json"


def _make_sources(tmp_path):
    """Create a fake source tree + a scan file describing it."""
    src = tmp_path / "oracle_sources"   # 'oracle' in path → keyword match
    src.mkdir(parents=True)
    code = src / "oracle_runner.py"
    code.write_text("print('oracle')\n", encoding="utf-8")
    dup = src / "oracle_runner_copy.py"
    dup.write_text("print('oracle')\n", encoding="utf-8")   # identical → duplicate
    env = src / ".env"
    env.write_text("API_KEY=sk-secret-should-never-be-copied\n", encoding="utf-8")
    stub = src / "SOV1_doctrine.gdoc"
    stub.write_text('{"doc_id":"abc"}', encoding="utf-8")
    big = src / "oracle_big_archive.zip"
    big.write_text("x", encoding="utf-8")   # tiny on disk; scan claims huge size

    lines = [
        "ORACLE content scan — test",
        "",
        "========== ROOT: C:\\ ==========",
        "Matched dirs: 1   Matched files: 5",
        "",
        "--- Directories ---",
        str(src),
        "",
        "--- Files ---",
        f"{code}\t2026-06-20\t{code.stat().st_size} bytes",
        f"{dup}\t2026-06-20\t{dup.stat().st_size} bytes",
        f"{env}\t2026-06-20\t{env.stat().st_size} bytes",
        f"{stub}\t2026-06-20\t{stub.stat().st_size} bytes",
        f"{big}\t2026-06-20\t999999999 bytes",
        "G:\\My Drive\\oracle_cloud_doc.txt\t2026-06-20\t1234 bytes",
        "",
        "========== SCAN COMPLETE ==========",
    ]
    scan = tmp_path / "scan.txt"
    scan.write_text("\n".join(lines), encoding="utf-8")
    return src, scan, {"code": code, "dup": dup, "env": env, "stub": stub, "big": big}


def _entries_by_name(summary_manifest, name):
    import json
    data = json.loads(Path(summary_manifest).read_text(encoding="utf-8"))
    return [e for e in data["entries"] if e["filename"] == name]


def test_governed_intake_full_pass(tmp_path):
    _redirect(tmp_path)
    src, scan, files = _make_sources(tmp_path)

    summary = ip.build_intake(scan)
    manifest = summary["manifest_path"]

    # Secret: flagged by path/type, NOT staged, NOT hashed, NOT copied.
    env_e = _entries_by_name(manifest, ".env")[0]
    assert env_e["classification"] == ip.SECRET_RISK
    assert env_e["ingest_status"] == ip.ST_SECRET
    assert env_e["staged_path"] == ""
    assert env_e["sha256"] == ""
    assert not (ip.STAGING / ".env").exists()
    # Secret VALUE must never leak into the manifest.
    assert "sk-secret-should-never-be-copied" not in Path(manifest).read_text(encoding="utf-8")

    # Safe code file: staged by copy, full fields present.
    code_e = _entries_by_name(manifest, "oracle_runner.py")[0]
    assert code_e["classification"] == ip.RUNTIME_CODE
    assert code_e["ingest_status"] == ip.ST_STAGED
    assert code_e["sha256"]
    assert "oracle" in code_e["keyword_matches"]
    assert code_e["source_drive"]
    assert Path(code_e["staged_path"]).exists()

    # Duplicate content → not staged twice.
    dup_e = _entries_by_name(manifest, "oracle_runner_copy.py")[0]
    assert dup_e["ingest_status"] == ip.ST_DUPLICATE

    # Cloud stub skipped.
    stub_e = _entries_by_name(manifest, "SOV1_doctrine.gdoc")[0]
    assert stub_e["ingest_status"] == ip.ST_CLOUD_STUB

    # Oversized (per scan) deferred, not staged.
    big_e = _entries_by_name(manifest, "oracle_big_archive.zip")[0]
    assert big_e["ingest_status"] == ip.ST_LARGE

    # Cloud-backed (G:) file deferred — never hashed/copied (no network).
    cloud_e = _entries_by_name(manifest, "oracle_cloud_doc.txt")[0]
    assert cloud_e["ingest_status"] == ip.ST_CLOUD_DEFERRED
    assert cloud_e["sha256"] == ""
    assert cloud_e["source_drive"] == "G:"

    # Originals untouched.
    for f in files.values():
        assert f.exists()
    assert files["env"].read_text(encoding="utf-8").startswith("API_KEY=")

    # A pending promotion exists for the staged file.
    assert summary["pending_promotions"] >= 1


def test_idempotent_rerun_does_not_double_stage(tmp_path):
    _redirect(tmp_path)
    src, scan, files = _make_sources(tmp_path)

    ip.build_intake(scan)
    staged_after_first = sorted(p.name for p in ip.STAGING.iterdir())

    ip.build_intake(scan)   # re-run
    staged_after_second = sorted(p.name for p in ip.STAGING.iterdir())

    assert staged_after_first == staged_after_second   # no new copies


def test_promote_copies_to_approved_without_moving(tmp_path):
    _redirect(tmp_path)
    src, scan, files = _make_sources(tmp_path)
    ip.build_intake(scan)

    pending = ip.list_pending_promotions()
    assert pending, "expected at least one pending promotion"
    sha = pending[0]["sha256"]
    staged_path = Path(pending[0]["staged_path"])

    res = ip.promote(sha, approved_by="noah")
    assert res["ok"] is True
    assert Path(res["approved_path"]).exists()
    # Copy, not move: staged file still present.
    assert staged_path.exists()


def test_approval_center_surfaces_intake_pending(tmp_path):
    _redirect(tmp_path)
    src, scan, files = _make_sources(tmp_path)
    ip.build_intake(scan)

    import approval_center as ac
    pend = ac.list_pending()
    assert any(item.get("source") == "intake" for item in pend)
