r"""Create a dry-run ORACLE migration plan from the storage census.

This is a planning tool only. It does not copy, move, delete, rename, upload,
sync, or ingest file contents. The active runtime policy is intentionally
conservative: keep the live runtime on C:\Oracle\ORACLE.AI-runtime and treat
Google Drive as archive/mirror/document storage, not as the process root.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OFFICIAL_RUNTIME = Path(r"C:\Oracle\ORACLE.AI-runtime")
OFFICIAL_STATE = Path(r"C:\Oracle\state")
DEFAULT_MANIFEST = OFFICIAL_STATE / "storage" / "storage_census_latest.json"
DEFAULT_OUT_DIR = OFFICIAL_STATE / "migration"
DEFAULT_INTAKE_PARENT = Path(r"C:\Oracle\migration_intake")
FORBIDDEN_RUNTIME_ROOTS = (
    Path(r"C:\ORACLE.AI"),
    Path(r"G:\My Drive\HawkesNest LLC\ORACLE.AI"),
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def under(path: Path | str, root: Path | str) -> bool:
    path_norm = norm(path)
    root_norm = norm(root).rstrip("\\/")
    return path_norm == root_norm or path_norm.startswith(root_norm + os.sep)


def source_key(path: Path) -> str:
    text = str(path)
    upper = text.upper()
    if upper.startswith("G:"):
        return "G_drive"
    if "OneDrive" in text:
        return "OneDrive"
    if upper.startswith(r"C:\ORACLE.AI"):
        return "C_ORACLE_AI_legacy"
    if upper.startswith(r"C:\ORACLE"):
        return "C_Oracle"
    drive = path.drive.replace(":", "") or "unknown"
    return f"{drive}_other"


def rel_for(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except Exception:
        drive = path.drive.replace(":", "") or "root"
        parts = [part for part in path.parts if part not in (path.drive, path.drive + "\\")]
        return Path(drive, *parts)


def classify_action(entry: dict[str, Any], path: Path) -> tuple[str, str, bool]:
    risks = set(entry.get("risk_flags") or [])
    classification = entry.get("classification")
    if "credential_risk" in risks or classification == "credential_risk":
        return (
            "credential_review_only",
            "Credential-risk path/name. Count and review only; no bulk copy or cut.",
            False,
        )
    if under(path, OFFICIAL_RUNTIME):
        return "already_official_runtime", "Already inside active official runtime; keep in place.", False
    if under(path, OFFICIAL_STATE):
        return "already_official_state", "Already inside official C:\\Oracle state; keep in place.", False
    if any(under(path, root) for root in FORBIDDEN_RUNTIME_ROOTS):
        return (
            "copy_legacy_runtime_to_intake_do_not_run",
            "Legacy or Drive runtime root. Archive/copy only; do not run active runtime here.",
            True,
        )
    if under(path, Path(r"C:\Oracle")):
        return "already_c_oracle_review", "Already under C:\\Oracle but outside active runtime/state; review before moving.", False
    return "candidate_copy_to_intake", "ORACLE-related file outside official runtime; copy-first migration candidate.", True


def build_plan(manifest: dict[str, Any], intake_root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for entry in manifest.get("entries", []):
        if not entry.get("oracle_related"):
            continue
        path = Path(entry["path"])
        action, reason, needs_target = classify_action(entry, path)
        target = None
        if needs_target:
            source_root = Path(entry.get("root") or path.anchor)
            target = intake_root / source_key(path) / rel_for(path, source_root)
        risks = set(entry.get("risk_flags") or [])
        entries.append(
            {
                "source_path": str(path),
                "source_root": entry.get("root"),
                "classification": entry.get("classification"),
                "size_bytes": entry.get("size_bytes"),
                "modified": entry.get("modified"),
                "risk_flags": entry.get("risk_flags") or [],
                "duplicate_candidate": "duplicate_candidate" in risks,
                "action": action,
                "reason": reason,
                "planned_target": str(target) if target else None,
                "delete_source_after_copy": False,
            }
        )

    counts = Counter(item["action"] for item in entries)
    by_root = Counter(item["source_root"] for item in entries)
    by_classification = Counter(item["classification"] for item in entries)
    planned_copy_bytes = sum(item.get("size_bytes") or 0 for item in entries if item["planned_target"])
    media_ext = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".flac", ".m4a"}
    archive_ext = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
    planned = [item for item in entries if item["planned_target"]]
    phase1 = [
        item for item in planned
        if Path(item["source_path"]).suffix.lower() not in media_ext | archive_ext
    ]
    media = [item for item in planned if Path(item["source_path"]).suffix.lower() in media_ext]
    archives = [item for item in planned if Path(item["source_path"]).suffix.lower() in archive_ext]

    def phase_count(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "entries": len(items),
            "bytes": sum(item.get("size_bytes") or 0 for item in items),
        }

    return {
        "schema_version": 1,
        "kind": "oracle_migration_plan",
        "created_at": utc_now(),
        "source_census_id": manifest.get("census_id"),
        "official_runtime_root": str(OFFICIAL_RUNTIME),
        "official_state_root": str(OFFICIAL_STATE),
        "recommended_active_runtime_policy": (
            r"Keep active runtime on C:\Oracle\ORACLE.AI-runtime. "
            r"Use G:\ only for backup/archive/docs, not live runtime."
        ),
        "planned_intake_root": str(intake_root),
        "cut_paste_policy": (
            "copy-first, verify hashes/size/counts, then explicit Noah approval "
            "before deleting or moving any source"
        ),
        "safety": {
            "no_files_copied": True,
            "no_files_moved": True,
            "no_files_deleted": True,
            "no_cloud_mutation": True,
            "credential_risk_bulk_copy_blocked": True,
        },
        "counts": {
            "oracle_related_entries": len(entries),
            "planned_copy_entries": sum(1 for item in entries if item["planned_target"]),
            "planned_copy_bytes": planned_copy_bytes,
            "by_action": dict(counts),
            "by_root": dict(by_root),
            "by_classification": dict(by_classification),
        },
        "phase_recommendations": {
            "phase_1_copy_nonmedia_nonarchive": {
                **phase_count(phase1),
                "policy": "copy first to C:\\Oracle\\migration_intake; verify before any source cleanup",
            },
            "phase_2_review_media": {
                **phase_count(media),
                "policy": "do not copy to C: until space/duplicate policy is chosen; keep cloud/archive source authoritative for now",
            },
            "phase_3_review_archives": {
                **phase_count(archives),
                "policy": "review archives for duplicates before copying",
            },
        },
        "entries": entries,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    counts = plan["counts"]
    lines = [
        "# ORACLE Migration Plan",
        f"Created: {plan['created_at']}",
        "",
        "## Recommendation",
        r"- Keep the active runtime on `C:\Oracle\ORACLE.AI-runtime`.",
        r"- Treat `G:\` / Google Drive as archive, mirror, and document storage only.",
        "- Use copy-first migration. Do not cut/delete sources until copy verification passes and Noah approves.",
        "",
        "## Counts",
        f"- ORACLE-related entries: {counts['oracle_related_entries']}",
        f"- Planned copy/archive candidates: {counts['planned_copy_entries']}",
        f"- Planned copy bytes: {counts['planned_copy_bytes']}",
        "",
        "## Recommended Phases",
    ]
    for key, value in plan["phase_recommendations"].items():
        gib = value["bytes"] / 1024**3
        lines.append(f"- `{key}`: {value['entries']} entries, {gib:.2f} GiB. {value['policy']}")
    lines.extend([
        "",
        "## By Action",
    ])
    for key, value in Counter(counts["by_action"]).most_common():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## By Root"])
    for key, value in Counter(counts["by_root"]).most_common():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Safety", "- No files copied.", "- No files moved.", "- No files deleted.", "- Credential-risk entries are review-only."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create dry-run ORACLE migration plan")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--intake-parent", default=str(DEFAULT_INTAKE_PARENT))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    out_dir = Path(args.out_dir)
    stamp = utc_stamp()
    intake_root = Path(args.intake_parent) / f"oracle_sprawl_{stamp}"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = build_plan(manifest, intake_root)
    plan["source_census"] = str(manifest_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / f"oracle_migration_plan_{stamp}.json"
    latest_path = out_dir / "oracle_migration_plan_latest.json"
    md_path = out_dir / f"oracle_migration_plan_{stamp}.md"
    latest_md = out_dir / "oracle_migration_plan_latest.md"

    payload = json.dumps(plan, indent=2, ensure_ascii=True)
    plan_path.write_text(payload + "\n", encoding="utf-8")
    latest_path.write_text(payload + "\n", encoding="utf-8")
    markdown = render_markdown(plan)
    md_path.write_text(markdown, encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")

    print(json.dumps({
        "plan_path": str(plan_path),
        "latest_path": str(latest_path),
        "md_path": str(md_path),
        "latest_md": str(latest_md),
        "counts": plan["counts"],
    }, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
