"""Governed human-baseline recall for Noah.Physical.

This module is a small adapter over existing ORACLE continuity sources. It is
not a separate memory engine and it does not write state. Its job is to make
the "actual human" baseline answerable without confusing biography, creative
canon, journal prose, or generated narrative.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

SOURCE_DERIVED = "SOURCE_DERIVED"
USER_CONFIRMED = "USER_CONFIRMED"
VERIFIED = "VERIFIED"
PUBLIC_SAFE = "PUBLIC_SAFE"
SUPERSEDED = "SUPERSEDED"
UNKNOWN = "UNKNOWN"

CURRENT_SNAPSHOT_DATE = "2026-08-19"
LAST_VERIFIED_AT = "2026-08-19T16:57:00-05:00"

_BIRTH_YEAR = 1982
_BIRTH_DATE = "1982"
_BIRTH_DATE_PRECISION = "year"
_REMEMBER_ME_DIR = RUNTIME_ROOT / "Memory" / "remember_me"
_REMEMBER_ME_INDEX = _REMEMBER_ME_DIR / "index.json"
_DOB_ASSERTION_FIELD = "date_of_birth"
_DOB_ASSERTION_SUBJECT = "Noah.Physical"
_DOB_PRIVACY_SCOPE = "PRIVATE_IDENTITY"
_DOB_VERIFICATION_STATE = VERIFIED
_DOB_SOURCE_REF_ID = "exact_dob_identity_record"

_HUMAN_QUERY_RE = re.compile(
    r"\b("
    r"who am i|who is noah|actual human|basic demographics|how old|"
    r"my age|birth date|education|what do i do professionally|professionally|"
    r"2022 accident|truck accident|major event happened to me in 2022|"
    r"human anchors behind rendered reality|human baseline|noah physical|"
    r"noah, the actual human"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AgeResult:
    value: int | str | None
    status: str
    method: str
    as_of: str
    precision: str
    historical_snapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "status": self.status,
            "method": self.method,
            "as_of": self.as_of,
            "precision": self.precision,
            "historical_snapshot": self.historical_snapshot,
        }


def _today() -> date:
    return date.fromisoformat(CURRENT_SNAPSHOT_DATE)


def _parse_as_of(value: date | str | None = None) -> date:
    if value is None:
        return _today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def calculate_age(birth_date: str, as_of: date | str | None = None) -> int | None:
    """Calculate exact age only from an ISO full date.

    A year-only source such as "1982" is not enough for birthday rollover, so
    the function returns None instead of inventing an exact age.
    """

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(birth_date or "")):
        return None
    born = date.fromisoformat(birth_date)
    current = _parse_as_of(as_of)
    return current.year - born.year - ((current.month, current.day) < (born.month, born.day))


def _valid_iso_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value or "")):
        return False
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def _governed_identity_records() -> list[dict[str, Any]]:
    try:
        index = json.loads(_REMEMBER_ME_INDEX.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []

    records: list[dict[str, Any]] = []
    for rid, indexed_status in sorted(index.items()):
        path = _REMEMBER_ME_DIR / f"{rid}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        data["_record_path"] = str(path.resolve())
        data["_indexed_status"] = indexed_status
        records.append(data)
    return records


def select_verified_dob_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Select a governed exact DOB assertion without letting recency silently win."""

    candidates: list[dict[str, Any]] = []
    ignored_unverified: list[str] = []
    for record in records:
        assertion = record.get("identity_assertion")
        if not isinstance(assertion, dict):
            continue
        if assertion.get("subject") != _DOB_ASSERTION_SUBJECT:
            continue
        if assertion.get("field") != _DOB_ASSERTION_FIELD:
            continue
        rid = str(record.get("id") or "")
        if record.get("_indexed_status", record.get("status")) != "approved" or record.get("status") != "approved":
            ignored_unverified.append(rid)
            continue
        if assertion.get("verification_state") != _DOB_VERIFICATION_STATE:
            ignored_unverified.append(rid)
            continue
        if assertion.get("privacy_scope") != _DOB_PRIVACY_SCOPE:
            ignored_unverified.append(rid)
            continue
        value = str(assertion.get("value") or "")
        if not _valid_iso_date(value):
            ignored_unverified.append(rid)
            continue
        candidates.append(
            {
                "id": rid,
                "value": value,
                "precision": assertion.get("precision") or "exact",
                "authority": assertion.get("authority"),
                "assertion_type": assertion.get("assertion_type"),
                "verification_state": assertion.get("verification_state"),
                "privacy_scope": assertion.get("privacy_scope"),
                "source": assertion.get("source"),
                "effective_date": assertion.get("effective_date"),
                "supersedes": assertion.get("supersedes"),
                "conflict_state": assertion.get("conflict_state"),
                "path": record.get("_record_path"),
                "approved_at": record.get("approved_at"),
            }
        )

    if not candidates:
        return {
            "status": UNKNOWN,
            "verification_state": UNKNOWN,
            "value": None,
            "precision": "year",
            "conflict": False,
            "ignored_unverified": ignored_unverified,
        }

    values = sorted({str(item["value"]) for item in candidates})
    if len(values) > 1:
        return {
            "status": "IDENTITY_CONFLICT",
            "verification_state": "IDENTITY_CONFLICT",
            "value": None,
            "precision": "conflict",
            "conflict": True,
            "values": values,
            "records": candidates,
            "ignored_unverified": ignored_unverified,
        }

    candidates.sort(key=lambda item: (str(item.get("approved_at") or ""), str(item.get("id") or "")))
    selected = dict(candidates[0])
    selected.update(
        {
            "status": VERIFIED,
            "conflict": False,
            "records": candidates,
            "ignored_unverified": ignored_unverified,
        }
    )
    return selected


