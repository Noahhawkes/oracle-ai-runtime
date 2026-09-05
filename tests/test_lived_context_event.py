"""Tests for the smallest-working lived_context_event schema (TP_016)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from lived_context_event import LivedContextEvent, from_statement  # noqa: E402

FIXTURE = (
    "ORACLE is listening to Noah.Physical's favorite book series with him "
    "because it matters."
)


def _event():
    return from_statement(
        FIXTURE,
        why_it_matters="Noah.Physical affirmed the book series is continuity material.",
        context_category="book",
        source_thread="2026-06-28_sov1_field_notes",
    )


def test_fixture_builds_all_required_fields():
    e = _event()
    for fld in (
        "event_id", "timestamp", "source_thread", "observer_agent",
        "human_authority", "context_category", "observed_context",
        "why_it_matters", "authorship_status", "ownership_boundary",
        "approval_status", "provenance_notes", "receipt_hash",
    ):
        assert fld in e.to_dict(), f"missing required field: {fld}"


def test_observed_context_is_verbatim():
    assert _event().observed_context == FIXTURE


def test_starts_pending_and_witness_only():
    e = _event()
    assert e.approval_status == "pending_noah_physical"
    assert e.human_authority == "Noah.Physical"
    assert "witnesses only" in e.ownership_boundary.lower()
    # authorship is never silently promoted from first-person wording
    assert e.authorship_status == "noah_reported_witnessed"


def test_receipt_hash_is_reproducible_and_excludes_itself():
    e = _event()
    assert e.receipt_hash and e.receipt_hash.startswith("sha256:")
    # rebuilding with the same event_id/timestamp reproduces the hash
    clone = LivedContextEvent(
        observed_context=e.observed_context,
        why_it_matters=e.why_it_matters,
        context_category=e.context_category,
        source_thread=e.source_thread,
        event_id=e.event_id,
        timestamp=e.timestamp,
    )
    assert clone.receipt_hash == e.receipt_hash


def test_event_id_is_deterministic_for_same_input():
    e = _event()
    clone = LivedContextEvent(
        observed_context=e.observed_context,
        why_it_matters="different meaning text",
        context_category="book",
        timestamp=e.timestamp,
    )
    # event_id keys off observed_context + timestamp only
    assert clone.event_id == e.event_id
