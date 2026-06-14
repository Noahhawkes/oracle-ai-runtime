from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def test_capability_broker_exposes_required_components_without_smoke():
    from capability_broker import discover_capabilities

    statuses = discover_capabilities(run_smokes=False)
    by_component = {s.component: s for s in statuses}
    required = {
        "ORACLE web UI",
        "ORACLE conversation core",
        "Continuity Fabric L1 memory",
        "Continuity Fabric L2 FTS5 recall",
        "durable memory",
        "operational world model",
        "vision model",
        "live visual observer",
        "OBS integration",
        "SOV1 vision",
        "SOV1 actuation",
        "local file access",
        "Git access",
        "GitHub access",
        "Google Drive local sync",
        "MiracleDrive index",
        "Claude Code bridge",
        "Codex bridge",
        "ChatGPT relay",
        "Ollama",
        "TTS",
        "STT",
        "approval queue",
        "execution receipts",
        "background watchers",
        "event polling",
        "replication workers",
    }

    assert required <= set(by_component)
    sample = by_component["ORACLE web UI"].to_dict()
    for key in (
        "registered",
        "implemented",
        "authenticated",
        "permitted",
        "available",
        "callable_from_oracle_web",
        "callable_from_oracle_core",
        "last_tested",
        "last_successful_receipt",
        "current_status",
        "blocker",
        "installed",
        "callable",
        "tested",
        "degraded",
        "blocked",
    ):
        assert key in sample


def test_capability_commands_are_wired_to_web_and_cli_sources():
    web = (ROOT / "oracle_server.py").read_text(encoding="utf-8", errors="replace")
    cli = (CORE / "oracle.py").read_text(encoding="utf-8", errors="replace")

    for command in ("/capabilities", "/doctor", "/tool-status", "/active-tasks"):
        assert command in web
        assert command in cli
    assert "capability_broker" in web
    assert "capability_broker" in cli


def test_miracledrive_query_can_force_synchronous_index(monkeypatch):
    import miracledrive_index

    record = miracledrive_index.FileRecord(
        path=str(ROOT / "docs" / "LIGHT.md"),
        name="LIGHT.md",
        extension=".md",
        size_bytes=42,
        mtime_utc="2026-06-14T00:00:00+00:00",
        sha256_prefix="abc123abc123abcd",
        content_preview="light compression law",
        content_available=True,
        source_root=str(ROOT / "docs"),
        category="text",
    )
    index = miracledrive_index.DriveIndex(
        built_at="2026-06-14T00:00:00+00:00",
        total_files=1,
        total_bytes=42,
        source_paths_scanned=[str(ROOT / "docs")],
        source_paths_missing=[],
        files=[record],
    )
    monkeypatch.setattr(miracledrive_index, "build_index", lambda: index)

    results = miracledrive_index.query("light compression", force_build=True)

    assert len(results) == 1
    assert results[0]["name"] == "LIGHT.md"


def test_miracledrive_cold_search_filters_nonmatching_large_files(tmp_path, monkeypatch):
    import miracledrive_index

    matching = tmp_path / "law.md"
    matching.write_text("the light compression law is here", encoding="utf-8")
    large_nonmatch = tmp_path / "random.pdf"
    large_nonmatch.write_bytes(b"x" * (miracledrive_index.MAX_CONTENT_BYTES + 10))
    monkeypatch.setattr(miracledrive_index, "_iter_source_roots", lambda: [tmp_path])

    results = miracledrive_index.search_filesystem("light compression", limit=10)
    names = {r["name"] for r in results}

    assert "law.md" in names
    assert "random.pdf" not in names
