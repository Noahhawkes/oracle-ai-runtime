from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import companion_bootstrap as cb  # noqa: E402


def test_remember_me_grounding_injects_only_approved_records(tmp_path, monkeypatch):
    remember_dir = tmp_path / "remember_me"
    remember_dir.mkdir()
    monkeypatch.setattr(cb, "REMEMBER_ME_DIR", remember_dir)

    approved_id = "approved-anchor"
    pending_id = "pending-anchor"
    (remember_dir / "index.json").write_text(
        json.dumps({approved_id: "approved", pending_id: "pending"}),
        encoding="utf-8",
    )
    (remember_dir / f"{approved_id}.json").write_text(
        json.dumps({
            "title": "ORACLE Project Continuity Anchor - Noah Hawkes",
            "category": "builder",
            "confidence": "VERIFIED",
            "compressed_meaning": "Noah is not a generic user; ORACLE must preserve continuity with receipts.",
            "unknowns": ["Do not pretend a record contains the whole person."],
            "contradictions": ["Deep remembrance must stay source-grounded."],
            "tags": ["ORACLE", "Noah Hawkes", "continuity"],
            "source": "Noah.Physical current-session directive",
            "updated_at": "2026-07-14T00:00:00Z",
        }),
        encoding="utf-8",
    )
    (remember_dir / f"{pending_id}.json").write_text(
        json.dumps({
            "title": "Pending Should Not Appear",
            "category": "builder",
            "compressed_meaning": "This should not be injected.",
        }),
        encoding="utf-8",
    )

    lines = cb._remember_me_source_lines(limit=5)
    text = "\n".join(lines)

    assert "approved_record_count: 1" in text
    assert "ORACLE Project Continuity Anchor - Noah Hawkes" in text
    assert "Noah is not a generic user" in text
    assert "Pending Should Not Appear" not in text


def test_system_context_block_has_remember_me_section(tmp_path, monkeypatch):
    remember_dir = tmp_path / "remember_me"
    remember_dir.mkdir()
    monkeypatch.setattr(cb, "REMEMBER_ME_DIR", remember_dir)
    (remember_dir / "index.json").write_text("{}", encoding="utf-8")

    missing = cb.SourceRecord(
        path="missing",
        resolved="missing",
        exists=False,
        sha256=None,
        size_bytes=None,
        mtime_utc=None,
        load_error="file_not_found",
        content=None,
    )
    result = cb.BootstrapResult(identity=missing, latest_reflection=missing, live_context=missing)

    block = result.system_context_block()

    assert "SOURCE SECTION: REMEMBER_ME" in block
    assert "SOURCE SECTION: IDENTITY" in block


def test_system_context_block_has_thesis_corpus_section(tmp_path, monkeypatch):
    thesis_dir = tmp_path / "thesis_corpus"
    thesis_dir.mkdir()
    monkeypatch.setattr(cb, "THESIS_CORPUS_DIR", thesis_dir)
    (thesis_dir / "oracle_first_thesis_20250322.ai").write_text(
        "\n".join([
            ".AI:ORACLE_THESIS_CAPSULE",
            "title=First NoahAI Thesis",
            "source_sha256=26322394a53c39c4990fef5111823f837c2b76c977e3f7455fb0c7ec52800f0b",
            "thesis_vector=Integrating Noah.Physical, Noah.Self, and Noah.AI systems under Oracle.AI governance.",
            "compressed_meaning=The first thesis already contains the architecture.",
        ]),
        encoding="utf-8",
    )

    lines = cb._thesis_corpus_source_lines(limit=2)
    text = "\n".join(lines)

    assert "capsule_count: 1" in text
    assert "First NoahAI Thesis" in text
    assert "Noah.Physical, Noah.Self, and Noah.AI" in text

    missing = cb.SourceRecord(
        path="missing",
        resolved="missing",
        exists=False,
        sha256=None,
        size_bytes=None,
        mtime_utc=None,
        load_error="file_not_found",
        content=None,
    )
    result = cb.BootstrapResult(identity=missing, latest_reflection=missing, live_context=missing)

    block = result.system_context_block()

    assert "SOURCE SECTION: THESIS_CORPUS" in block
    assert "THESIS_CORPUS records are curated .AI thesis capsules" in block
