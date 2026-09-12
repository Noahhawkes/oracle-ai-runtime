"""Deterministic source resolution for ORACLE recall.

This module is not a memory engine and not a crawler. It is a small
orchestrator over existing source surfaces. Its job is to stop ORACLE from
treating "not retrieved" as "does not exist" by making source priority,
availability, conflicts, and provenance explicit before a natural answer is
formed elsewhere.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

MEMORY_DIR = RUNTIME_ROOT / "Memory"
RECEIPT_FILE = MEMORY_DIR / "source_resolution_receipts.jsonl"
REMEMBER_ME_DIR = MEMORY_DIR / "remember_me"
REMEMBER_ME_INDEX = REMEMBER_ME_DIR / "index.json"

RESOLVED = "RESOLVED"
PARTIAL = "PARTIAL"
CONFLICT = "CONFLICT"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
NOT_FOUND = "NOT_FOUND"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

PERSONAL_IDENTITY = "personal_identity"
REPOSITORY_SOFTWARE = "repository_software"
HISTORICAL_LIFE_EVENT = "historical_life_event"
EDUCATION_RECORD = "education_record"
RUNTIME_STATE = "runtime_state"
RAW_TRANSCRIPT = "raw_transcript"
GENERAL_PROJECT = "general_project"

DOMAIN_SOURCE_PRIORITY: dict[str, tuple[str, ...]] = {
    PERSONAL_IDENTITY: (
        "explicit_current_human_approval",
        "primary_legal_identity_artifact",
        "governed_verified_identity_record",
        "t1_verified_continuity_signal",
        "authored_primary_artifact",
        "structured_profile_source",
        "journal_source_narrative",
        "later_summary",
        "model_inference",
    ),
    REPOSITORY_SOFTWARE: (
        "live_runtime_receipt",
        "current_filesystem_repository_state",
        "current_commit_test_evidence",
        "current_config",
        "implementation_documentation",
        "historical_receipt",
        "narrative_summary",
        "model_claim",
    ),
    HISTORICAL_LIFE_EVENT: (
        "native_primary_artifact",
        "contemporaneous_record",
        "explicit_current_human_approval",
        "governed_verified_identity_record",
        "later_first_person_recollection",
        "secondary_summary",
        "model_inference",
    ),
    EDUCATION_RECORD: (
        "primary_education_artifact",
        "transcript_or_diploma",
        "explicit_current_human_approval",
        "governed_verified_identity_record",
        "structured_profile_source",
        "later_summary",
        "model_inference",
    ),
    RUNTIME_STATE: (
        "live_runtime_receipt",
        "current_filesystem_repository_state",
        "current_config",
        "historical_receipt",
        "narrative_summary",
        "model_claim",
    ),
    RAW_TRANSCRIPT: (
        "raw_transcript",
        "thread_ingest_record",
        "quote_corpus_excerpt",
        "conversation_summary",
        "model_inference",
    ),
    GENERAL_PROJECT: (
        "live_runtime_receipt",
        "current_filesystem_repository_state",
        "implementation_documentation",
        "governed_verified_identity_record",
        "authored_primary_artifact",
        "document_atlas_metadata",
        "file_recall_metadata",
        "thread_ingest_record",
        "later_summary",
        "model_inference",
    ),
}

HIGH_AUTHORITY_CLASSES = {
    "explicit_current_human_approval",
    "primary_legal_identity_artifact",
    "governed_verified_identity_record",
    "native_primary_artifact",
    "contemporaneous_record",
    "primary_education_artifact",
    "transcript_or_diploma",
    "live_runtime_receipt",
    "current_filesystem_repository_state",
    "current_commit_test_evidence",
    "raw_transcript",
    "thread_ingest_record",
    "quote_corpus_excerpt",
}

MODEL_CLASSES = {"model_inference", "model_claim"}
PRIVATE_SCOPES = {"PRIVATE", "PRIVATE_ORACLE", "PRIVATE_IDENTITY", "private", "private_identity"}


@dataclass(frozen=True)
class SourceCandidate:
    field: str
    value: Any
    source_class: str
    source_id: str
    source_label: str = ""
    precision: str = "exact"
    authority: str = ""
    confidence: str = ""
    evidence_date: str = ""
    source_path: str | None = None
    privacy_scope: str = "PRIVATE_ORACLE"
    provenance_ref: str = ""
    note: str = ""
    claim_status: str = "candidate"

    @classmethod
    def from_any(cls, value: "SourceCandidate | dict[str, Any]") -> "SourceCandidate":
        if isinstance(value, cls):
            return value
        return cls(
            field=str(value.get("field") or ""),
            value=value.get("value"),
            source_class=str(value.get("source_class") or ""),
            source_id=str(value.get("source_id") or value.get("id") or ""),
            source_label=str(value.get("source_label") or value.get("label") or ""),
            precision=str(value.get("precision") or "exact"),
            authority=str(value.get("authority") or ""),
            confidence=str(value.get("confidence") or ""),
            evidence_date=str(value.get("evidence_date") or value.get("date") or ""),
            source_path=value.get("source_path") or value.get("path"),
            privacy_scope=str(value.get("privacy_scope") or "PRIVATE_ORACLE"),
            provenance_ref=str(value.get("provenance_ref") or value.get("source") or ""),
            note=str(value.get("note") or ""),
            claim_status=str(value.get("claim_status") or "candidate"),
        )

    def to_dict(self, *, public: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if public and self.privacy_scope in PRIVATE_SCOPES:
            data["value"] = "REDACTED_PRIVATE"
            data["source_path"] = None
            data["provenance_ref"] = "REDACTED_PRIVATE"
        return data


@dataclass
class ResolutionResult:
    query: str
    fact_domain: str
    field: str
    status: str
    searched_sources: list[dict[str, Any]]
    unavailable_sources: list[dict[str, Any]]
    candidate_claims: list[SourceCandidate] = field(default_factory=list)
    selected_claim: SourceCandidate | None = None
    selection_reason: str = ""
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provenance_refs: list[str] = field(default_factory=list)
    receipt_path: str | None = None

    def to_dict(self, *, public: bool = False) -> dict[str, Any]:
        return {
            "query": self.query,
            "fact_domain": self.fact_domain,
            "field": self.field,
            "status": self.status,
            "searched_sources": self.searched_sources,
            "unavailable_sources": self.unavailable_sources,
            "candidate_claims": [item.to_dict(public=public) for item in self.candidate_claims],
            "selected_claim": self.selected_claim.to_dict(public=public) if self.selected_claim else None,
            "selection_reason": self.selection_reason,
            "conflicts": self.conflicts if not public else _redact_conflicts(self.conflicts),
            "timestamp": self.timestamp,
            "provenance_refs": [] if public else self.provenance_refs,
            "receipt_path": None if public else self.receipt_path,
        }


def _redact_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    redacted: list[dict[str, Any]] = []
    for item in conflicts:
        copy = dict(item)
        if copy.get("privacy_scope") in PRIVATE_SCOPES:
            copy["value"] = "REDACTED_PRIVATE"
            copy["source_path"] = None
        redacted.append(copy)
    return redacted


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _receipt_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")).hexdigest()


def classify_fact_domain(query: str) -> str:
    text = str(query or "").lower()
    if re.search(r"\b(birthday|birth date|date of birth|dob|born|age|how old)\b", text):
        return PERSONAL_IDENTITY
    if re.search(r"\b(did i say|quote me|raw transcript|thread said|conversation)\b", text):
        return RAW_TRANSCRIPT
    if re.search(r"\b(graduat\w*|diploma|transcript|degree|mba|school|education)\b", text):
        return EDUCATION_RECORD
    if re.search(r"\b(accident|injury|happened in 20\d\d|life event|father died|death)\b", text):
        return HISTORICAL_LIFE_EVENT
    if re.search(r"\b(commit|branch|head|git|gateway|built|tests?|repository|repo)\b", text):
        return REPOSITORY_SOFTWARE
    if re.search(r"\b(runtime|localhost|port|running|server|mode|oracle state)\b", text):
        return RUNTIME_STATE
    return GENERAL_PROJECT


def infer_field(query: str, domain: str | None = None) -> str:
    text = str(query or "").lower()
    if re.search(r"\b(birthday|birth date|date of birth|dob|born|age|how old)\b", text):
        return "date_of_birth"
    if re.search(r"\b(did i say|quote me|raw transcript|thread said|conversation)\b", text):
        return "raw_transcript_claim"
    if re.search(r"\b(graduat\w*|diploma|transcript|degree|mba|school|education)\b", text):
        return "education_date"
    if re.search(r"\b(accident|injury|happened in 20\d\d|life event)\b", text):
        return "historical_life_event"
    if re.search(r"\b(commit|branch|head|git)\b", text):
        return "repository_head"
    if re.search(r"\b(runtime|localhost|port|running|server|mode)\b", text):
        return "runtime_state"
    return domain or GENERAL_PROJECT


def required_precision(query: str, field_name: str) -> str:
    text = str(query or "").lower()
    if field_name == "date_of_birth" and re.search(r"\b(exact|birthday|birth date|date of birth|dob|how old|age)\b", text):
        return "exact"
    if "date" in field_name and "year" not in text:
        return "exact"
    return "any"


def source_plan(domain: str) -> tuple[str, ...]:
    return DOMAIN_SOURCE_PRIORITY.get(domain, DOMAIN_SOURCE_PRIORITY[GENERAL_PROJECT])


def source_rank(domain: str, source_class: str) -> int:
    plan = source_plan(domain)
    try:
        return plan.index(source_class)
    except ValueError:
        return len(plan) + 100


def _normalize_unavailable(unavailable_sources: list[Any] | dict[str, str] | None) -> list[dict[str, Any]]:
    if not unavailable_sources:
        return []
    if isinstance(unavailable_sources, dict):
        return [{"source_class": key, "reason": str(value)} for key, value in unavailable_sources.items()]
    out = []
    for item in unavailable_sources:
        if isinstance(item, str):
            out.append({"source_class": item, "reason": "unavailable"})
        elif isinstance(item, dict):
            out.append({"source_class": str(item.get("source_class") or item.get("source") or ""), "reason": str(item.get("reason") or "unavailable")})
    return [item for item in out if item.get("source_class")]


def _field_matches(candidate: SourceCandidate, field_name: str) -> bool:
    return not field_name or candidate.field == field_name


def _meets_precision(candidate: SourceCandidate, needed: str) -> bool:
    if needed == "any":
        return True
    return candidate.precision == needed


def _is_model_only(candidates: list[SourceCandidate]) -> bool:
    return bool(candidates) and all(item.source_class in MODEL_CLASSES for item in candidates)


def _conflict_rows(candidates: list[SourceCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "field": item.field,
            "value": item.value,
            "source_class": item.source_class,
            "source_id": item.source_id,
            "source_label": item.source_label,
            "source_path": item.source_path,
            "authority": item.authority,
            "confidence": item.confidence,
            "date": item.evidence_date,
            "privacy_scope": item.privacy_scope,
        }
        for item in candidates
    ]


def resolve_fact(
    query: str,
    *,
    field: str | None = None,
    candidates: list[SourceCandidate | dict[str, Any]] | None = None,
    unavailable_sources: list[Any] | dict[str, str] | None = None,
    fact_domain: str | None = None,
    public: bool = False,
    write_receipt: bool = True,
) -> ResolutionResult:
    domain = fact_domain or classify_fact_domain(query)
    field_name = field or infer_field(query, domain)
    plan = source_plan(domain)
    unavailable = _normalize_unavailable(unavailable_sources)
    unavailable_by_class = {item["source_class"]: item for item in unavailable}
    claims = [SourceCandidate.from_any(item) for item in (candidates if candidates is not None else gather_candidates(query, field_name, domain))]
    matching = [item for item in claims if _field_matches(item, field_name)]

    searched_sources = []
    for source_class in plan:
        source_claims = [item for item in matching if item.source_class == source_class]
        searched_sources.append(
            {
                "source_class": source_class,
                "status": "unavailable" if source_class in unavailable_by_class else "searched",
                "candidate_count": len(source_claims),
            }
        )

    needed = required_precision(query, field_name)
    usable = [item for item in matching if item.value not in (None, "", "UNKNOWN")]
    precise = [item for item in usable if _meets_precision(item, needed)]
    provenance_refs = sorted({item.provenance_ref or item.source_id for item in usable if item.provenance_ref or item.source_id})

    status: str
    selected: SourceCandidate | None = None
    reason = ""
    conflicts: list[dict[str, Any]] = []

    if not usable:
        if unavailable:
            status = SOURCE_UNAVAILABLE
            reason = "No candidate claim was retrieved, and at least one relevant source class was unavailable."
        else:
            status = NOT_FOUND
            reason = "Relevant source classes were searched but produced no candidate claim."
    elif _is_model_only(usable):
        status = INSUFFICIENT_EVIDENCE
        reason = "Only model inference/model claim evidence was available; model output is not authoritative evidence."
    elif needed != "any" and not precise:
        best_partial = sorted(usable, key=lambda item: source_rank(domain, item.source_class))[0]
        selected = best_partial
        status = PARTIAL
        reason = f"Best retrieved evidence has precision={best_partial.precision}; required precision={needed}."
    else:
        pool = precise or usable
        ranked = sorted(pool, key=lambda item: (source_rank(domain, item.source_class), item.source_id))
        selected = ranked[0]
        selected_rank = source_rank(domain, selected.source_class)
        strong = [
            item for item in pool
            if item.source_class in HIGH_AUTHORITY_CLASSES
            and source_rank(domain, item.source_class) <= selected_rank + 1
        ]
        values = {json.dumps(item.value, sort_keys=True, default=str) for item in strong}
        if len(values) > 1:
            status = CONFLICT
            conflicts = _conflict_rows(strong)
            selected = None
            reason = "Two or more high-authority source classes disagree; Noah.Physical resolution is required."
        else:
            higher_unavailable = [
                item for item in unavailable
                if source_rank(domain, item["source_class"]) < selected_rank
            ]
            if higher_unavailable:
                status = PARTIAL
                reason = "A lower-authority claim was found, but a stronger relevant source class was unavailable."
            else:
                status = RESOLVED
                reason = f"Selected highest-priority available source class: {selected.source_class}."

    result = ResolutionResult(
        query=query,
        fact_domain=domain,
        field=field_name,
        status=status,
        searched_sources=searched_sources,
        unavailable_sources=unavailable,
        candidate_claims=matching,
        selected_claim=selected,
        selection_reason=reason,
        conflicts=conflicts,
        provenance_refs=provenance_refs,
    )
    if write_receipt:
        result.receipt_path = write_resolution_receipt(result, public=public)
    return result


def write_resolution_receipt(result: ResolutionResult, *, public: bool = False) -> str:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "receipt_kind": "source_resolution_receipt",
        "schema_version": "source_resolver.v1",
        "written_at": _now(),
        "result": result.to_dict(public=public),
        "boundary": {
            "read_only": True,
            "source_mutation": False,
            "external_send": False,
            "canon_promotion": False,
            "public_redaction_applied": bool(public),
        },
    }
    payload["receipt_sha256"] = _receipt_hash(payload)
    with RECEIPT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str) + "\n")
    return str(RECEIPT_FILE)


def _remember_me_records() -> list[dict[str, Any]]:
    try:
        index = json.loads(REMEMBER_ME_INDEX.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    records: list[dict[str, Any]] = []
    for rid, indexed_status in sorted(index.items()):
        path = REMEMBER_ME_DIR / f"{rid}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            data["_indexed_status"] = indexed_status
            data["_record_path"] = str(path.resolve())
            records.append(data)
    return records


def _identity_candidates_from_remember_me(field_name: str) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    for record in _remember_me_records():
        if record.get("status") != "approved" or record.get("_indexed_status") != "approved":
            continue
        assertion = record.get("identity_assertion")
        if isinstance(assertion, dict) and assertion.get("field") == field_name:
            candidates.append(
                SourceCandidate(
                    field=field_name,
                    value=assertion.get("value"),
                    source_class="governed_verified_identity_record",
                    source_id=str(record.get("id") or ""),
                    source_label=str(record.get("title") or ""),
                    precision=str(assertion.get("precision") or "exact"),
                    authority=str(assertion.get("authority") or record.get("decided_by") or ""),
                    confidence=str(assertion.get("verification_state") or record.get("confidence") or ""),
                    evidence_date=str(assertion.get("effective_date") or record.get("approved_at") or ""),
                    source_path=record.get("_record_path"),
                    privacy_scope=str(assertion.get("privacy_scope") or "PRIVATE_IDENTITY"),
                    provenance_ref=str(assertion.get("source") or record.get("source") or ""),
                    note=str(record.get("provenance_note") or ""),
                    claim_status="approved",
                )
            )
        if field_name == "date_of_birth" and "birth" in " ".join(record.get("tags") or []).lower():
            year = str(record.get("event_date") or "")
            if re.fullmatch(r"\d{4}", year):
                candidates.append(
                    SourceCandidate(
                        field=field_name,
                        value=year,
                        source_class="t1_verified_continuity_signal" if record.get("confidence") == "VERIFIED" else "structured_profile_source",
                        source_id=str(record.get("id") or ""),
                        source_label=str(record.get("title") or ""),
                        precision="year",
                        authority=str(record.get("decided_by") or ""),
                        confidence=str(record.get("confidence") or ""),
                        evidence_date=year,
                        source_path=record.get("_record_path"),
                        privacy_scope="PRIVATE_ORACLE",
                        provenance_ref=str(record.get("source") or ""),
                        note=str(record.get("provenance_note") or ""),
                        claim_status="approved",
                    )
                )
    return candidates


def _repository_candidates(field_name: str) -> list[SourceCandidate]:
    if field_name not in {"repository_head", "repository_software", REPOSITORY_SOFTWARE}:
        return []
    try:
        from git_state_reader import read_git_snapshot

        snap = read_git_snapshot(RUNTIME_ROOT)
    except Exception:
        return []
    if not snap.get("available"):
        return []
    return [
        SourceCandidate(
            field="repository_head",
            value=snap.get("head_sha") or snap.get("commit"),
            source_class="current_filesystem_repository_state",
            source_id="git_state_reader",
            source_label="Git HEAD file snapshot",
            precision="exact",
            authority="filesystem",
            confidence="VERIFIED",
            source_path=str(RUNTIME_ROOT / ".git"),
            privacy_scope="PRIVATE_ORACLE",
            provenance_ref="git_files_no_subprocess",
            note="Read from .git files without invoking git.exe.",
            claim_status="observed",
        )
    ]


def _runtime_candidates(field_name: str) -> list[SourceCandidate]:
    if field_name not in {"runtime_state", RUNTIME_STATE}:
        return []
    try:
        from operational_state import build_operational_state

        state = build_operational_state()
    except Exception:
        return []
    runtime = ((state.get("verified") or {}).get("runtime") or {})
    return [
        SourceCandidate(
            field="runtime_state",
            value={
                "runtime_status": runtime.get("runtime_status"),
                "runtime_port": runtime.get("runtime_port"),
                "mode": runtime.get("mode"),
                "session_id": runtime.get("session_id"),
            },
            source_class="live_runtime_receipt",
            source_id="operational_state",
            source_label="Operational state",
            precision="current",
            authority="runtime_probe",
            confidence="VERIFIED",
            privacy_scope="PRIVATE_ORACLE",
            provenance_ref="operational_state.build_operational_state",
            claim_status="observed",
        )
    ]


def _metadata_source_candidates(query: str, field_name: str) -> list[SourceCandidate]:
    """Use existing metadata surfaces as evidence pointers, not fact values."""

    candidates: list[SourceCandidate] = []
    if field_name == "date_of_birth":
        search_terms = ("birth certificate", "certificate birth Noah")
    elif field_name == "education_date":
        search_terms = ("diploma transcript graduation", "MBA degree")
    elif field_name == "raw_transcript_claim":
        search_terms = (_clean(query),)
    else:
        search_terms = (_clean(query),)

    for term in search_terms:
        try:
            from document_atlas import search_atlas

            result = search_atlas(term, limit=3)
            for item in result.get("results") or []:
                candidates.append(
                    SourceCandidate(
                        field=field_name,
                        value=None,
                        source_class="document_atlas_metadata",
                        source_id=str(item.get("id") or item.get("path") or item.get("name") or ""),
                        source_label=str(item.get("name") or "document_atlas_hit"),
                        precision="metadata_pointer",
                        confidence=str(item.get("classification_confidence") or ""),
                        evidence_date=str(item.get("modified_at") or ""),
                        source_path=item.get("path"),
                        privacy_scope="PRIVATE_ORACLE",
                        provenance_ref=str(item.get("index_path") or "document_atlas"),
                        note="Metadata hit only; no fact value extracted.",
                    )
                )
        except Exception:
            pass
        try:
            from file_recall import search

            result = search(term, limit=3, write_receipt=False, deep=False)
            for item in result.get("results") or []:
                candidates.append(
                    SourceCandidate(
                        field=field_name,
                        value=None,
                        source_class="file_recall_metadata",
                        source_id=str(item.get("path") or item.get("name") or ""),
                        source_label=str(item.get("name") or "file_recall_hit"),
                        precision="metadata_pointer",
                        evidence_date=str(item.get("modified") or ""),
                        source_path=item.get("path"),
                        privacy_scope="PRIVATE_ORACLE",
                        provenance_ref="file_recall.search",
                        note="Metadata hit only; no fact value extracted.",
                    )
                )
        except Exception:
            pass
    return candidates


def gather_candidates(query: str, field_name: str, domain: str) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    if domain == PERSONAL_IDENTITY or field_name == "date_of_birth":
        candidates.extend(_identity_candidates_from_remember_me(field_name))
        if any(
            item.value not in (None, "", "UNKNOWN")
            and item.precision == "exact"
            and item.source_class == "governed_verified_identity_record"
            for item in candidates
        ):
            return candidates
    if domain == REPOSITORY_SOFTWARE or field_name == "repository_head":
        candidates.extend(_repository_candidates(field_name))
    if domain == RUNTIME_STATE or field_name == "runtime_state":
        candidates.extend(_runtime_candidates(field_name))
    candidates.extend(_metadata_source_candidates(query, field_name))
    return candidates


def format_for_context(result: ResolutionResult, *, public: bool = False, max_chars: int = 1600) -> str:
    data = result.to_dict(public=public)
    lines = [
        "[SOURCE_RESOLVER - deterministic evidence resolution]",
        f"query: {data['query']}",
        f"fact_domain: {data['fact_domain']}",
        f"field: {data['field']}",
        f"status: {data['status']}",
        f"selection_reason: {data['selection_reason']}",
    ]
    selected = data.get("selected_claim")
    if selected:
        lines.append(
            "selected_claim: "
            f"value={selected.get('value')} source_class={selected.get('source_class')} "
            f"source_id={selected.get('source_id')} precision={selected.get('precision')}"
        )
    if data.get("unavailable_sources"):
        lines.append("unavailable_sources:")
        for item in data["unavailable_sources"]:
            lines.append(f"- {item.get('source_class')}: {item.get('reason')}")
    if data.get("conflicts"):
        lines.append("conflicts:")
        for item in data["conflicts"]:
            lines.append(f"- value={item.get('value')} source_class={item.get('source_class')} source_id={item.get('source_id')}")
    lines.append("law: SOURCE_UNAVAILABLE != NOT_FOUND; NOT_FOUND != FALSE; NOT_RETRIEVED != DOES_NOT_EXIST")
    return "\n".join(lines)[:max_chars]


def natural_status_line(result: ResolutionResult) -> str:
    if result.status == RESOLVED and result.selected_claim:
        return "Resolved from the strongest available source class."
    if result.status == PARTIAL:
        return "I found partial evidence, but a stronger source is unavailable or the retrieved precision is insufficient."
    if result.status == SOURCE_UNAVAILABLE:
        return "I know which evidence class should be checked, but that source is unavailable right now."
    if result.status == CONFLICT:
        return "I found conflicting strong sources and will not choose one without resolution."
    if result.status == NOT_FOUND:
        return "I searched the relevant reachable records and did not find a candidate claim."
    return "The retrieved evidence is insufficient for a reliable claim."


def resolve_to_dict(query: str, **kwargs: Any) -> dict[str, Any]:
    return resolve_fact(query, **kwargs).to_dict(public=bool(kwargs.get("public")))
