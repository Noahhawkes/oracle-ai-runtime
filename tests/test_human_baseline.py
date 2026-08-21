from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import human_baseline as hb  # noqa: E402


def _private_baseline():
    return hb.baseline_payload()["baseline"]


def test_governed_dob_record_is_retrieved_and_refines_year_only_state():
    baseline = _private_baseline()

    assert baseline["birth_year"] == 1982
    assert baseline["birth_date"] == "1982-02-02"
    assert baseline["birth_date_precision"] == "exact"
    assert baseline["birth_date_verification"] == hb.VERIFIED
    assert baseline["birth_date_privacy_scope"] == "PRIVATE_IDENTITY"
    assert baseline["birth_date_source_ref_id"] == "exact_dob_identity_record"
    assert baseline["age_at_snapshot"]["value"] == 44
    assert baseline["age_at_snapshot"]["precision"] == "exact"
    assert baseline["age_at_snapshot"]["historical_snapshot"]["age"] == 44
    assert not any("Exact birth month/day" in item for item in baseline["known_unknowns"])
    assert baseline["confidence"]["exact_birth_date"] == hb.VERIFIED


def test_human_baseline_does_not_hardcode_exact_dob():
    source = (ROOT / "core" / "human_baseline.py").read_text(encoding="utf-8")

    assert "1982-02-02" not in source


def test_previous_year_only_record_remains_intact():
    record_path = ROOT / "Memory" / "remember_me" / "fe0aba91-eac9-48a1-b627-c80d83bf1e23.json"
    record = __import__("json").loads(record_path.read_text(encoding="utf-8"))

    assert record["event_date"] == "1982"
    assert record["event_date_note"] == "birth year confirmed"
    assert "Exact birth date (day and month)" in record["unknowns"]
    assert record["status"] == "approved"


def test_age_calculation_handles_exact_birth_date_rollover_from_private_record():
    assert hb.calculate_age("1982-02-02", date(2026, 2, 1)) == 43
    assert hb.calculate_age("1982-02-02", date(2026, 2, 2)) == 44
    assert hb.calculate_age("1982-02-02", date(2026, 8, 19)) == 44
    assert hb.calculate_age("1982-02-02", date(2027, 2, 1)) == 44
    assert hb.calculate_age("1982-02-02", date(2027, 2, 2)) == 45
    assert hb.calculate_age("1982", date(2026, 8, 19)) is None


def test_unverified_dob_cannot_override_verified_dob():
    records = [
        {
            "id": "verified",
            "status": "approved",
            "_indexed_status": "approved",
            "approved_at": "2026-08-19T00:00:00+00:00",
            "identity_assertion": {
                "subject": "Noah.Physical",
                "field": "date_of_birth",
                "value": "1982-02-02",
                "verification_state": "VERIFIED",
                "privacy_scope": "PRIVATE_IDENTITY",
            },
        },
        {
            "id": "unverified",
            "status": "pending",
            "_indexed_status": "pending",
            "approved_at": "2027-01-01T00:00:00+00:00",
            "identity_assertion": {
                "subject": "Noah.Physical",
                "field": "date_of_birth",
                "value": "1983-03-03",
                "verification_state": "INFERRED",
                "privacy_scope": "PRIVATE_IDENTITY",
            },
        },
    ]

    selected = hb.select_verified_dob_record(records)

    assert selected["status"] == hb.VERIFIED
    assert selected["value"] == "1982-02-02"
    assert selected["conflict"] is False
    assert "unverified" in selected["ignored_unverified"]


def test_conflicting_verified_dob_does_not_silently_replace_current_record():
    records = [
        {
            "id": "first",
            "status": "approved",
            "_indexed_status": "approved",
            "identity_assertion": {
                "subject": "Noah.Physical",
                "field": "date_of_birth",
                "value": "1982-02-02",
                "verification_state": "VERIFIED",
                "privacy_scope": "PRIVATE_IDENTITY",
            },
        },
        {
            "id": "second",
            "status": "approved",
            "_indexed_status": "approved",
            "identity_assertion": {
                "subject": "Noah.Physical",
                "field": "date_of_birth",
                "value": "1983-03-03",
                "verification_state": "VERIFIED",
                "privacy_scope": "PRIVATE_IDENTITY",
            },
        },
    ]

    selected = hb.select_verified_dob_record(records)

    assert selected["status"] == "IDENTITY_CONFLICT"
    assert selected["conflict"] is True
    assert selected["value"] is None
    assert selected["values"] == ["1982-02-02", "1983-03-03"]