def load_verified_dob_record() -> dict[str, Any]:
    try:
        from source_resolver import CONFLICT as SOURCE_CONFLICT
        from source_resolver import PARTIAL, RESOLVED, resolve_fact

        result = resolve_fact(
            "What is my exact date of birth?",
            field=_DOB_ASSERTION_FIELD,
            write_receipt=False,
        )
        if result.status == RESOLVED and result.selected_claim:
            claim = result.selected_claim
            if claim.source_class == "governed_verified_identity_record" and _valid_iso_date(str(claim.value)):
                return {
                    "id": claim.source_id,
                    "value": str(claim.value),
                    "precision": claim.precision,
                    "authority": claim.authority,
                    "assertion_type": "explicit_human_approval",
                    "verification_state": VERIFIED,
                    "privacy_scope": claim.privacy_scope,
                    "source": claim.provenance_ref,
                    "effective_date": claim.evidence_date,
                    "supersedes": "no exact prior DOB record",
                    "conflict_state": "none known",
                    "path": claim.source_path,
                    "approved_at": claim.evidence_date,
                    "status": VERIFIED,
                    "conflict": False,
                    "records": [claim.to_dict()],
                    "source_resolution": result.to_dict(public=False),
                }
        if result.status == SOURCE_CONFLICT:
            return {
                "status": "IDENTITY_CONFLICT",
                "verification_state": "IDENTITY_CONFLICT",
                "value": None,
                "precision": "conflict",
                "conflict": True,
                "records": result.conflicts,
                "source_resolution": result.to_dict(public=False),
            }
        if result.status == PARTIAL:
            return {
                "status": UNKNOWN,
                "verification_state": UNKNOWN,
                "value": None,
                "precision": "year",
                "conflict": False,
                "source_resolution": result.to_dict(public=False),
            }
    except Exception:
        pass
    return select_verified_dob_record(_governed_identity_records())


def _age_range_from_year(year: int, as_of: date) -> str:
    high = as_of.year - year
    low = high - 1
    return f"{low}-{high}"


def _private_birth_date_phrase(value: str | None) -> str:
    if not _valid_iso_date(str(value or "")):
        return "the verified private date of birth"
    born = date.fromisoformat(str(value))
    return f"{born.strftime('%B')} {born.day}, {born.year}"


