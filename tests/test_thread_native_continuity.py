from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import thread_native_continuity as tnc  # noqa: E402


def make_store(tmp_path: Path) -> tnc.ThreadStore:
    store = tnc.ThreadStore(tmp_path / "thread_native_continuity.db")
    store.init_schema()
    return store


def test_thread_survives_restart_with_candidate_boundaries(tmp_path: Path):
    store = make_store(tmp_path)
    store.upsert_thread(
        tnc.ThreadRecord(
            thread_id="rendered-reality",
            human_title="Rendered Reality",
            aliases=("Rendered Reality", "ORACLE continuity"),
            creation_date="2026-07-23T10:00:00+00:00",
            last_activity="2026-07-23T10:05:00+00:00",
            participants=("Noah.Physical", "ORACLE"),
            related_projects=("ORACLE.AI",),
            next_actions=("Implement thread heartbeat",),
            provenance={"authority": tnc.NOAH_AUTHORITY},
            confidence=0.7,
        )
    )

    restarted = tnc.ThreadStore(tmp_path / "thread_native_continuity.db")
    restarted.init_schema()
    record = restarted.get_thread("rendered-reality")

    assert record is not None
    assert record.human_title == "Rendered Reality"
    assert "ORACLE continuity" in record.aliases
    assert record.next_actions == ("Implement thread heartbeat",)
    assert record.canon_status == tnc.CANON_CANDIDATE
    assert record.promotion_status == tnc.NO_CANON_PROMOTION
    assert record.approval_state == tnc.DEFAULT_APPROVAL_STATE


def test_source_ingestion_preserves_hash_and_extracts_thread_items(tmp_path: Path):
    store = make_store(tmp_path)
    store.upsert_thread(
        tnc.ThreadRecord(
            thread_id="oracle-runtime",
            human_title="ORACLE Runtime",
            aliases=("ORACLE Runtime", "Thread-Native Continuity"),
            creation_date="2026-07-23T10:00:00+00:00",
            last_activity="2026-07-23T10:00:00+00:00",
        )
    )
    raw = "\n".join(
        [
            "This belongs to Thread-Native Continuity.",
            "FACT[port]: Authoritative port is 7781.",
            "TASK[engine]: Implement persistent thread object.",
            "WAITING_ON[review]: Noah.Physical approval for canon promotion.",
            "NEXT_ACTION[brief]: Generate operational briefing from thread state.",
        ]
    )
    source = tnc.make_source_record(
        origin="codex_prompt",
        source_identifier=".AI:THREAD_NATIVE_CONTINUITY_ENGINE/2026-07-23",
        raw_content=raw,
        timestamp="2026-07-23T11:00:00+00:00",
        provenance={"transport": "Codex", "authorial_authority": tnc.NOAH_AUTHORITY},
    )

    result = store.ingest_source(source)
    saved_source = store.get_source(source.source_id)
    thread = store.get_thread("oracle-runtime")

    assert result.thread_ids == ("oracle-runtime",)
    assert len(result.item_ids) == 4
    assert saved_source is not None
    assert saved_source.sha256 == source.sha256
    assert saved_source.raw_content == raw
    assert thread is not None
    assert thread.confirmed_facts == ("Authoritative port is 7781.",)
    assert thread.tasks == ("Implement persistent thread object.",)
    assert thread.waiting_on == ("Noah.Physical approval for canon promotion.",)
    assert thread.next_actions == ("Generate operational briefing from thread state.",)
    assert result.canon_status == tnc.CANON_CANDIDATE
    assert result.promotion_status == tnc.NO_CANON_PROMOTION