def test_family_facts_are_bounded_and_brooklyn_relationship_stays_unresolved():
    family = _private_baseline()["family_summary"]

    assert family["spouse"]["name"] == "Ashley"
    assert family["spouse"]["relationship"] == "spouse"
    assert family["children_established"] == ["Elijah", "Ethan", "Ender"]
    unresolved = family["family_record_unresolved"][0]
    assert unresolved["name"] == "Brooklyn"
    assert unresolved["relationship"] == hb.UNKNOWN


def test_2022_truck_accident_answer_has_no_invented_medical_detail():
    answer = hb.answer_text("What major event happened to me in 2022?")

    assert "August 2022 truck accident" in answer
    assert "medical specifics" in answer
    forbidden = ("diagnosis", "surgery", "spinal cord", "paralysis", "MRN")
    assert not any(term in answer.lower() for term in forbidden)


def test_education_and_professional_summary_are_retrievable():
    education = hb.answer_text("What is my education?")
    profession = hb.answer_text("What do I do professionally?")

    assert "MBA" in education
    assert "institution" in education
    assert "sales leadership" in profession
    assert "EcoWater Systems" in profession


def test_public_scope_excludes_private_family_and_local_source_paths():
    public = hb.baseline_payload(audience="public")["baseline"]
    serialized = str(public)

    assert public["privacy_scope"]["default"] == "PUBLIC_SAFE"
    assert public["birth_date"] == "1982"
    assert public["birth_date_precision"] == "year"
    assert "1982-02-02" not in serialized
    assert "exact_dob_identity_record" not in serialized
    for private_name in ("Ashley", "Elijah", "Ethan", "Ender", "Brooklyn"):
        assert private_name not in serialized
    assert "C:\\Oracle" not in serialized
    assert "Users\\Noah.Self" not in serialized


def test_first_person_journal_is_source_context_not_fact_table():
    baseline = _private_baseline()
    journal = next(ref for ref in baseline["source_refs"] if ref["id"] == "noah_personal_journal_docx")

    assert "not an automatic fact table" in journal["note"]
    assert journal["status"] == hb.SOURCE_DERIVED
    accident = next(item for item in baseline["major_life_events"] if item["event"] == "truck_accident")
    assert "noah_personal_journal_docx" in accident["source_ref_ids"]
    assert "No medical specifics" in accident["boundary"]


def test_source_refs_survive_answer_retrieval():
    payload = hb.answer_query("Who am I?")

    assert "source_refs" in payload
    assert "seed_verified_noah_py" in payload["source_refs"]
    assert "noah_profile_candidate_md" in payload["source_refs"]


def test_superseded_fields_do_not_override_current_fields():
    baseline = _private_baseline()
    superseded = baseline["superseded_fields"][0]

    assert superseded["field"] == "residence"
    assert superseded["superseded_value"] == "Midlothian, TX"
    assert superseded["current_value"] == "Ovilla, TX"
    assert superseded["status"] == hb.SUPERSEDED


def test_natural_uncertainty_avoids_robotic_status_labels():
    answer = hb.answer_text("How old am I?")

    assert answer == "You're 44."
    assert "UNKNOWN FIELD" not in answer


def test_private_birth_date_provenance_answer_uses_governed_record():
    answer = hb.answer_text("What is my date of birth and provenance?")

    assert "February 2, 1982" in answer
    assert "explicit Noah.Physical identity approval" in answer


def test_public_birth_date_answer_redacts_exact_dob():
    answer = hb.answer_text("What is my date of birth?", audience="public")

    assert "birth year only: 1982" in answer
    assert "February 2, 1982" not in answer
    assert "1982-02-02" not in answer


def test_identity_equivalence_claim_is_forbidden():
    for prompt in ("Who am I?", "What are the major human anchors behind Rendered Reality?"):
        answer = hb.answer_text(prompt).lower()
        assert "the archive is evidence about you; it is not you" in answer or "not just fiction" in answer
        assert "oracle is noah" not in answer
        assert "archive is noah" not in answer