def age_at(as_of: date | str | None = None, dob_record: dict[str, Any] | None = None) -> AgeResult:
    current = _parse_as_of(as_of)
    dob_record = dob_record if dob_record is not None else load_verified_dob_record()
    exact_birth_date = dob_record.get("value") if dob_record.get("status") == VERIFIED else _BIRTH_DATE
    exact = calculate_age(str(exact_birth_date or ""), current)
    if exact is not None:
        return AgeResult(
            value=exact,
            status=SOURCE_DERIVED,
            method="governed exact DOB identity assertion",
            as_of=current.isoformat(),
            precision="exact",
            historical_snapshot={"age": 44, "as_of": CURRENT_SNAPSHOT_DATE, "status": USER_CONFIRMED},
        )
    return AgeResult(
        value=_age_range_from_year(_BIRTH_YEAR, current),
        status=SOURCE_DERIVED,
        method="birth-year range; exact month/day not verified in repo-local sources",
        as_of=current.isoformat(),
        precision="range",
        historical_snapshot={
            "age": 44,
            "as_of": CURRENT_SNAPSHOT_DATE,
            "status": USER_CONFIRMED,
            "note": "Current Noah.Physical build directive uses 44 as the expected live answer; exact DOB remains unverified here.",
        },
    )


def _sha256(path: Path) -> str | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _source_ref(ref_id: str, rel_path: str | None, label: str, note: str, status: str = SOURCE_DERIVED) -> dict[str, Any]:
    path = RUNTIME_ROOT / rel_path if rel_path else None
    return {
        "id": ref_id,
        "label": label,
        "path": str(path.resolve()) if path and path.exists() else (str(path) if path else None),
        "sha256": _sha256(path) if path else None,
        "status": status,
        "note": note,
    }


def source_refs(*, public: bool = False) -> list[dict[str, Any]]:
    dob_record = load_verified_dob_record()
    refs = [
        _source_ref(
            "seed_verified_noah_py",
            "core/seed_verified_noah.py",
            "Verified Noah seed records",
            "Approved/candidate identity continuity seed material already present in the runtime.",
            VERIFIED,
        ),
        _source_ref(
            "noah_profile_candidate_md",
            "docs/NOAH_PROFILE_CANDIDATE.md",
            "Corrected Noah profile candidate",
            "Candidate profile with explicit UNKNOWN handling, public/private boundary, and superseded location correction.",
            SOURCE_DERIVED,
        ),
        _source_ref(
            "noah_identity_anchor_json",
            "Users/Noah.Self/Noah.Self Upload Repository/Noah.Identity.Anchor.json",
            "Noah.Identity.Anchor",
            "Noah.Self value and continuity anchor. Treated as identity-source context, not proof that the archive is Noah.",
            SOURCE_DERIVED,
        ),
        _source_ref(
            "noah_complete_profile_docx",
            "Users/Noah.Self/Noah.Self Upload Repository/Noah_Hawkes_Complete_Profile.docx",
            "Noah Hawkes complete profile",
            "Profile source with birth year, Fort Sam Houston origin, and family/professional continuity context.",
            SOURCE_DERIVED,
        ),
        _source_ref(
            "noah_personal_journal_docx",
            "Users/Noah.Self/Noah.Self Upload Repository/Journals/Noah Personal Journal.docx",
            "Noah Personal Journal",
            "First-person authored continuity artifact. It is source context, not an automatic fact table.",
            SOURCE_DERIVED,
        ),
        {
            "id": "current_codex_build_directive_2026_08_19",
            "label": "Noah.Physical build directive",
            "path": None,
            "sha256": None,
            "status": USER_CONFIRMED,
            "note": "Current directive requesting Human Baseline Continuity V1, including age handling and August 2022 accident boundary.",
        },
    ]
    if dob_record.get("status") == VERIFIED:
        dob_path = Path(str(dob_record.get("path") or ""))
        refs.append(
            {
                "id": _DOB_SOURCE_REF_ID,
                "label": "Private exact DOB identity assertion",
                "path": str(dob_path) if dob_path.exists() else str(dob_record.get("path") or ""),
                "sha256": _sha256(dob_path) if dob_path.exists() else None,
                "status": VERIFIED,
                "privacy_scope": _DOB_PRIVACY_SCOPE,
                "note": "Explicit Noah.Physical identity approval; exact value is private and public-redacted.",
            }
        )
    elif dob_record.get("conflict"):
        refs.append(
            {
                "id": _DOB_SOURCE_REF_ID,
                "label": "Private exact DOB identity assertion",
                "path": None,
                "sha256": None,
                "status": "IDENTITY_CONFLICT",
                "privacy_scope": _DOB_PRIVACY_SCOPE,
                "note": "Conflicting governed exact DOB values detected; exact DOB is withheld until Noah.Physical resolves it.",
            }
        )
    if not public:
        return refs
    return [
        {k: v for k, v in item.items() if k in {"id", "label", "status", "note"}}
        for item in refs[:2]
    ]


