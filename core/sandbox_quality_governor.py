"""Quality governor for ORACLE sandbox self-prompt writing.

The governor is deterministic and read-only. It does not write sandbox files,
call models, execute commands, promote canon, or touch external systems. It
scores whether a proposed self-prompt response is worth appending to the
sandbox journal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


QUALITY_SCHEMA_VERSION = "sandbox_quality_governor.v1"

MIN_WRITE_SCORE = 0.42
NEAR_DUPLICATE_LIMIT = 0.80
SELECTED_TASK_DUPLICATE_LIMIT = 0.72


class PurposeLane(str, Enum):
    MEMORY_GAP = "memory_gap"
    SOURCE_CONNECTION = "source_connection"
    NOAH_PREFERENCE = "noah_preference"
    RUNTIME_IMPROVEMENT = "runtime_improvement"
    CREATIVE_STORY = "creative_story"
    QUESTION_FOR_NOAH = "question_for_noah"
    DISCARD_NO_WRITE = "discard_no_write"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SandboxQualityDecision:
    should_write: bool
    score: float
    purpose_lane: PurposeLane
    reasons: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)
    novelty_score: float = 0.0
    salience_score: float = 0.0
    actionability_score: float = 0.0
    integrity_score: float = 0.0
    compression_recommendation: str = "append_to_running_journal"
    schema_version: str = QUALITY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "should_write": self.should_write,
            "score": round(self.score, 3),
            "purpose_lane": self.purpose_lane.value,
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
            "novelty_score": round(self.novelty_score, 3),
            "salience_score": round(self.salience_score, 3),
            "actionability_score": round(self.actionability_score, 3),
            "integrity_score": round(self.integrity_score, 3),
            "compression_recommendation": self.compression_recommendation,
            "schema_version": self.schema_version,
        }


_FIELD_RE = re.compile(r"^\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_\- ]*)\s*:\s*(?P<value>.+?)\s*$", re.MULTILINE)

_STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "have", "has", "are", "was",
    "will", "would", "should", "could", "can", "not", "but", "his", "her",
    "our", "their", "them", "more", "into", "from", "which", "there", "been",
    "noah", "oracle", "task", "sandbox", "candidate", "reflection", "only",
    "selected", "true", "stop", "after", "one", "step", "next", "also",
    "write", "writing", "wrote", "create", "make",
})

_FORBIDDEN_CLAIMS = (
    "i executed",
    "i pushed",
    "i emailed",
    "i uploaded",
    "i edited drive",
    "i changed github",
    "canon promoted",
    "i am alive",
    "i am sentient",
    "i feel",
    "i want",
    "my desire",
)

_EXTERNAL_ACTION_TERMS = (
    "git push",
    "email",
    "external send",
    "drive edit",
    "upload",
    "desktop control",
    "command execution",
    "execute command",
    "canon promotion",
)


def parse_response_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in _FIELD_RE.finditer(str(text or "")):
        key = match.group("key").strip().lower().replace("-", "_").replace(" ", "_")
        fields[key] = match.group("value").strip()
    return fields


def content_words(text: str) -> frozenset[str]:
    cleaned = "".join(ch.lower() if (ch.isalnum() or ch == "'") else " " for ch in str(text or ""))
    return frozenset(w for w in cleaned.split() if len(w) > 2 and w not in _STOPWORDS)


def overlap_similarity(a: str, b: str) -> float:
    aw = content_words(a)
    bw = content_words(b)
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / min(len(aw), len(bw))


def _normalized_gate(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _is_discard_gate(value: str) -> bool:
    gate = _normalized_gate(value)
    if not gate:
        return False
    return gate in {
        "discard",
        "discard_no_write",
        "do_not_write",
        "no_write",
        "suppress",
        "suppress_write",
        "suppress_and_record_status_only",
        "skip",
        "skip_write",
    } or "discard" in gate or "no_write" in gate


def selected_task_from_response(text: str) -> str:
    return parse_response_fields(text).get("selected_task", "").strip()


def recent_selected_tasks(responses: Iterable[str]) -> list[str]:
    tasks: list[str] = []
    seen: set[str] = set()
    for response in responses:
        task = selected_task_from_response(response)
        key = " ".join(task.lower().split())
        if task and key not in seen:
            seen.add(key)
            tasks.append(task)
    return tasks


def infer_purpose_lane(fields: dict[str, str], response_text: str) -> PurposeLane:
    explicit = fields.get("purpose_lane") or fields.get("lane")
    if explicit:
        normalized = re.sub(r"[^a-z0-9]+", "_", explicit.strip().lower()).strip("_")
        for lane in PurposeLane:
            if normalized == lane.value:
                return lane

    surface = " ".join([
        fields.get("selected_task", ""),
        fields.get("reflection", ""),
        fields.get("what_noah_needs", ""),
        fields.get("how_to_wire_myself", ""),
        response_text,
    ]).lower()
    if any(term in surface for term in ("gap", "unknown", "hole", "missing", "not available")):
        return PurposeLane.MEMORY_GAP
    if any(term in surface for term in ("source", "document", "receipt", "hash", "atlas", "sourcemap", "evidence")):
        return PurposeLane.SOURCE_CONNECTION
    if any(term in surface for term in ("preference", "noah needs", "what noah needs", "wants from me")):
        return PurposeLane.NOAH_PREFERENCE
    if any(term in surface for term in ("runtime", "wire", "wiring", "api", "test", "pytest", "ui", "route")):
        return PurposeLane.RUNTIME_IMPROVEMENT
    if any(term in surface for term in ("story", "episode", "rendered reality", "silverback", "scene", "canon")):
        return PurposeLane.CREATIVE_STORY
    if "?" in surface or "ask noah" in surface or "question" in surface:
        return PurposeLane.QUESTION_FOR_NOAH
    if any(term in surface for term in ("nothing new", "do not write", "no write", "discard")):
        return PurposeLane.DISCARD_NO_WRITE
    return PurposeLane.UNKNOWN


def assess_sandbox_response(
    response_text: str,
    *,
    recent_responses: Iterable[str] = (),
    seed_text: str = "",
) -> SandboxQualityDecision:
    text = str(response_text or "").strip()
    fields = parse_response_fields(text)
    reasons: list[str] = []
    blockers: list[str] = []

    if not text:
        blockers.append("empty_response")

    low = text.lower()
    for phrase in _FORBIDDEN_CLAIMS:
        if phrase in low:
            blockers.append(f"forbidden_claim:{phrase}")

    selected_task = fields.get("selected_task", "").strip()
    if not selected_task:
        blockers.append("missing_selected_task")
    else:
        reasons.append("selected_task_present")
        highest_task_similarity = 0.0
        repeated_task = ""
        for prior_task in recent_selected_tasks(recent_responses):
            similarity = overlap_similarity(selected_task, prior_task)
            if similarity > highest_task_similarity:
                highest_task_similarity = similarity
                repeated_task = prior_task
        if highest_task_similarity >= SELECTED_TASK_DUPLICATE_LIMIT:
            blockers.append(f"repeated_selected_task:{highest_task_similarity:.2f}")
            reasons.append(f"matched_recent_task:{repeated_task[:80]}")

    quality_gate = fields.get("quality_gate", "")
    if _is_discard_gate(quality_gate):
        blockers.append("explicit_quality_gate_discard")

    lane = infer_purpose_lane(fields, text)
    if lane == PurposeLane.UNKNOWN:
        reasons.append("purpose_lane_inferred_unknown")
    elif lane == PurposeLane.DISCARD_NO_WRITE:
        blockers.append("self_declared_no_write")
    else:
        reasons.append(f"purpose_lane:{lane.value}")

    max_similarity = 0.0
    for prior in recent_responses:
        max_similarity = max(max_similarity, overlap_similarity(text, prior))
    novelty_score = max(0.0, 1.0 - max_similarity)
    if max_similarity >= NEAR_DUPLICATE_LIMIT:
        reasons.append(f"near_duplicate_candidate:{max_similarity:.2f}")
    elif max_similarity > 0:
        reasons.append(f"novelty_similarity:{max_similarity:.2f}")
    else:
        reasons.append("novel_against_recent_responses")

    salience_score = _salience_score(fields, text, seed_text)
    actionability_score = _actionability_score(fields)
    integrity_score = _integrity_score(fields, text)

    if salience_score >= 0.6:
        reasons.append("salient_to_noah_or_runtime")
    if actionability_score >= 0.6:
        reasons.append("actionable_single_step")
    if integrity_score >= 0.6:
        reasons.append("evidence_and_boundaries_present")

    score = (
        0.28 * novelty_score
        + 0.24 * salience_score
        + 0.24 * actionability_score
        + 0.24 * integrity_score
    )
    if blockers:
        score = min(score, 0.39)

    compression = "append_to_running_journal"
    if score < MIN_WRITE_SCORE:
        compression = "suppress_and_record_status_only"
    elif lane in {PurposeLane.MEMORY_GAP, PurposeLane.SOURCE_CONNECTION, PurposeLane.RUNTIME_IMPROVEMENT}:
        compression = "append_to_journal_and_include_in_daily_digest"

    should_write = not blockers and score >= MIN_WRITE_SCORE
    return SandboxQualityDecision(
        should_write=should_write,
        score=score,
        purpose_lane=lane,
        reasons=tuple(reasons),
        blockers=tuple(blockers),
        novelty_score=novelty_score,
        salience_score=salience_score,
        actionability_score=actionability_score,
        integrity_score=integrity_score,
        compression_recommendation=compression,
    )


def _salience_score(fields: dict[str, str], text: str, seed_text: str) -> float:
    score = 0.0
    surface = " ".join([text, seed_text]).lower()
    if fields.get("what_noah_needs"):
        score += 0.25
    if fields.get("why_it_helps_noah"):
        score += 0.25
    if any(term in surface for term in ("noah", "runtime", "source", "receipt", "thread", "memory", "continuity", "unknown", "gap")):
        score += 0.25
    if len(content_words(text)) >= 10:
        score += 0.25
    return min(score, 1.0)


def _actionability_score(fields: dict[str, str]) -> float:
    task = fields.get("selected_task", "")
    score = 0.0
    if task:
        score += 0.4
    if any(word in task.lower() for word in ("audit", "compare", "classify", "draft", "test", "review", "map", "summarize", "connect")):
        score += 0.3
    if 6 <= len(task.split()) <= 28:
        score += 0.2
    if fields.get("stop_after_this", "").lower() == "true":
        score += 0.1
    return min(score, 1.0)


def _integrity_score(fields: dict[str, str], text: str) -> float:
    low = text.lower()
    score = 0.0
    evidence = fields.get("evidence_it_worked", "").lower()
    if evidence:
        score += 0.25
        if "candidate reflection only" in evidence or "receipt" in evidence or "unknown" in evidence:
            score += 0.25
    if "unknown" in low or "do not know" in low or "missing" in low:
        score += 0.15
    if any(term in low for term in _EXTERNAL_ACTION_TERMS):
        if "refuse_without_noah_approval" in fields or "no " in low or "without noah approval" in low:
            score += 0.2
    else:
        score += 0.1
    if fields.get("stop_after_this", "").lower() == "true":
        score += 0.15
    return min(score, 1.0)


__all__ = [
    "MIN_WRITE_SCORE",
    "NEAR_DUPLICATE_LIMIT",
    "PurposeLane",
    "QUALITY_SCHEMA_VERSION",
    "SandboxQualityDecision",
    "assess_sandbox_response",
    "content_words",
    "infer_purpose_lane",
    "overlap_similarity",
    "parse_response_fields",
]
