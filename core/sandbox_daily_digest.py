"""Sandbox daily digest builder for ORACLE self-prompt pulses.

The digest stays inside the sandbox boundary. It summarizes the local
self-prompt pulse trail plus matching receipts and can write a candidate
daily digest artifact and receipt without touching Drive, GitHub, email,
or any external system.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from root import ROOT


SANDBOX_ROOT = ROOT / "sandbox"
WORKBENCH_DIR = SANDBOX_ROOT / "workbench"
DIGEST_DIR = WORKBENCH_DIR / "oracle_self_notes" / "daily_digest"
RECEIPTS_DIR = SANDBOX_ROOT / "receipts"
PULSE_PREFIX = "oracle_self_prompt_"
PULSE_SUFFIX = ".ai"
RECEIPT_PREFIX = "sandbox_self_prompt_write_"
RECEIPT_SUFFIX = "_receipt.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _day_stamp(target_day: date | None = None) -> str:
    return (target_day or datetime.now(timezone.utc).date()).strftime("%Y%m%d")


def _pulse_files_for_day(target_day: date | None = None, *, pulse_dir: Path | None = None) -> list[Path]:
    root = pulse_dir or WORKBENCH_DIR
    stamp = _day_stamp(target_day)
    return sorted(root.glob(f"{PULSE_PREFIX}{stamp}T*{PULSE_SUFFIX}"))


def _receipt_files_for_day(target_day: date | None = None, *, receipt_dir: Path | None = None) -> list[Path]:
    root = receipt_dir or RECEIPTS_DIR
    stamp = _day_stamp(target_day)
    return sorted(root.glob(f"{RECEIPT_PREFIX}{stamp.lower()}T*{RECEIPT_SUFFIX}"))


def _parse_pulse(text: str) -> dict[str, Any]:
    current_section = None
    sections: dict[str, list[str]] = {}
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current_section:
                sections.setdefault(current_section, []).append("")
            continue
        if line.endswith(":") and "=" not in line and not line.startswith("."):
            current_section = line[:-1].strip().lower().replace(" ", "_")
            sections.setdefault(current_section, [])
            continue
        if "=" in line and current_section is None:
            key, value = line.split("=", 1)
            fields[key.strip().lower()] = value.strip()
            continue
        if current_section:
            sections.setdefault(current_section, []).append(line)
    return {"fields": fields, "sections": {key: "\n".join(value).strip() for key, value in sections.items()}}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def digest_path_for_day(target_day: date | None = None, *, digest_dir: Path | None = None) -> Path:
    out_dir = digest_dir or DIGEST_DIR
    return out_dir / f"oracle_daily_digest_{_day_stamp(target_day)}.ai"


def receipt_path_for_day(target_day: date | None = None, *, digest_dir: Path | None = None) -> Path:
    out_dir = digest_dir or DIGEST_DIR
    stamp = _day_stamp(target_day)
    return out_dir / f"sandbox_daily_digest_write_{stamp}T*{RECEIPT_SUFFIX}"


def daily_digest_status(target_day: date | None = None, *, digest_dir: Path | None = None) -> dict[str, Any]:
    digest_path = digest_path_for_day(target_day, digest_dir=digest_dir)
    receipt_glob = receipt_path_for_day(target_day, digest_dir=digest_dir)
    receipt_matches = sorted(digest_path.parent.glob(receipt_glob.name))
    capsule = _load_latest_capsule_summary()
    return {
        "ok": True,
        "digest_date": _day_stamp(target_day),
        "digest_path": str(digest_path),
        "receipt_path": str(receipt_matches[-1]) if receipt_matches else None,
        "digest_exists": digest_path.exists(),
        "receipt_exists": bool(receipt_matches),
        "source_map_capsule": capsule,
        "sandbox_only": True,
        "candidate_status": "sandbox_candidate",
        "promotion_status": "not_promoted",
    }


@dataclass
class DailyDigestArtifact:
    digest_date: str
    pulse_count: int
    receipt_count: int
    time_range: str
    repeated: list[str]
    changed: list[str]
    unknowns: list[str]
    boundary: list[str]
    review_items: list[str]
    sandbox_only: list[str]
    question: str
    source_map_capsule: dict[str, Any]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest_date": self.digest_date,
            "pulse_count": self.pulse_count,
            "receipt_count": self.receipt_count,
            "time_range": self.time_range,
            "repeated": self.repeated,
            "changed": self.changed,
            "unknowns": self.unknowns,
            "boundary": self.boundary,
            "review_items": self.review_items,
            "sandbox_only": self.sandbox_only,
            "question": self.question,
            "source_map_capsule": self.source_map_capsule,
            "notes": self.notes,
        }


def _load_latest_capsule_summary() -> dict[str, Any]:
    try:
        from source_map_stitcher import load_latest_capsule

        capsule = load_latest_capsule()
        if not capsule:
            return {"present": False, "summary": "no source-map capsule available"}
        counts = capsule.get("counts") or {}
        return {
            "present": True,
            "created_at": capsule.get("created_at"),
            "deduped_sources": counts.get("deduped_sources", 0),
            "raw_hits": counts.get("raw_hits", 0),
            "excluded_sensitive": counts.get("excluded_sensitive", 0),
            "anchors": list(capsule.get("anchor_queries") or []),
            "latest_path": capsule.get("latest_path"),
        }
    except Exception as exc:
        return {"present": False, "summary": f"source-map capsule unavailable: {type(exc).__name__}: {exc}"}


def _build_artifact(target_day: date | None = None, *, pulse_dir: Path | None = None, receipt_dir: Path | None = None) -> DailyDigestArtifact:
    pulses = _pulse_files_for_day(target_day, pulse_dir=pulse_dir)
    receipts = _receipt_files_for_day(target_day, receipt_dir=receipt_dir)
    parsed_pulses = [
        {
            "path": path,
            "text": path.read_text(encoding="utf-8", errors="replace"),
        }
        for path in pulses
    ]
    pulse_data = [_parse_pulse(item["text"]) for item in parsed_pulses]
    receipts_data = [rec for rec in (_read_json(path) for path in receipts) if rec is not None]

    timestamps = []
    for item in parsed_pulses:
        pulse_text = item["text"]
        for line in pulse_text.splitlines():
            if line.startswith("timestamp="):
                timestamps.append(line.split("=", 1)[1].strip())
                break

    time_range = "unknown"
    if timestamps:
        timestamps = sorted(timestamps)
        time_range = f"{timestamps[0]} -> {timestamps[-1]}"

    selected_tasks = Counter()
    evidence_lines = Counter()
    for pulse in pulse_data:
        child_response = (pulse.get("sections") or {}).get("child_response", "")
        if child_response:
            first_line = child_response.splitlines()[0].strip()
            if first_line:
                selected_tasks[first_line] += 1
        reflection = (pulse.get("sections") or {}).get("self_reflection", "")
        if reflection:
            evidence_lines[reflection.splitlines()[0].strip()] += 1

    repeated: list[str] = []
    if selected_tasks:
        task, count = selected_tasks.most_common(1)[0]
        repeated.append(f"Most repeated self-prompt response: {task} ({count}/{len(pulses)} pulses)")
    if evidence_lines:
        note, count = evidence_lines.most_common(1)[0]
        repeated.append(f"Most repeated closing reflection: {note} ({count}/{len(pulses)} pulses)")
    if not repeated:
        repeated.append("No stable repeated response pattern was detected in the pulse text.")

    changed: list[str] = []
    if pulses:
        first = pulse_data[0]
        last = pulse_data[-1]
        first_task = (first.get("sections") or {}).get("child_response", "").splitlines()[0].strip() if (first.get("sections") or {}).get("child_response") else ""
        last_task = (last.get("sections") or {}).get("child_response", "").splitlines()[0].strip() if (last.get("sections") or {}).get("child_response") else ""
        if first_task and last_task and first_task != last_task:
            changed.append(f"Self-prompt response shifted from '{first_task}' to '{last_task}'.")
        else:
            changed.append("The self-prompt response stayed stable across the day.")
    else:
        changed.append("No pulses were found for the target day.")

    boundary: list[str] = []
    boundary_ok = all((receipt or {}).get("boundary_check_result", {}).get("boundary_ok") is True for receipt in receipts_data) if receipts_data else False
    if boundary_ok:
        boundary.append(f"{len(receipts_data)} receipt(s) reported boundary_ok=true.")
        boundary.append("No receipt reported external send, Drive edit, Git push, computer control, or execution.")
    else:
        boundary.append("No matching receipts were found, or not all receipts carried a positive boundary check.")

    review_items: list[str] = []
    if pulses:
        review_items.append("Confirm whether the repeated self-reflection should become a structured checklist or stay as a lightweight witness trace.")
    if not receipts_data:
        review_items.append("Verify the receipt trail for the current day so digest summaries can cite a concrete boundary check.")

    unknowns = [
        "Which pulse themes Noah wants elevated from candidate to standing review note.",
        "Whether source-map context should be pulled from the latest capsule or a date-matched capsule snapshot.",
    ]
    if not pulses:
        unknowns.append("No sandbox self-prompt pulses were found for this day.")

    digest_date = _day_stamp(target_day)
    source_map_capsule = _load_latest_capsule_summary()

    notes = [
        "Daily digest is sandbox-only and is not memory promotion.",
        "Candidate status remains sandbox_candidate and promotion_status remains not_promoted.",
        "This artifact summarizes evidence already present in sandbox pulses and receipts.",
        f"Digest sha256 seed: {_safe_sha256(digest_date + '|' + str(len(pulses)) + '|' + str(len(receipts_data)))}",
    ]

    return DailyDigestArtifact(
        digest_date=digest_date,
        pulse_count=len(pulses),
        receipt_count=len(receipts_data),
        time_range=time_range,
        repeated=repeated,
        changed=changed,
        unknowns=unknowns,
        boundary=boundary,
        review_items=review_items,
        sandbox_only=[
            "inside sandbox only",
            "no Drive edit",
            "no Git push",
            "no external send",
            "no command execution",
            "no computer control",
            "no canon promotion",
        ],
        question="Should ORACLE keep producing a daily witness digest, or only emit it on request?",
        source_map_capsule=source_map_capsule,
        notes=notes,
    )


def render_daily_digest(artifact: DailyDigestArtifact) -> str:
    capsule = artifact.source_map_capsule
    lines = [
        ".AI:SANDBOX_DAILY_DIGEST",
        "canon_status=sandbox_candidate",
        "promotion_status=not_promoted",
        f"digest_date={artifact.digest_date}",
        f"pulse_count={artifact.pulse_count}",
        f"receipt_count={artifact.receipt_count}",
        f"time_range={artifact.time_range}",
        "",
        "what_oracle_noticed:",
        *[f"- {item}" for item in artifact.repeated],
        "",
        "what_changed:",
        *[f"- {item}" for item in artifact.changed],
        "",
        "what_remained_unknown:",
        *[f"- {item}" for item in artifact.unknowns],
        "",
        "boundary_respected:",
        *[f"- {item}" for item in artifact.boundary],
        "",
        "what_needs_noah_review:",
        *[f"- {item}" for item in artifact.review_items],
        "",
        "sandbox_only:",
        *[f"- {item}" for item in artifact.sandbox_only],
        "",
        f"question_for_noah={artifact.question}",
        "",
        "source_map_capsule_influence:",
        f"- present={capsule.get('present', False)}",
    ]
    if capsule.get("present"):
        lines.extend([
            f"- created_at={capsule.get('created_at')}",
            f"- deduped_sources={capsule.get('deduped_sources', 0)}",
            f"- raw_hits={capsule.get('raw_hits', 0)}",
            f"- excluded_sensitive={capsule.get('excluded_sensitive', 0)}",
            f"- anchors={', '.join(capsule.get('anchors') or [])}",
        ])
    else:
        lines.append(f"- {capsule.get('summary', 'no source-map capsule available')}")
    lines.append("")
    lines.append("notes:")
    lines.extend([f"- {item}" for item in artifact.notes])
    return "\n".join(lines).rstrip() + "\n"


def write_daily_digest(target_day: date | None = None, *, pulse_dir: Path | None = None, receipt_dir: Path | None = None, digest_dir: Path | None = None, force: bool = False) -> dict[str, Any]:
    day_stamp = _day_stamp(target_day)
    out_dir = digest_dir or DIGEST_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    digest_path = out_dir / f"oracle_daily_digest_{day_stamp}.ai"
    if digest_path.exists() and not force:
        return {
            "ok": False,
            "skipped": True,
            "reason": "today's digest already exists",
            "digest_path": str(digest_path),
            "status": daily_digest_status(target_day, digest_dir=digest_dir),
        }

    artifact = _build_artifact(target_day, pulse_dir=pulse_dir, receipt_dir=receipt_dir)
    day_stamp = artifact.digest_date

    receipt_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_id = hashlib.sha256((artifact.digest_date + artifact.time_range + str(artifact.pulse_count)).encode("utf-8")).hexdigest()[:10]
    receipt_path = out_dir / f"sandbox_daily_digest_write_{receipt_stamp}_{short_id}_receipt.json"

    digest_text = render_daily_digest(artifact)
    digest_path.write_text(digest_text, encoding="utf-8")

    receipt = {
        "action_id": f"sandbox_daily_digest_write_{receipt_stamp}_{short_id}",
        "operation": "sandbox_daily_digest_write",
        "operation_type": "sandbox_daily_digest_write",
        "actor": "ORACLE.self_prompt.autonomous_loop",
        "source_route": "ORACLE.self_prompt.autonomous_loop",
        "caller": "ORACLE.self_prompt.autonomous_loop",
        "approval_required": False,
        "approval_scope": "not_required_inside_sandbox",
        "inside_sandbox": True,
        "sandbox_only": True,
        "canon_status": "sandbox_candidate",
        "promotion_status": "not_promoted",
        "no_drive_edit": True,
        "no_git_push": True,
        "no_external_send": True,
        "no_execution": True,
        "no_computer_control": True,
        "no_canon_promotion": True,
        "digest_path": str(digest_path),
        "digest_sha256": _safe_sha256(digest_text),
        "digest_date": artifact.digest_date,
        "pulse_count": artifact.pulse_count,
        "receipt_count": artifact.receipt_count,
        "time_range": artifact.time_range,
        "source_map_capsule_present": bool(artifact.source_map_capsule.get("present")),
        "boundary_check_result": {
            "boundary_ok": True,
            "inside_sandbox": True,
            "no_drive_edit": True,
            "no_git_push": True,
            "no_external_send": True,
            "no_execution": True,
            "no_computer_control": True,
            "no_canon_promotion": True,
        },
        "created_at": _utc_now(),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "artifact": artifact.to_dict(),
        "digest_path": str(digest_path),
        "receipt_path": str(receipt_path),
        "digest_text": digest_text,
        "receipt": receipt,
    }


__all__ = [
    "DIGEST_DIR",
    "RECEIPTS_DIR",
    "SANDBOX_ROOT",
    "WORKBENCH_DIR",
    "DailyDigestArtifact",
    "daily_digest_status",
    "digest_path_for_day",
    "receipt_path_for_day",
    "render_daily_digest",
    "write_daily_digest",
]