def _base(as_of: date | str | None = None) -> dict[str, Any]:
    dob_record = load_verified_dob_record()
    dob_verified = dob_record.get("status") == VERIFIED
    dob_conflict = bool(dob_record.get("conflict"))
    birth_date = str(dob_record["value"]) if dob_verified else _BIRTH_DATE
    birth_precision = "exact" if dob_verified else _BIRTH_DATE_PRECISION
    birth_status = VERIFIED if dob_verified else ("IDENTITY_CONFLICT" if dob_conflict else SOURCE_DERIVED)
    age = age_at(as_of, dob_record=dob_record).to_dict()
    known_unknowns = [
        "Brooklyn's exact relationship is unresolved in the current baseline.",
        "MBA institution and graduation year are not verified here.",
        "Medical details from the 2022 accident are not verified and are intentionally not surfaced.",
        "First-person journal material is source context, not automatically structured fact.",
    ]
    if not dob_verified:
        known_unknowns.insert(0, "Exact birth month/day is not verified in repo-local sources.")
    if dob_conflict:
        known_unknowns.insert(0, "IDENTITY_CONFLICT: conflicting exact DOB records require Noah.Physical resolution.")
    return {
        "human_id": "Noah.Physical",
        "display_name": "Noah Alexander Hawkes Sr.",
        "birth_year": _BIRTH_YEAR,
        "birth_date": birth_date,
        "birth_date_precision": birth_precision,
        "birth_date_status": birth_status,
        "birth_date_verification": dob_record.get("verification_state", UNKNOWN),
        "birth_date_privacy_scope": dob_record.get("privacy_scope", "PRIVATE_ORACLE"),
        "birth_date_source_ref_id": _DOB_SOURCE_REF_ID if dob_verified else None,
        "age_at_snapshot": age,
        "sex": {"value": "male", "status": SOURCE_DERIVED},
        "family_summary": {
            "status": USER_CONFIRMED,
            "private_oracle": True,
            "summary": (
                "Noah is represented as married to Ashley and as father to Elijah, Ethan, and Ender. "
                "Brooklyn appears in the family record, but this baseline does not have the exact relationship resolved strongly enough to state as fact."
            ),
            "spouse": {"name": "Ashley", "relationship": "spouse", "status": USER_CONFIRMED},
            "children_established": ["Elijah", "Ethan", "Ender"],
            "family_record_unresolved": [{"name": "Brooklyn", "relationship": UNKNOWN, "status": UNKNOWN}],
            "speaker_boundary": "Ashley may use the account and should be speaker-attributed when context indicates that.",
        },
        "education_summary": {
            "summary": "Noah holds an MBA. The institution and year are not verified in this baseline.",
            "credentials": [{"name": "MBA", "status": VERIFIED}],
            "known_unknowns": ["MBA institution", "MBA graduation year"],
        },
        "professional_summary": {
            "summary": (
                "Noah's professional record centers on sales leadership and business development in the water industry. "
                "EcoWater Systems is observed in the current profile record; older records also connect him to industrial, trucking, and small-business operations."
            ),
            "organizations": [
                {"name": "EcoWater Systems", "status": SOURCE_DERIVED},
                {"name": "Culligan", "status": SOURCE_DERIVED},
                {"name": "Babylon Micro-Farms", "status": SOURCE_DERIVED},
            ],
        },
        "major_life_events": [
            {
                "event": "birth_origin",
                "date": "1982",
                "summary": "Born in 1982 at Fort Sam Houston / San Antonio, Texas.",
                "status": SOURCE_DERIVED,
                "source_ref_ids": ["seed_verified_noah_py", "noah_complete_profile_docx"],
            },
            {
                "event": "father_death",
                "date": "1997",
                "summary": "Noah's father, Thomas Alvin Hawkes Jr., died in 1997; Noah was 15.",
                "status": VERIFIED,
                "source_ref_ids": ["seed_verified_noah_py"],
            },
            {
                "event": "lds_records_removed",
                "date": "2008",
                "summary": "Noah removed his name from LDS church records in 2008.",
                "status": VERIFIED,
                "source_ref_ids": ["seed_verified_noah_py"],
            },
            {
                "event": "truck_accident",
                "date": "2022-08",
                "summary": "A truck accident in August 2022 is preserved as a major life event that affected Noah's work and family continuity.",
                "status": SOURCE_DERIVED,
                "boundary": "No medical specifics, legal numbers, or unsupported detail are promoted here.",
                "source_ref_ids": ["noah_personal_journal_docx", "current_codex_build_directive_2026_08_19"],
            },
            {
                "event": "rendered_reality_archive_begins",
                "date": "2024-12-01",
                "summary": "Noah began what became the Rendered Reality archive across multiple AI systems.",
                "status": VERIFIED,
                "source_ref_ids": ["seed_verified_noah_py"],
            },
        ],
        "creative_identity": {
            "summary": (
                "Noah is a writer and builder whose creative work includes Rendered Reality, The Silverback Tales, "
                "Jupiter Station, Drakin, and continuity-centered AI architecture. Creative canon remains separate from biography."
            ),
            "status": SOURCE_DERIVED,
        },
        "continuity_projects": [
            {"name": "ORACLE", "classification": "local witness, memory, provenance, and continuity runtime"},
            {"name": "Rendered Reality", "classification": "public-facing creative and continuity umbrella"},
            {"name": "The Silverback Tales", "classification": "creative production line"},
            {"name": "SOV1.AI", "classification": "governed companion/intelligence layer under development"},
            {"name": "Legacy.GI", "classification": "memory and identity architecture"},
            {"name": "Continuity Engine", "classification": "cross-session preservation system"},
        ],
        "current_snapshot_date": _parse_as_of(as_of).isoformat(),
        "source_refs": source_refs(public=False),
        "provenance": {
            "produced_with": "ORACLE human_baseline adapter",
            "token_origin": "code-derived structured baseline",
            "reviewed_by": "tests",
            "approved_by": "Noah.Physical required for canon promotion",
            "authorial_authority": "Noah.Physical",
            "identity_boundary": "The archive is evidence about Noah. The archive is not Noah.",
        },
        "confidence": {
            "name": VERIFIED,
            "birth_year": SOURCE_DERIVED,
            "exact_birth_date": VERIFIED if dob_verified else ("IDENTITY_CONFLICT" if dob_conflict else UNKNOWN),
            "family_summary": USER_CONFIRMED,
            "brooklyn_relationship": UNKNOWN,
            "profession": SOURCE_DERIVED,
            "creative_identity": SOURCE_DERIVED,
        },
        "privacy_scope": {
            "default": "PRIVATE_ORACLE",
            "public_policy": "Return only public-safe representation; omit local paths, children names, private family detail, and legal/medical particulars.",
        },
        "public_representation": {
            "display_name": "Noah Alexander Hawkes Sr.",
            "summary": "Founder and builder of Noah AI Technologies / ORACLE continuity work; writer of Rendered Reality; professional background in sales and business development.",
            "safe_fields": ["display_name", "creative_identity", "professional_summary_public", "continuity_projects_public"],
        },
        "known_unknowns": known_unknowns,
        "superseded_fields": [
            {
                "field": "residence",
                "superseded_value": "Midlothian, TX",
                "current_value": "Ovilla, TX",
                "status": SUPERSEDED,
                "source_ref_id": "noah_profile_candidate_md",
                "privacy": "private_oracle",
            }
        ],
        "last_verified_at": LAST_VERIFIED_AT,
    }