def test_corrections_preserve_history_and_supersede_current_claim(tmp_path: Path):
    store = make_store(tmp_path)
    store.upsert_thread(
        tnc.ThreadRecord(
            thread_id="oracle-runtime",
            human_title="ORACLE Runtime",
            aliases=("ORACLE Runtime",),
        )
    )
    first_source = tnc.make_source_record(
        origin="test",
        source_identifier="first",
        raw_content="FACT[port]: Authoritative port is 7777.",
        timestamp="2026-07-23T11:00:00+00:00",
    )
    correction_source = tnc.make_source_record(
        origin="test",
        source_identifier="correction",
        raw_content="CORRECTION[port]: Authoritative port is 7781.",
        timestamp="2026-07-23T11:05:00+00:00",
    )

    store.ingest_source(first_source, candidate_thread_ids=("oracle-runtime",))
    store.ingest_source(correction_source, candidate_thread_ids=("oracle-runtime",))
    current = store.get_thread("oracle-runtime")

    with sqlite3.connect(tmp_path / "thread_native_continuity.db") as conn:
        rows = conn.execute(
            "SELECT item_type, value, superseded_by FROM thread_items WHERE thread_id = ? ORDER BY created_at",
            ("oracle-runtime",),
        ).fetchall()

    assert current is not None
    assert current.confirmed_facts == ()
    assert current.corrections == ("Authoritative port is 7781.",)
    assert len(rows) == 2
    assert rows[0][0] == "confirmed_fact"
    assert rows[0][1] == "Authoritative port is 7777."
    assert rows[0][2]
    assert rows[1][0] == "correction"
    assert rows[1][2] == ""


def test_heartbeat_exposes_operational_state(tmp_path: Path):
    store = make_store(tmp_path)
    store.upsert_thread(
        tnc.ThreadRecord(
            thread_id="dealer-locator",
            human_title="Dealer Locator",
            creation_date="2026-07-23T10:00:00+00:00",
            last_activity="2026-07-23T10:15:00+00:00",
            waiting_on=("NexGen source export",),
            next_actions=("Compare dealer expansion notes",),
            confidence=0.62,
        )
    )

    heartbeat = store.generate_heartbeat(
        "dealer-locator",
        urgency="high",
        downstream_dependencies=("Costco Expansion",),
        generated_at="2026-07-23T10:20:00+00:00",
    )
    latest = store.latest_heartbeat("dealer-locator")

    assert heartbeat.state == tnc.ThreadState.WAITING
    assert heartbeat.waiting_on == ("NexGen source export",)
    assert heartbeat.next_expected_event == "Compare dealer expansion notes"
    assert heartbeat.downstream_dependencies == ("Costco Expansion",)
    assert latest == heartbeat


def test_thread_relationship_graph_keeps_threads_distinct(tmp_path: Path):
    store = make_store(tmp_path)
    store.upsert_thread(tnc.ThreadRecord(thread_id="dealer-locator", human_title="Dealer Locator"))
    store.upsert_thread(tnc.ThreadRecord(thread_id="costco-expansion", human_title="Costco Expansion"))

    edge = store.link_threads(
        "dealer-locator",
        "costco-expansion",
        relation="downstream_strategy",
        evidence_source_id="src-test",
        confidence=0.75,
    )

    dealer = store.get_thread("dealer-locator")
    costco = store.get_thread("costco-expansion")

    assert edge.relation == "downstream_strategy"
    assert dealer is not None
    assert costco is not None
    assert dealer.related_threads == ("costco-expansion",)
    assert costco.related_threads == ("dealer-locator",)
    assert dealer.human_title == "Dealer Locator"
    assert costco.human_title == "Costco Expansion"


def test_daily_operational_briefing_comes_from_thread_state(tmp_path: Path):
    store = make_store(tmp_path)
    store.upsert_thread(
        tnc.ThreadRecord(
            thread_id="ai-compliance-core",
            human_title="AI Compliance Core",
            last_activity="2026-07-23T10:30:00+00:00",
            tasks=("Package audit kit",),
            next_actions=("Draft customer-facing offer",),
            confidence=0.8,
        )
    )
    store.upsert_thread(
        tnc.ThreadRecord(
            thread_id="old-thread",
            human_title="Old Thread",
            thread_health="archived",
            confidence=0.9,
        )
    )

    briefing = store.daily_operational_briefing()

    assert briefing["schema_version"] == tnc.SCHEMA_VERSION
    assert briefing["thread_count"] == 2
    assert briefing["canon_promoted"] is False
    assert briefing["external_action_performed"] is False
    entries = briefing["active_entries"]
    assert len(entries) == 1
    assert entries[0]["thread_id"] == "ai-compliance-core"
    assert entries[0]["state"] == "ACTIVE"
    assert entries[0]["next_expected_event"] == "Draft customer-facing offer"
