"""Regression tests for the self-prompt source-reading patch.

Guarantees:
  * No active self-prompt path emits the old "source gap audit from the approved
    index map" plumbing task.
  * The brief, the fallback, and the child prompt all use the structured reading
    schema (OBSERVED / INTERPRETED / UNKNOWN / CONTRADICTION / NEXT_SOURCE_QUESTION).
  * duplicate-family suppression collapses copy/timestamp filename families.
  * source rotation is deterministic and varies with seed.
  * sandbox-only / no-external / no-canon boundaries are preserved everywhere.
  * the corpus excerpt is bounded and carries a receipt (sha256 + path).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import self_prompt_evolution as spe  # noqa: E402

OLD_TASK_MARKERS = ("source gap audit", "gap audit from the approved index map")
READING_SCHEMA = ("OBSERVED", "INTERPRETED", "UNKNOWN", "CONTRADICTION", "NEXT_SOURCE_QUESTION")
BOUNDARY_MARKERS = ("sandbox_write=false", "external_send=false")


# ── duplicate-family suppression ──────────────────────────────────────────────

def test_family_key_collapses_copy_and_timestamp_families():
    fk = spe.family_key
    # copies collapse to the same lineage
    assert fk("SOV1 - Copy.txt") == fk("sov1.txt") == fk("SOV1 (2).txt")
    # timestamp/id suffixes drop out
    assert fk("sov1_manifesto_20250612_135341.txt") == "sov1 manifesto"
    assert fk("sov1._summary_-_copy.txt") == "sov1 summary"
    assert fk("SOV1_IdentityFrame - Copy.txt") == "sov1 identityframe"


def test_suppress_duplicate_families_skips_recent_and_seen():
    names = [
        "SOV1 - Copy.txt",
        "sov1 (2).txt",                    # same family as above -> dropped (seen)
        "sov1_manifesto_20250612.txt",
        "rendered_reality_book.docx",
    ]
    kept = spe.suppress_duplicate_families(names, recent_family_keys=["sov1 manifesto"])
    fams = [spe.family_key(n) for n in kept]
    assert "sov1 manifesto" not in fams          # recently read -> suppressed
    assert fams.count("sov1") == 1               # duplicate family collapsed to one
    assert "rendered reality book" in fams


# ── no active path emits the old plumbing task ────────────────────────────────

def test_evolution_brief_has_no_source_gap_audit_and_has_reading_schema():
    brief = spe.render_evolution_brief(
        seed_text="seed",
        journal_text="child_response:\nselected_task: something\nself_reflection: done\n",
        capsule={"sources": [{"source_id": "src_a", "name": "A", "category": "c"}]},
    )
    low = brief.lower()
    for marker in OLD_TASK_MARKERS:
        assert marker not in low, f"old plumbing task leaked: {marker}"
    for field in READING_SCHEMA:
        assert field in brief, f"missing reading-schema field: {field}"
    for b in BOUNDARY_MARKERS:
        assert b in brief, f"boundary marker missing: {b}"
    # existing contract markers preserved (backwards compatibility)
    assert ".AI:SELF_PROMPT_EVOLUTION_BRIEF" in brief
    assert "repeated_task_blacklist:" in brief
    assert "rotating_focus_sources:" in brief


def test_fallback_response_emits_reading_task_not_plumbing_audit():
    resp = spe.fallback_response(
        seed_text="seed",
        journal_text="",
        capsule={"sources": [{"source_id": "src_x", "name": "SOV1_Manifesto"}]},
        reason="model_disabled",
    )
    low = resp.lower()
    for marker in OLD_TASK_MARKERS:
        assert marker not in low
    assert "selected_task:" in resp
    assert "read " in low  # a reading task
    # boundary + parser strings the rest of the pipeline relies on
    assert "candidate reflection only" in resp
    assert "git push" in low
    assert "model_fallback_reason: model_disabled" in resp


def test_fallback_rotates_and_avoids_repeated_family():
    # If the top reading task overlaps a recent task, a different one is chosen.
    journal = (
        "child_response:\n"
        "selected_task: read SOV1_Manifesto (src_x) and record OBSERVED / INTERPRETED / "
        "UNKNOWN / CONTRADICTION / NEXT_SOURCE_QUESTION about its content\n"
        "self_reflection: done\n"
    )
    resp = spe.fallback_response(
        seed_text="seed",
        journal_text=journal,
        capsule={"sources": [{"source_id": "src_x", "name": "SOV1_Manifesto"}]},
        reason="model_disabled",
    )
    # still a reading task, still bounded, no plumbing audit
    assert "selected_task:" in resp
    assert "source gap audit" not in resp.lower()


# ── the child prompt (oracle_server) ──────────────────────────────────────────

def test_child_prompt_uses_reading_schema_and_holds_boundaries():
    import oracle_server as srv

    prompt = srv._build_sandbox_self_child_prompt("regression seed")
    for field in READING_SCHEMA:
        assert field in prompt, f"child prompt missing reading field: {field}"
    assert "approved_source_excerpt" in prompt

    # The OLD instruction must be gone. Note: the phrase may still appear inside
    # the do-not-repeat blacklist or fed-forward journal history (memory of past
    # cycles), which is correct — that is not an instruction to do it again.
    assert "preferred_shapes: source gap audit" not in prompt
    # The NEW instruction must be present and dominant.
    assert "READ THIS" in prompt
    assert "reading task about content" in prompt or "READ the approved_source_excerpt" in prompt

    # boundaries preserved
    assert "sandbox_write=false" in prompt
    assert "no canon promotion" in prompt.lower()
    assert "no external send" in prompt.lower()
    # candidate-pipeline fields preserved so downstream parsers still work
    assert "selected_task:" in prompt
    assert "purpose_lane:" in prompt


def test_excerpt_block_renders_receipt_or_none():
    import oracle_server as srv

    # none -> explicit none_available, never fabricated
    assert srv._self_prompt_excerpt_block(None) == "none_available"

    block = srv._self_prompt_excerpt_block({
        "source_name": "sov1_manifesto.txt",
        "topic": "ORACLE & SOV1",
        "source_sha256": "abcdef0123456789",
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
        "excerpt_chars": 42,
        "excerpt": "I run on cost, loss, faith, fire. All sealed.",
    })
    assert "approved_source_read:" in block
    assert "sha256=abcdef012345" in block          # receipt present, truncated
    assert "candidate/not_promoted" in block        # status carried through
    assert "excerpt:" in block


def test_private_topics_are_excluded_from_reading_pool():
    import oracle_server as srv

    fn = srv._self_prompt_topic_is_private
    # private personal records must be excluded
    assert fn("Financial & Tax", "june_uufcu_statement2016.pdf")
    assert fn("Medical", "")
    assert fn("Vehicles", "")
    assert fn("Personal & Family Paperwork", "")
    assert fn("", "some_bank_statement.pdf")
    # doctrine / identity / creative corpus must be allowed
    assert not fn("ORACLE & SOV1", "sov1_manifesto.txt")
    assert not fn("Legacy.GI", "indistinguishability_theorem.txt")
    assert not fn("RenderedReality", "rendered_reality_book.txt")
    assert not fn("Drakin & Ellie (Fiction)", "drakin.txt")


def test_corpus_excerpt_is_bounded_receipted_and_not_private():
    import oracle_server as srv

    if not srv._SELF_PROMPT_EXCERPT_MANIFEST.exists():
        return  # corpus not extracted on this machine; nothing to assert
    # sample several rotations; none may be a private record
    for seed in ("a", "b", "c", "seed", "sov1", "rendered"):
        exc = srv._self_prompt_corpus_excerpt(seed, [])
        if exc is None:
            continue
        assert exc["excerpt_chars"] <= srv._SELF_PROMPT_EXCERPT_CHARS
        assert exc["extracted_path"]                      # receipt: where from
        assert exc["promotion_status"] == "not_promoted"  # never auto-promoted
        assert exc["excerpt"].strip()
        assert not srv._self_prompt_topic_is_private(
            exc["topic"], exc["extracted_path"]
        ), f"private record leaked into reading pool: {exc['source_name']}"