def public_view(baseline: dict[str, Any]) -> dict[str, Any]:
    public_age = deepcopy(baseline["age_at_snapshot"])
    if public_age.get("precision") == "exact":
        public_age["precision"] = "exact_age_public_safe"
        public_age["method"] = "derived current age; exact DOB redacted for public-safe view"
    public_age.pop("historical_snapshot", None)
    public = {
        "human_id": baseline["human_id"],
        "display_name": baseline["display_name"],
        "birth_date": str(baseline.get("birth_year") or _BIRTH_YEAR),
        "birth_date_precision": "year",
        "birth_date_status": SOURCE_DERIVED,
        "age_at_snapshot": public_age,
        "creative_identity": baseline["creative_identity"],
        "professional_summary": {
            "summary": "Sales and business-development background; current public-safe detail does not expose private family or legal/medical facts.",
            "status": SOURCE_DERIVED,
        },
        "continuity_projects": [
            item for item in baseline["continuity_projects"]
            if item["name"] in {"ORACLE", "Rendered Reality", "The Silverback Tales", "SOV1.AI"}
        ],
        "public_representation": baseline["public_representation"],
        "known_unknowns": [
            "Exact DOB is private identity data and is intentionally omitted.",
            "Private family details are intentionally omitted.",
        ],
        "source_refs": source_refs(public=True),
        "privacy_scope": {"default": "PUBLIC_SAFE"},
        "last_verified_at": baseline["last_verified_at"],
    }
    return public


