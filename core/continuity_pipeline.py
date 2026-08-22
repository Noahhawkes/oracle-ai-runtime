"""
core/continuity_pipeline.py — ORACLE Minimum End-to-End Continuity Loop

Wire existing modules together to produce the session continuity guarantee:

  session input
    -> classify_messages        (source_type per message)
    -> extract_candidates       (salience scoring via light_compression)
    -> assign_provenance        (builds full provenance record)
    -> evaluate_policy          (governance gate)
    -> write_durable_memory     (sqlite durable_facts)
    -> write_audit_chain        (structured audit record)

Rules enforced:
  - Fail closed if required provenance fields are absent (raises, does not silently continue)
  - Inferred facts must NOT be written as canonical without explicit approval
  - Every durable write produces an audit record
  - The test fixture session is three statements; only high-salience human_stated facts
    cross the write gate without explicit approval required

Usage:
  from continuity_pipeline import run_continuity_pipeline, ContinuityRuntime

  result = run_continuity_pipeline(session)
  runtime = ContinuityRuntime()
  recalled = runtime.wake_memory_search("dealer visit cadence")
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# ── Imported after path bootstrap ─────────────────────────────────────────────

from memory import (
    init_db,
    insert_durable_fact,
    search_durable_facts,
    append_audit_chain,
    get_audit_chain,
)
from light_compression import score_signal, FACT, CONSTRAINT, PATTERN
from governance import is_approval_required


# ── Constants ─────────────────────────────────────────────────────────────────

SALIENCE_THRESHOLD = 0.30        # below this: discard
INFERRED_AUTO_APPROVE = False    # inferred facts never auto-promoted to canonical

# ── Classification ────────────────────────────────────────────────────────────

def classify_source_type(message: dict) -> str:
    """
    Classify a message's source_type from speaker and content.

    Rules:
      - Any human speaking (Noah, a generic "user"/"human" placeholder, or a
        named human like "Ashley") → "human_stated"
      - Oracle speaking with hedge words → "inferred"
      - Oracle speaking factually → "generated"

    This decides *what kind of claim* the text is (a human statement vs. a
    model inference), not *who* said it. Identity is resolved separately by
    `resolve_speaker_identity` — do not conflate the two (Issue #16).

    Historical bug (Issue #16, site B): this used to only recognize the
    literal strings "noah"/"user"/"human" as human speech. A real name like
    "Ashley" fell through to the Oracle-inference branch below and got
    misclassified as AI-generated content — which then made her statement
    ineligible for the human-stated salience override and let it be
    silently discarded. Any non-Oracle speaker is a human statement.
    """
    speaker = str(message.get("speaker", "")).strip().lower()
    text = str(message.get("text", "")).lower()

    if speaker not in ("oracle", "assistant", "ai"):
        return "human_stated"

    # Model inference markers
    inference_markers = (
        "probably", "likely", "might", "may", "seems", "appears",
        "i think", "i believe", "could be", "perhaps", "arguably",
    )
    if any(marker in text for marker in inference_markers):
        return "inferred"

    return "generated"


# ── Speaker identity resolution (Issue #16: never collapse speaker into
#    Noah.Physical) ────────────────────────────────────────────────────────

# Generic role placeholders carry no identity signal by themselves — they
# only say "some human typed this," not "Noah typed this." A placeholder
# must resolve to UNKNOWN, never be silently upgraded to the account owner.
_GENERIC_HUMAN_PLACEHOLDERS = {"user", "human"}


def resolve_speaker_identity(message: dict) -> dict:
    """
    Resolve who actually produced this turn, independent of source_type.

    Governing rule (Issue #16 — cross-human provenance integrity): never
    assume account_owner == speaker, submitter == author, or that a generic
    "user"/"human" role means Noah. Ashley, a coworker, a pasted AI reply,
    or an unidentified human must stay distinguishable from Noah.

      - "" / "user" / "human"  -> speaker_id UNKNOWN (no identity given)
      - "noah" (any case)      -> speaker_id "Noah.Physical" (explicit claim)
      - anything else          -> preserved verbatim (e.g. "Ashley", "ChatGPT")

    `author_id` / `submitter_id` default to the resolved speaker but can be
    set independently on the message (e.g. Noah submitting text authored by
    an external AI). `account_owner_id` is the runtime's account owner — it
    is tracked separately from speaker/author/submitter and must never be
    used to infer either.
    """
    raw_speaker = str(message.get("speaker", "")).strip()
    lowered = raw_speaker.lower()
    if not raw_speaker or lowered in _GENERIC_HUMAN_PLACEHOLDERS:
        speaker_id = "UNKNOWN"
    elif lowered == "noah":
        speaker_id = "Noah.Physical"
    else:
        speaker_id = raw_speaker

    author_id = str(message.get("author_id", "")).strip() or speaker_id
    submitter_id = str(message.get("submitter_id", "")).strip() or speaker_id

    return {
        "speaker_id": speaker_id,
        "author_id": author_id,
        "submitter_id": submitter_id,
        "account_owner_id": "Noah.Physical",
        "provenance_note": (
            "account_owner_id identifies the runtime owner and is never "
            "assumed to be the speaker/author/submitter; unresolved humans "
            "stay UNKNOWN rather than being silently attributed to Noah."
        ),
    }


# ── Salience extraction ───────────────────────────────────────────────────────

def extract_candidates(session: list[dict], session_id: str) -> list[dict]:
    """
    Score each message. Return candidate records for messages above threshold.
    Each candidate carries:
      - text
      - source_type
      - score
      - transformation_history so far
    """
    candidates = []
    for i, msg in enumerate(session):
        text = str(msg.get("text", "")).strip()
        if not text:
            continue

        source_type = classify_source_type(msg)
        identity = resolve_speaker_identity(msg)
        score, relevance, emo, proj, sensitivity, noise = score_signal(
            text, memory_type=FACT, source="conversation"
        )

        transformation_history = [
            {
                "step": "source_classification",
                "source_type": source_type,
            },
            {
                "step": "speaker_identity_resolved",
                "speaker_id": identity["speaker_id"],
                "author_id": identity["author_id"],
                "submitter_id": identity["submitter_id"],
            },
            {
                "step": "salience_scoring",
                "score": round(score, 3),
                "relevance": round(relevance, 3),
                "emotional_weight": round(emo, 3),
                "project_value": round(proj, 3),
                "sensitivity": round(sensitivity, 3),
                "noise": round(noise, 3),
            },
        ]

        # Human-stated facts with substantive content are always candidates —
        # the keyword scorer is tuned for ORACLE project terms and will score
        # 0 for general statements from Noah. Length > 5 words is the proxy
        # for "substantive" without requiring an LLM.
        word_count = len(text.split())
        human_stated_override = (
            source_type == "human_stated" and word_count > 5
        )

        if score < SALIENCE_THRESHOLD and not human_stated_override:
            transformation_history.append({"step": "discarded", "reason": "below_salience_threshold"})
            candidates.append({
                "text": text,
                "source_type": source_type,
                "identity": identity,
                "score": score,
                "discarded": True,
                "transformation_history": transformation_history,
                "message_index": i,
                "session_id": session_id,
            })
            continue

        if human_stated_override and score < SALIENCE_THRESHOLD:
            # Assign a baseline score proportional to word count
            score = min(0.5, 0.05 * word_count)
            transformation_history.append({
                "step": "human_stated_override",
                "reason": "explicit_human_statement_always_candidate",
                "adjusted_score": round(score, 3),
            })

        candidates.append({
            "text": text,
            "source_type": source_type,
            "identity": identity,
            "score": score,
            "discarded": False,
            "transformation_history": transformation_history,
            "message_index": i,
            "session_id": session_id,
        })

    return candidates


# ── Provenance assignment ─────────────────────────────────────────────────────

def assign_provenance(candidate: dict) -> dict:
    """
    Build a complete provenance record for a candidate.

    Rules:
      - human_stated facts get canonical_status="accepted", approval_status="auto_approved"
      - inferred facts get canonical_status="staged", approval_status="pending"
        (inferred must never be written as canonical without explicit approval)
      - generated facts get canonical_status="staged", approval_status="pending"
    """
    source_type = candidate["source_type"]
    now = datetime.now(timezone.utc).isoformat()
    # Falls back to a fresh UNKNOWN resolution for candidates built before
    # identity resolution existed (e.g. hand-built dicts in older callers).
    identity = candidate.get("identity") or resolve_speaker_identity(candidate)

    if source_type == "human_stated":
        canonical_status = "accepted"
        approval_status = "auto_approved"
    else:
        # inferred and generated: never auto-promoted
        canonical_status = "staged"
        approval_status = "pending"

    transformation_history = list(candidate.get("transformation_history", []))
    transformation_history.append({
        "step": "provenance_assigned",
        "canonical_status": canonical_status,
        "approval_status": approval_status,
        "speaker_id": identity["speaker_id"],
    })

    provenance = {
        "source_type": source_type,
        "source_id": candidate["session_id"],
        "speaker_id": identity["speaker_id"],
        "author_id": identity["author_id"],
        "submitter_id": identity["submitter_id"],
        "account_owner_id": identity["account_owner_id"],
        "provenance_note": identity["provenance_note"],
        "observed_at": now,
        "confidence": min(1.0, max(0.0, candidate["score"] * 1.5))
        if source_type == "human_stated"
        else min(1.0, max(0.0, candidate["score"])),
        "transformation_history": transformation_history,
        "canonical_status": canonical_status,
        "approval_status": approval_status,
    }

    return provenance


# ── Governance evaluation ─────────────────────────────────────────────────────

def evaluate_policy(candidate: dict, provenance: dict) -> dict:
    """
    Apply governance policy. Returns policy_result dict with:
      - write_allowed: bool
      - reason: str
    """
    # Governance.is_approval_required() is True by default
    approval_required = is_approval_required()

    source_type = provenance["source_type"]
    approval_status = provenance["approval_status"]
    canonical_status = provenance["canonical_status"]

    # Inferred/generated facts must never be written as canonical without explicit approval
    if source_type in ("inferred", "generated"):
        return {
            "write_allowed": True,   # write is allowed but as staged/pending
            "reason": f"staged_{source_type}_pending_approval",
            "canonical_status": "staged",
            "approval_status": "pending",
        }

    # human_stated: allow if approval not required, or if already auto_approved
    if source_type == "human_stated":
        if approval_required and approval_status != "auto_approved":
            return {
                "write_allowed": False,
                "reason": "approval_required_by_governance",
                "canonical_status": "staged",
                "approval_status": "pending",
            }
        return {
            "write_allowed": True,
            "reason": "human_stated_auto_approved",
            "canonical_status": canonical_status,
            "approval_status": approval_status,
        }

    return {
        "write_allowed": False,
        "reason": "unknown_source_type",
        "canonical_status": "staged",
        "approval_status": "pending",
    }


# ── Durable write ─────────────────────────────────────────────────────────────

def write_durable_memory(
    fact_text: str,
    provenance: dict,
    policy_result: dict,
    session_id: str,
) -> dict:
    """
    Write a durable fact with full provenance to the database.
    Always writes an audit entry — even for rejected facts.

    Returns the written record or a rejection record.
    """
    # Update provenance with policy result
    final_provenance = dict(provenance)
    final_provenance["canonical_status"] = policy_result.get("canonical_status", provenance["canonical_status"])
    final_provenance["approval_status"] = policy_result.get("approval_status", provenance["approval_status"])

    # Add policy step to transformation history
    history = list(final_provenance.get("transformation_history", []))
    history.append({
        "step": "policy_evaluated",
        "write_allowed": policy_result["write_allowed"],
        "reason": policy_result["reason"],
    })
    final_provenance["transformation_history"] = history

    if not policy_result["write_allowed"]:
        audit_detail = {
            "fact_text": fact_text[:200],
            "reason": policy_result["reason"],
            "source_type": final_provenance["source_type"],
        }
        append_audit_chain(session_id, "memory_write_blocked", audit_detail)
        return {
            "status": "blocked",
            "reason": policy_result["reason"],
            "fact_text": fact_text,
            "provenance": final_provenance,
        }

    # Fail closed: validate provenance before writing
    from memory import _validate_provenance
    _validate_provenance(final_provenance)

    history.append({"step": "memory_written"})
    final_provenance["transformation_history"] = history

    row_id = insert_durable_fact(fact_text, final_provenance)

    append_audit_chain(session_id, "memory_written", {
        "row_id": row_id,
        "fact_text": fact_text[:200],
        "source_type": final_provenance["source_type"],
        "canonical_status": final_provenance["canonical_status"],
        "approval_status": final_provenance["approval_status"],
    })

    return {
        "status": "written",
        "row_id": row_id,
        "fact_text": fact_text,
        "provenance": final_provenance,
    }


# ── Pipeline orchestrator ─────────────────────────────────────────────────────

def run_continuity_pipeline(
    session: list[dict],
    session_id: str | None = None,
    db_path: "Path | None" = None,
) -> dict:
    """
    Run the full continuity loop on a session (list of message dicts).
    Each message dict: {"speaker": str, "text": str}

    Returns a result dict with:
      - session_id
      - candidates: all scored messages (including discarded)
      - written: records that were written as durable facts
      - staged: records that need approval
      - discarded: records below salience threshold
      - audit_chain: ordered list of audit events
    """
    if db_path is not None:
        # Allow test isolation: override DB_PATH in memory module
        import memory as _mem
        _mem.DB_PATH = db_path

    init_db()

    session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"

    # 1. Audit: session received
    append_audit_chain(session_id, "session_received", {"message_count": len(session)})

    # 2. Score and extract candidates
    candidates = extract_candidates(session, session_id)
    append_audit_chain(session_id, "candidate_extracted", {
        "total": len(candidates),
        "above_threshold": sum(1 for c in candidates if not c.get("discarded")),
    })

    written_records = []
    staged_records = []
    discarded_records = []

    for candidate in candidates:
        if candidate.get("discarded"):
            discarded_records.append(candidate)
            continue

        # 3. Assign provenance
        provenance = assign_provenance(candidate)
        append_audit_chain(session_id, "provenance_assigned", {
            "source_type": provenance["source_type"],
            "speaker_id": provenance["speaker_id"],
            "canonical_status": provenance["canonical_status"],
            "approval_status": provenance["approval_status"],
            "confidence": provenance["confidence"],
        })

        # 4. Evaluate policy
        policy_result = evaluate_policy(candidate, provenance)

        # 5. Write (or stage)
        write_result = write_durable_memory(
            candidate["text"], provenance, policy_result, session_id
        )

        if write_result["status"] == "written":
            written_records.append(write_result)
        else:
            staged_records.append(write_result)

    # 6. Final audit entry
    append_audit_chain(session_id, "pipeline_complete", {
        "written": len(written_records),
        "staged": len(staged_records),
        "discarded": len(discarded_records),
    })

    chain = get_audit_chain(session_id)

    return {
        "session_id": session_id,
        "candidates": candidates,
        "written": written_records,
        "staged": staged_records,
        "discarded": discarded_records,
        "audit_chain": chain,
    }


# ── Clean runtime (for reload tests) ─────────────────────────────────────────

class ContinuityRuntime:
    """
    A minimal runtime that loads durable memory on construction.
    Used to verify that a clean reload can recall durable facts.
    """

    def __init__(self, db_path: "Path | None" = None) -> None:
        if db_path is not None:
            import memory as _mem
            _mem.DB_PATH = db_path
        init_db()

    def wake_memory_search(self, query: str) -> dict | None:
        """
        Search durable facts for a query.
        Returns the first matching accepted fact, or None.
        """
        rows = search_durable_facts(query, limit=10)
        # Prefer accepted/auto_approved facts
        for row in rows:
            if row.get("canonical_status") == "accepted":
                return {
                    "fact_text": row["fact_text"],
                    "source_type": row["source_type"],
                    "canonical_status": row["canonical_status"],
                    "approval_status": row["approval_status"],
                    "confidence": row["confidence"],
                }
        # Fall back to any match
        return rows[0] if rows else None
