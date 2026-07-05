from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import source_map_stitcher as sms  # noqa: E402


def _record(path: str, query_text: str, *, preview: str | None = None) -> dict:
    p = Path(path)
    return {
        "path": path,
        "name": p.name,
        "extension": p.suffix.lower(),
        "size_bytes": 123,
        "mtime_utc": "2026-07-04T20:00:00+00:00",
        "sha256_prefix": "abc123def4567890",
        "content_preview": preview or f"{query_text} local continuity note",
        "content_available": preview is not None,
        "source_root": str(ROOT),
        "category": "text",
    }


def test_build_capsule_dedupes_filters_and_writes_outside_sandbox(tmp_path):
    shared = _record(r"C:\Oracle\ORACLE.AI-runtime\Memory\source_note.md", "ORACLE")
    drive = _record(
        r"G:\My Drive\HawkesNest LLC\ORACLE.AI\source_map.md",
        "SourceMap",
        preview="api_key=abcdef should be redacted",
    )
    secret = _record(r"C:\Oracle\ORACLE.AI-runtime\.env", "ORACLE", preview="ANTHROPIC_API_KEY=secret")

    def fake_search(query: str, limit: int) -> list[dict]:
        if query == "ORACLE":
            return [shared, secret]
        if query == "SourceMap":
            return [shared, drive]
        return []

    capsule = sms.build_capsule(
        ["ORACLE", "SourceMap"],
        5,
        search_fn=fake_search,
        capsule_dir=tmp_path / "capsules",
        latest_path=tmp_path / "latest.json",
    )

    assert capsule["ok"] is True
    assert capsule["counts"]["raw_hits"] == 4
    assert capsule["counts"]["deduped_sources"] == 2
    assert capsule["counts"]["excluded_sensitive"] == 1
    assert capsule["safety"]["read_only"] is True
    assert capsule["safety"]["sandbox_write"] is False
    assert capsule["safety"]["external_send"] is False
    assert all("sandbox" not in str(source["path"]).lower() for source in capsule["sources"])
    assert "abcdef" not in json.dumps(capsule["sources"])
    assert "api_key=[REDACTED]" in json.dumps(capsule["sources"])

    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert latest["latest_path"].endswith("latest.json")
    assert Path(capsule["capsule_path"]).parent == tmp_path / "capsules"


def test_latest_capsule_prompt_context_is_compact_and_safety_labeled(tmp_path):
    latest_path = tmp_path / "latest.json"
    latest_path.write_text(json.dumps({
        "ok": True,
        "created_at": "2026-07-04T20:00:00Z",
        "anchor_queries": ["ORACLE"],
        "counts": {"deduped_sources": 1, "excluded_sensitive": 0},
        "sources": [{
            "name": "source_note.md",
            "path": r"C:\Oracle\ORACLE.AI-runtime\Memory\source_note.md",
            "category": "text",
            "sha256_prefix": "abc123def4567890",
            "content_preview": "ORACLE continuity note",
        }],
    }), encoding="utf-8")

    context = sms.latest_capsule_prompt_context(latest_path=latest_path, max_sources=1)

    assert "source_map_capsule:" in context
    assert "safety: read_only=true sandbox_write=false external_send=false canon_promotion=false" in context
    assert "source_note.md" in context
    assert "ORACLE continuity note" in context


def test_child_self_prompt_includes_latest_source_map_capsule(monkeypatch, tmp_path):
    latest_path = tmp_path / "latest.json"
    latest_path.write_text(json.dumps({
        "ok": True,
        "created_at": "2026-07-04T20:00:00Z",
        "anchor_queries": ["Ellie"],
        "counts": {"deduped_sources": 1, "excluded_sensitive": 0},
        "sources": [{
            "name": "ellie_note.md",
            "path": r"C:\Oracle\ORACLE.AI-runtime\data\domains\ellie\ellie_note.md",
            "category": "text",
            "sha256_prefix": "feedface12345678",
            "content_preview": "Ellie sandbox recall seed",
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(sms, "LATEST_CAPSULE_PATH", latest_path)

    import oracle_server as srv  # noqa: E402

    prompt = srv._build_sandbox_self_child_prompt("scheduled tick")

    assert "read_only_source_map_capsule_context:" in prompt
    assert "ellie_note.md" in prompt
    assert "sandbox_write=false" in prompt
