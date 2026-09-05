from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import human_baseline as hb  # noqa: E402
import recall_orchestrator as ro  # noqa: E402
import source_resolver as sr  # noqa: E402


def cand(field: str, value, source_class: str, source_id: str, **kwargs) -> sr.SourceCandidate:
    return sr.SourceCandidate(
        field=field,
        value=value,
        source_class=source_class,
        source_id=source_id,
        source_label=kwargs.pop("source_label", source_id),
        precision=kwargs.pop("precision", "exact"),
        authority=kwargs.pop("authority", ""),
        confidence=kwargs.pop("confidence", "VERIFIED"),
        evidence_date=kwargs.pop("evidence_date", ""),
        source_path=kwargs.pop("source_path", None),
        privacy_scope=kwargs.pop("privacy_scope", "PRIVATE_ORACLE"),
        provenance_ref=kwargs.pop("provenance_ref", source_id),
        note=kwargs.pop("note", ""),
        claim_status=kwargs.pop("claim_status", "candidate"),
    )


def test_personal_dob_selects_primary_over_year_summary_and_model_guess():
    result = sr.resolve_fact(
        "What is my birthday?",
        field="date_of_birth",
        candidates=[
            cand("date_of_birth", "1982", "t1_verified_continuity_signal", "t1_birth", precision="year"),
            cand("date_of_birth", "1982-02-02", "primary_legal_identity_artifact", "birth_certificate"),
            cand("date_of_birth", "1984-04-04", "model_inference", "model_guess"),
        ],
        write_receipt=False,
    )

    assert result.status == sr.RESOLVED
    assert result.selected_claim is not None
    assert result.selected_claim.value == "1982-02-02"
    assert result.selected_claim.source_class == "primary_legal_identity_artifact"


def test_source_unavailable_is_not_absence_when_partial_evidence_exists():
    result = sr.resolve_fact(
        "What is my exact date of birth?",
        field="date_of_birth",
        candidates=[
            cand("date_of_birth", "1982", "t1_verified_continuity_signal", "t1_birth", precision="year"),
        ],
        unavailable_sources={"primary_legal_identity_artifact": "Drive/local primary artifact source unreachable"},
        write_receipt=False,
    )

    assert result.status == sr.PARTIAL
    assert result.status != sr.NOT_FOUND
    assert result.unavailable_sources[0]["source_class"] == "primary_legal_identity_artifact"
    assert result.selected_claim is not None
    assert result.selected_claim.value == "1982"


def test_source_unavailable_without_candidates_is_not_not_found():
    result = sr.resolve_fact(
        "What is my exact date of birth?",
        field="date_of_birth",
        candidates=[],
        unavailable_sources={"primary_legal_identity_artifact": "birth certificate store unavailable"},
        write_receipt=False,
    )

    assert result.status == sr.SOURCE_UNAVAILABLE
    assert result.status != sr.NOT_FOUND


def test_conflicting_strong_sources_do_not_silently_overwrite():
    result = sr.resolve_fact(
        "What is my birthday?",
        field="date_of_birth",
        candidates=[
            cand("date_of_birth", "1982-02-02", "primary_legal_identity_artifact", "birth_certificate"),
            cand("date_of_birth", "1983-03-03", "governed_verified_identity_record", "remember_me_dob"),
        ],
        write_receipt=False,
    )

    assert result.status == sr.CONFLICT
    assert result.selected_claim is None
    assert {item["value"] for item in result.conflicts} == {"1982-02-02", "1983-03-03"}


def test_education_date_uses_education_primary_source_before_summary():
    result = sr.resolve_fact(
        "When did I graduate?",
        candidates=[
            cand("education_date", "2008", "later_summary", "summary", precision="year"),
            cand("education_date", "2007-05-12", "primary_education_artifact", "diploma"),
        ],
        write_receipt=False,
    )

    assert result.fact_domain == sr.EDUCATION_RECORD
    assert result.status == sr.RESOLVED
    assert result.selected_claim.value == "2007-05-12"
    assert result.selected_claim.source_class == "primary_education_artifact"


def test_historical_life_event_prefers_contemporaneous_record():
    result = sr.resolve_fact(
        "What happened in the 2022 accident?",
        candidates=[
            cand("historical_life_event", "truck accident in August 2022", "later_first_person_recollection", "journal"),
            cand("historical_life_event", "truck accident recorded 2022-08", "contemporaneous_record", "accident_record"),
        ],
        write_receipt=False,
    )

    assert result.fact_domain == sr.HISTORICAL_LIFE_EVENT
    assert result.status == sr.RESOLVED
    assert result.selected_claim.source_class == "contemporaneous_record"