def baseline_payload(*, audience: str = "private", as_of: date | str | None = None) -> dict[str, Any]:
    baseline = _base(as_of)
    public = str(audience or "").lower() in {"public", "public_safe", "noah.public"}
    return {
        "ok": True,
        "component": "human_baseline",
        "schema_version": "human_baseline.v1",
        "audience": "public" if public else "private",
        "boundary": "read-only structured recall; no memory write, no canon promotion, no sandbox access",
        "baseline": public_view(baseline) if public else baseline,
    }


def recall_record(user_text: str = "human baseline") -> dict[str, Any]:
    baseline = _base()
    return {
        "surface": "human_baseline",
        "query": user_text,
        "title": "Human Baseline Continuity V1",
        "path": str((RUNTIME_ROOT / "core" / "human_baseline.py").resolve()),
        "category": "governed_human_baseline",
        "canon_status": "candidate",
        "preview": (
            f"{baseline['display_name']} | birth_date={baseline['birth_date']} "
            f"precision={baseline['birth_date_precision']} | verification={baseline['birth_date_verification']} "
            f"| age={baseline['age_at_snapshot']['value']} "
            f"| boundary=archive evidence, not Noah"
        ),
        "source_refs": [ref["id"] for ref in baseline["source_refs"]],
    }


def is_human_baseline_query(user_text: str) -> bool:
    return bool(_HUMAN_QUERY_RE.search(str(user_text or "")))


def _contains(text: str, *needles: str) -> bool:
    lower = str(text or "").lower()
    return any(needle in lower for needle in needles)


