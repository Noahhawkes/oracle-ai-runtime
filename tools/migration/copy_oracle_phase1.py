r"""Copy Phase 1 ORACLE migration candidates.

Copy-only executor for the migration plan produced by
create_oracle_migration_plan.py. This script intentionally does not delete,
move, rename, sync, upload, commit, or activate any runtime from cloud storage.

Phase 1 means: planned copy targets excluding media, archives, and credential
risk entries. Each copied file is verified by size and sha256 and recorded in a
JSONL receipt so the operation is resumable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN_PATH = Path(r"C:\Oracle\state\migration\oracle_migration_plan_latest.json")
RECEIPT_DIR = Path(r"C:\Oracle\state\migration")
DEFAULT_MIN_FREE_AFTER_BYTES = 10 * 1024**3

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".flac", ".m4a"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
BLOCKED_ACTIONS = {"credential_review_only"}


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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_with_source_hash(source: Path, temp_target: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    temp_target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, temp_target.open("wb") as dst:
        for chunk in iter(lambda: src.read(chunk_size), b""):
            h.update(chunk)
            dst.write(chunk)
    shutil.copystat(source, temp_target, follow_symlinks=True)
    return h.hexdigest()


def phase1_entries(plan: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for entry in plan.get("entries", []):
        target = entry.get("planned_target")
        if not target:
            continue
        if entry.get("action") in BLOCKED_ACTIONS:
            continue
        suffix = Path(entry["source_path"]).suffix.lower()
        if suffix in MEDIA_EXT or suffix in ARCHIVE_EXT:
            continue
        entries.append(entry)
    return entries


def read_existing_receipt(receipt_path: Path) -> set[str]:
    done: set[str] = set()
    if not receipt_path.exists():
        return done
    for line in receipt_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("status") in {"copied_verified", "already_verified"}:
            done.add(str(row.get("source_path", "")))
    return done


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def validate_targets(entries: list[dict[str, Any]], intake_root: Path) -> None:
    for entry in entries:
        target = Path(entry["planned_target"])
        if not under(target, intake_root):
            raise RuntimeError(f"Refusing target outside intake root: {target}")
        source = Path(entry["source_path"])
        if under(source, intake_root):
            raise RuntimeError(f"Refusing source already inside intake root: {source}")


def bytes_to_copy(entries: list[dict[str, Any]], skip_sources: set[str]) -> int:
    total = 0
    for entry in entries:
        if str(entry["source_path"]) in skip_sources:
            continue
        target = Path(entry["planned_target"])
        source_size = int(entry.get("size_bytes") or 0)
        if target.exists() and target.is_file() and target.stat().st_size == source_size:
            continue
        total += source_size
    return total


def drive_free_bytes(path: Path) -> int:
    usage = shutil.disk_usage(str(path.anchor or path.parent))
    return int(usage.free)


def run(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan)
    plan = load_json(plan_path)
    intake_root = Path(plan["planned_intake_root"])
    entries = phase1_entries(plan)
    validate_targets(entries, intake_root)

    stamp = utc_stamp()
    receipt_path = Path(args.receipt) if args.receipt else RECEIPT_DIR / f"phase1_copy_receipt_{stamp}.jsonl"
    summary_path = RECEIPT_DIR / f"phase1_copy_summary_{stamp}.json"
    latest_summary_path = RECEIPT_DIR / "phase1_copy_summary_latest.json"

    completed_sources = read_existing_receipt(receipt_path)
    planned_bytes = sum(int(entry.get("size_bytes") or 0) for entry in entries)
    remaining_bytes = bytes_to_copy(entries, completed_sources)
    free_before = drive_free_bytes(intake_root)
    min_free_after = int(args.min_free_after_gib * 1024**3)

    preflight = {
        "ts_utc": utc_now(),
        "plan_path": str(plan_path),
        "intake_root": str(intake_root),
        "receipt_path": str(receipt_path),
        "phase": "phase_1_copy_nonmedia_nonarchive",
        "entries": len(entries),
        "planned_bytes": planned_bytes,
        "remaining_bytes": remaining_bytes,
        "free_before": free_before,
        "min_free_after": min_free_after,
        "execute": bool(args.execute),
        "safety": {
            "copy_only": True,
            "no_source_delete": True,
            "no_source_move": True,
            "no_cloud_activation": True,
            "credential_risk_excluded": True,
            "media_excluded": True,
            "archives_excluded": True,
        },
    }

    print(json.dumps({"preflight": preflight}, indent=2, ensure_ascii=True), flush=True)
    if not args.execute:
        return 0
    if free_before - remaining_bytes < min_free_after:
        print("BLOCKED: insufficient free space after safety reserve.", file=sys.stderr, flush=True)
        return 2

    intake_root.mkdir(parents=True, exist_ok=True)
    counters = {
        "copied_verified": 0,
        "already_verified": 0,
        "missing_source": 0,
        "target_conflict": 0,
        "copy_failed": 0,
        "verify_failed": 0,
        "skipped_receipted": 0,
    }
    copied_bytes = 0
    started = time.time()

    for index, entry in enumerate(entries, start=1):
        source = Path(entry["source_path"])
        target = Path(entry["planned_target"])
        source_str = str(source)
        base_row = {
            "ts_utc": utc_now(),
            "index": index,
            "total": len(entries),
            "source_path": source_str,
            "target_path": str(target),
            "size_bytes": int(entry.get("size_bytes") or 0),
            "classification": entry.get("classification"),
            "action": entry.get("action"),
        }

        if source_str in completed_sources:
            counters["skipped_receipted"] += 1
            continue

        try:
            if not source.exists() or not source.is_file():
                counters["missing_source"] += 1
                append_jsonl(receipt_path, {**base_row, "status": "missing_source"})
                continue

            source_size = source.stat().st_size
            if target.exists():
                if target.is_file() and target.stat().st_size == source_size:
                    source_hash = sha256_file(source)
                    target_hash = sha256_file(target)
                    if source_hash == target_hash:
                        counters["already_verified"] += 1
                        append_jsonl(
                            receipt_path,
                            {
                                **base_row,
                                "status": "already_verified",
                                "source_sha256": source_hash,
                                "target_sha256": target_hash,
                            },
                        )
                        completed_sources.add(source_str)
                    else:
                        counters["target_conflict"] += 1
                        append_jsonl(receipt_path, {**base_row, "status": "target_conflict_hash_mismatch"})
                    continue
                counters["target_conflict"] += 1
                append_jsonl(receipt_path, {**base_row, "status": "target_conflict_exists"})
                continue

            temp_target = target.with_name(target.name + f".partial_{os.getpid()}")
            try:
                source_hash = copy_with_source_hash(source, temp_target)
                temp_size = temp_target.stat().st_size
                if temp_size != source_size:
                    counters["verify_failed"] += 1
                    append_jsonl(
                        receipt_path,
                        {**base_row, "status": "verify_failed_size", "source_size_actual": source_size, "temp_size": temp_size},
                    )
                    try:
                        temp_target.unlink()
                    except Exception:
                        pass
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temp_target.replace(target)
                target_hash = sha256_file(target)
                if target_hash != source_hash or target.stat().st_size != source_size:
                    counters["verify_failed"] += 1
                    append_jsonl(
                        receipt_path,
                        {
                            **base_row,
                            "status": "verify_failed_hash",
                            "source_sha256": source_hash,
                            "target_sha256": target_hash,
                            "source_size_actual": source_size,
                            "target_size": target.stat().st_size,
                        },
                    )
                    continue
                counters["copied_verified"] += 1
                copied_bytes += source_size
                completed_sources.add(source_str)
                append_jsonl(
                    receipt_path,
                    {
                        **base_row,
                        "status": "copied_verified",
                        "source_sha256": source_hash,
                        "target_sha256": target_hash,
                        "source_size_actual": source_size,
                        "target_size": target.stat().st_size,
                    },
                )
            except Exception as exc:
                counters["copy_failed"] += 1
                append_jsonl(receipt_path, {**base_row, "status": "copy_failed", "error": f"{type(exc).__name__}: {exc}"})
                try:
                    if temp_target.exists():
                        temp_target.unlink()
                except Exception:
                    pass
        finally:
            if index == 1 or index % args.progress_every == 0:
                elapsed = max(time.time() - started, 0.001)
                print(
                    json.dumps(
                        {
                            "progress": {
                                "index": index,
                                "total": len(entries),
                                "copied_verified": counters["copied_verified"],
                                "already_verified": counters["already_verified"],
                                "errors": counters["missing_source"] + counters["copy_failed"] + counters["verify_failed"] + counters["target_conflict"],
                                "copied_gib": round(copied_bytes / 1024**3, 3),
                                "elapsed_seconds": round(elapsed, 1),
                            }
                        },
                        ensure_ascii=True,
                    ),
                    flush=True,
                )

    free_after = drive_free_bytes(intake_root)
    summary = {
        **preflight,
        "completed_at": utc_now(),
        "elapsed_seconds": round(time.time() - started, 3),
        "free_after": free_after,
        "counters": counters,
        "copied_bytes": copied_bytes,
        "receipt_path": str(receipt_path),
        "summary_path": str(summary_path),
        "safe_for_source_cleanup": False,
        "source_cleanup_requires_explicit_noah_approval": True,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    latest_summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary}, indent=2, ensure_ascii=True), flush=True)
    return 0 if counters["copy_failed"] == 0 and counters["verify_failed"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy ORACLE migration Phase 1 candidates")
    parser.add_argument("--plan", default=str(PLAN_PATH))
    parser.add_argument("--receipt", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--min-free-after-gib", type=float, default=10.0)
    parser.add_argument("--progress-every", type=int, default=250)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