def test_repository_head_prefers_current_filesystem_state():
    result = sr.resolve_fact(
        "What commit is ORACLE running?",
        candidates=[
            cand("repository_head", "old-summary-sha", "narrative_summary", "summary"),
            cand("repository_head", "abc123", "current_filesystem_repository_state", "git_head"),
        ],
        write_receipt=False,
    )

    assert result.fact_domain == sr.REPOSITORY_SOFTWARE
    assert result.status == sr.RESOLVED
    assert result.selected_claim.value == "abc123"


def test_runtime_state_query_prefers_live_runtime_receipt():
    result = sr.resolve_fact(
        "Is localhost runtime running?",
        candidates=[
            cand("runtime_state", {"runtime_status": "offline"}, "narrative_summary", "summary"),
            cand("runtime_state", {"runtime_status": "online", "runtime_port": 7781}, "live_runtime_receipt", "runtime_probe"),
        ],
        write_receipt=False,
    )

    assert result.fact_domain == sr.RUNTIME_STATE
    assert result.status == sr.RESOLVED
    assert result.selected_claim.value["runtime_status"] == "online"


def test_raw_transcript_claim_prefers_raw_record_before_summary():
    result = sr.resolve_fact(
        "Did I say build the gateway?",
        candidates=[
            cand("raw_transcript_claim", "summary says maybe gateway", "conversation_summary", "summary"),
            cand("raw_transcript_claim", "Noah: build the gateway", "raw_transcript", "raw_thread"),
        ],
        write_receipt=False,
    )

    assert result.fact_domain == sr.RAW_TRANSCRIPT
    assert result.status == sr.RESOLVED
    assert result.selected_claim.source_class == "raw_transcript"


def test_missing_reachable_sources_return_not_found_not_false():
    result = sr.resolve_fact(
        "When did I graduate?",
        field="education_date",
        candidates=[],
        write_receipt=False,
    )

    assert result.status == sr.NOT_FOUND
    assert result.selection_reason.startswith("Relevant source classes were searched")


def test_weak_summary_does_not_outrank_primary_source():
    result = sr.resolve_fact(
        "What happened in the 2022 accident?",
        candidates=[
            cand("historical_life_event", "summary version", "secondary_summary", "summary"),
            cand("historical_life_event", "primary record version", "native_primary_artifact", "primary"),
        ],
        write_receipt=False,
    )

    assert result.status == sr.RESOLVED
    assert result.selected_claim.value == "primary record version"


def test_model_inference_alone_is_insufficient():
    result = sr.resolve_fact(
        "What is my birthday?",
        field="date_of_birth",
        candidates=[
            cand("date_of_birth", "1982-02-02", "model_inference", "model_guess"),
        ],
        write_receipt=False,
    )

    assert result.status == sr.INSUFFICIENT_EVIDENCE
    assert result.selected_claim is None


def test_public_result_redacts_private_selected_claim():
    result = sr.resolve_fact(
        "What is my birthday?",
        field="date_of_birth",
        candidates=[
            cand(
                "date_of_birth",
                "1982-02-02",
                "primary_legal_identity_artifact",
                "birth_certificate",
                source_path=r"C:\private\birth_certificate.png",
                privacy_scope="PRIVATE_IDENTITY",
            ),
        ],
        public=True,
        write_receipt=False,
    )
    public = result.to_dict(public=True)

    assert result.to_dict(public=False)["selected_claim"]["value"] == "1982-02-02"
    assert public["selected_claim"]["value"] == "REDACTED_PRIVATE"
    assert public["selected_claim"]["source_path"] is None


def test_resolution_receipt_is_written(tmp_path, monkeypatch):
    receipt = tmp_path / "source_resolution_receipts.jsonl"
    monkeypatch.setattr(sr, "RECEIPT_FILE", receipt)

    result = sr.resolve_fact(
        "What is my birthday?",
        field="date_of_birth",
        candidates=[
            cand("date_of_birth", "1982-02-02", "primary_legal_identity_artifact", "birth_certificate"),
        ],
        write_receipt=True,
    )

    assert result.receipt_path == str(receipt)
    lines = receipt.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert '"receipt_kind": "source_resolution_receipt"' in lines[0]


def test_real_governed_dob_record_resolves_without_hardcoded_human_baseline_value():
    result = sr.resolve_fact("What is my birthday?", field="date_of_birth", write_receipt=False)

    assert result.status == sr.RESOLVED
    assert result.selected_claim is not None
    assert result.selected_claim.source_class == "governed_verified_identity_record"
    assert result.selected_claim.value == "1982-02-02"


def test_human_baseline_consumes_source_resolver_for_private_age():
    record = hb.load_verified_dob_record()
    context = ro.build_context("How old am I?")

    assert record["source_resolution"]["status"] == sr.RESOLVED
    assert record["value"] == "1982-02-02"
    assert context["source_resolution"]["status"] == sr.RESOLVED
    assert context["source_resolution"]["selected_claim"]["source_class"] == "governed_verified_identity_record"
    assert ro.format_recall_answer("How old am I?", context) == "You're 44."