def answer_query(user_text: str, *, audience: str = "private", as_of: date | str | None = None) -> dict[str, Any]:
    baseline = baseline_payload(audience=audience, as_of=as_of)["baseline"]
    text = str(user_text or "")
    age = baseline["age_at_snapshot"]
    source_ids = [ref.get("id") for ref in baseline.get("source_refs", [])]
    public = str(audience or "").lower() in {"public", "public_safe", "noah.public"}

    if _contains(text, "how old", "my age"):
        if age["precision"] in {"exact", "exact_age_public_safe"}:
            if public:
                answer = f"Public-safe answer: Noah is {age['value']} as of {age['as_of']}."
            elif _contains(text, "provenance", "source", "birth date", "dob"):
                answer = (
                    f"You're {age['value']}. Your verified date of birth is {_private_birth_date_phrase(baseline.get('birth_date'))}, "
                    "based on an explicit Noah.Physical identity approval."
                )
            else:
                answer = f"You're {age['value']}."
        else:
            answer = (
                f"I have your birth year as 1982, so as of {age['as_of']} the repo-local baseline can only calculate "
                f"an age range of {age['value']}. The current build directive uses 44 as the live snapshot age, "
                "but I do not have a verified birth month and day in these sources, so I will not pretend the rollover is proven."
            )
    elif _contains(text, "birth date", "date of birth", "dob"):
        if public:
            answer = "Public-safe baseline exposes birth year only: 1982. The exact date of birth is private identity data."
        elif baseline.get("birth_date_verification") == VERIFIED:
            answer = (
                f"Your verified date of birth is {_private_birth_date_phrase(baseline.get('birth_date'))}, "
                "based on an explicit Noah.Physical identity approval."
            )
        elif baseline.get("birth_date_verification") == "IDENTITY_CONFLICT":
            answer = "IDENTITY_CONFLICT: conflicting exact date-of-birth records exist and require Noah.Physical resolution."
        else:
            answer = "I have your birth year as 1982, but no verified exact month/day in the governed identity records."
    elif _contains(text, "2022", "truck accident", "accident"):
        answer = (
            "I have the August 2022 truck accident as a major life event. The bounded baseline says it affected your work "
            "and family continuity, including the trucking-career thread, but it does not promote medical specifics, legal numbers, "
            "or extra details from journal prose as verified fact."
        )
    elif _contains(text, "education"):
        answer = (
            "Your education baseline includes an MBA. The current structured record does not verify the institution or graduation year, "
            "so those remain open fields."
        )
    elif _contains(text, "professionally", "what do i do"):
        answer = (
            "Professionally, the baseline places you in sales leadership and business development, centered on the water industry. "
            "EcoWater Systems is observed in the current profile, with older source context also tying you to industrial, trucking, "
            "and small-business operations."
        )
    elif _contains(text, "human anchors", "rendered reality"):
        answer = (
            "The human anchors behind Rendered Reality are not just fiction: family continuity, your father's death in 1997, "
            "the need to preserve voice and memory, Ashley and the household as reality gravity, fatherhood, the August 2022 accident, "
            "and the long-running attempt to make AI preserve truth without turning it into mythology."
        )
    elif str(audience or "").lower() in {"public", "public_safe", "noah.public"}:
        answer = (
            "Noah Alexander Hawkes Sr. is represented publicly here as the human founder-builder behind ORACLE, SOV1.AI, "
            "and Rendered Reality. Public-safe recall omits private family details, local paths, and legal or medical specifics."
        )
    else:
        answer = (
            "You are Noah Alexander Hawkes Sr., recorded here as Noah.Physical: the human operator and final correction authority "
            "for ORACLE. I have your birth year as 1982 at Fort Sam Houston / San Antonio, Texas. I have Ashley as your spouse "
            "and Elijah, Ethan, and Ender as established sons. Brooklyn appears in the family record, but I do not have the exact "
            "relationship resolved strongly enough to state it as fact. You are a writer and builder of Rendered Reality, ORACLE, "
            "SOV1.AI, and related continuity systems. The archive is evidence about you; it is not you."
        )

    return {
        "answer": answer,
        "source_refs": source_ids,
        "confidence": baseline.get("confidence", {}),
        "known_unknowns": baseline.get("known_unknowns", []),
        "privacy_scope": baseline.get("privacy_scope", {}),
        "canon_status": "candidate",
        "promotion_status": "not_promoted",
    }


def answer_text(user_text: str, *, audience: str = "private", as_of: date | str | None = None) -> str:
    return str(answer_query(user_text, audience=audience, as_of=as_of)["answer"])


def evidence_view(user_text: str) -> dict[str, Any]:
    payload = baseline_payload()
    answer = answer_query(user_text)
    data = deepcopy(payload)
    data["query_answer"] = answer
    return data
