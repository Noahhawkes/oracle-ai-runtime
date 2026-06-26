from pathlib import Path
import os
import json
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

WORKSPACE_DIR = Path("./noah_exocortex").resolve()
VAULT_DIR = WORKSPACE_DIR / "vault" / "raw_artifacts"
LEDGER_DIR = WORKSPACE_DIR / ".oracle" / "ledger"
OPEN_HOLES_DIR = LEDGER_DIR / "open_holes"
LEDGER_FILE = LEDGER_DIR / "provenance_ledger.json"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def safe_join(base_dir: Path, user_path: str) -> Path:
    base = base_dir.resolve()
    target = (base / user_path).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError(f"Path traversal rejected: {user_path}")
    return target

def calculate_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_ledger() -> list:
    if not LEDGER_FILE.exists():
        return []
    try:
        with LEDGER_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        ts = utc_timestamp()
        backup_name = f"provenance_ledger.corrupt.{ts}.{uuid4().hex[:8]}.bak.json"
        backup_path = LEDGER_DIR / backup_name
        try:
            os.replace(str(LEDGER_FILE), str(backup_path))
        except OSError:
            pass
        return []

def write_ledger_atomic(records: list) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = LEDGER_DIR / f"provenance_ledger.tmp.{uuid4().hex}.json"
    try:
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(temp_file), str(LEDGER_FILE))
    except Exception:
        if temp_file.exists():
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise

def append_ledger(record: dict) -> None:
    ledger = load_ledger()
    ledger.insert(0, record)
    write_ledger_atomic(ledger)

def create_open_hole(
    hole_type: str,
    claim_or_action: str,
    expected_evidence: str,
    actual_result: str,
    source_path: str | None = None,
    severity: str = "medium",
    related_artifact_id: str | None = None,
) -> dict:
    OPEN_HOLES_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        hole_id = f"HOLE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
        hole_path = OPEN_HOLES_DIR / f"{hole_id}.json"
        if not hole_path.exists():
            break

    hole_record = {
        "hole_id": hole_id,
        "created_at": utc_now(),
        "hole_type": hole_type,
        "severity": severity,
        "status": "open",
        "related_artifact_id": related_artifact_id,
        "claim_or_action": claim_or_action,
        "expected_evidence": expected_evidence,
        "actual_result": actual_result,
        "source_path": source_path,
        "preserved_reason": "Missing or blocked evidence must remain explicit. Do not infer or reconstruct content.",
        "basis_label": "ABSENT_DATA_HOLE",
        "created_by": "ingestion_engine",
        "resolution_required_from": "Noah.Physical",
        "resolution_notes": [],
        "closed_at": None,
        "closure_receipt_id": None,
    }

    with hole_path.open("w", encoding="utf-8") as f:
        json.dump(hole_record, f, indent=2, ensure_ascii=False)

    receipt = {
        "receipt_id": f"RCPT-{uuid4().hex[:10].upper()}",
        "receipt_type": "open_hole_created",
        "created_at": utc_now(),
        "basis_label": "ABSENT_DATA_HOLE",
        "hole_id": hole_id,
        "hole_path": str(hole_path),
        "summary": f"OpenHole preserved: {hole_type}",
        "open_holes": [hole_id],
    }

    append_ledger(receipt)
    return hole_record

def ingest_raw_artifact(filename: str, source_path: str, author: str = "Noah.Physical") -> dict:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)

    try:
        target_path = safe_join(VAULT_DIR, filename)
    except PermissionError as e:
        return create_open_hole(
            hole_type="unsafe_target_path",
            claim_or_action=f"Attempted ingest target filename: {filename}",
            expected_evidence="Target path must remain inside vault/raw_artifacts",
            actual_result=str(e),
            source_path=source_path,
            severity="high",
        )

    source = Path(source_path)

    if not source.exists():
        return create_open_hole(
            hole_type="missing_source_file",
            claim_or_action=f"Attempted to ingest file: {source_path}",
            expected_evidence="Readable source file at provided source_path",
            actual_result="File not found",
            source_path=source_path,
            severity="medium",
        )

    if not source.is_file():
        return create_open_hole(
            hole_type="source_not_file",
            claim_or_action=f"Attempted to ingest source: {source_path}",
            expected_evidence="Source path must point to a file",
            actual_result="Source exists but is not a file",
            source_path=source_path,
            severity="medium",
        )

    raw_content = source.read_text(encoding="utf-8")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(raw_content, encoding="utf-8")

    file_hash = calculate_sha256(target_path)
    artifact_id = f"ART-{file_hash[:8].upper()}"

    receipt_record = {
        "receipt_id": f"RCPT-{uuid4().hex[:10].upper()}",
        "receipt_type": "raw_artifact_ingested",
        "artifact_id": artifact_id,
        "sha256": file_hash,
        "captured_at": utc_now(),
        "source_type": "session_log" if filename.endswith(".log") else "external_document",
        "source_path": str(source.resolve()),
        "vault_path": str(target_path),
        "author_claim": author,
        "custody_status": "Sovereign_Held",
        "basis_label": "CANDIDATE_SIGNAL",
        "canon_status": False,
        "transformation_chain": [],
        "summary": f"Ingested text block length: {len(raw_content)} characters.",
        "open_holes": [],
    }

    append_ledger(receipt_record)
    return receipt_record

def get_redink_status() -> dict:
    """Read-only RedInk custody status (Phase 1.2).

    Reads filesystem state ONLY. It must not ingest, write, delete, move,
    summarize, mutate, or promote canon. It deliberately does NOT call
    load_ledger() because that function renames a corrupt ledger; here we read
    the ledger non-destructively instead.
    """
    ledger_exists = LEDGER_FILE.exists()
    records: list = []
    if ledger_exists:
        try:
            with LEDGER_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                records = data
        except Exception:
            records = []  # do NOT back up / rename here — read-only

    # Ledger is newest-first (records are inserted at index 0).
    last_receipt_id = records[0].get("receipt_id") if records else None
    last_artifact_id = next((r["artifact_id"] for r in records if r.get("artifact_id")), None)
    last_open_hole_id = next((r["hole_id"] for r in records if r.get("hole_id")), None)

    open_hole_count = 0
    if OPEN_HOLES_DIR.exists():
        open_hole_count = sum(1 for p in OPEN_HOLES_DIR.glob("*.json") if p.is_file())

    vault_raw_artifact_count = 0
    if VAULT_DIR.exists():
        vault_raw_artifact_count = sum(1 for p in VAULT_DIR.iterdir() if p.is_file())

    return {
        "status": "ok",
        "redink_phase": "1.2",
        "ledger_exists": ledger_exists,
        "ledger_record_count": len(records),
        "open_hole_count": open_hole_count,
        "vault_raw_artifact_count": vault_raw_artifact_count,
        "last_receipt_id": last_receipt_id,
        "last_artifact_id": last_artifact_id,
        "last_open_hole_id": last_open_hole_id,
        "workspace_root": str(WORKSPACE_DIR),
        "mutation_performed": False,
        "basis_label": "RUNTIME_REPORTED",
    }
