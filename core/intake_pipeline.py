"""core/intake_pipeline.py — Governed ORACLE file ingestion (read-only, copy+manifest).

Consolidates discovered ORACLE/SOV1 files into the active runtime root WITHOUT
moving, deleting, overwriting, or modifying any original. Files are *copied* into
an intake staging zone and every candidate is recorded in a manifest. Nothing is
promoted into canonical runtime folders until Noah.Physical approves it through
the Guard approval lane.

Hard guarantees (see the task doctrine):
  1. No move / delete / overwrite / modify of originals.
  2. No raw content ingested into memory.
  3. Secrets (.env, keys, tokens, credentials, browser profiles, private config)
     are flagged by PATH and TYPE only — never copied, never printed.
  4. All staged files land ONLY under intake/staging and get a manifest entry.
  5. Idempotent: the same SHA-256 never stages twice.
  6. No network calls. No destructive operations.

Layout (created by the bootstrap step):
  intake/staging      copied safe candidates
  intake/manifests    per-run manifests + staged index + pending promotions
  intake/quarantine   reserved for rejected/secret items (never auto-filled with content)
  intake/approved     promotion target after Guard approval (copy, not move)
  Memory/source_maps  condensed source maps
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable

# ── Paths ───────────────────────────────────────────────────────────────────
RUNTIME_ROOT = Path(__file__).resolve().parent.parent
INTAKE = RUNTIME_ROOT / "intake"
STAGING = INTAKE / "staging"
MANIFESTS = INTAKE / "manifests"
QUARANTINE = INTAKE / "quarantine"
APPROVED = INTAKE / "approved"
SOURCE_MAPS = RUNTIME_ROOT / "Memory" / "source_maps"

DEFAULT_SCAN_FILE = RUNTIME_ROOT / "oracle_content_scan.txt"
STAGED_INDEX = MANIFESTS / "staged_index.json"
PENDING_PROMOTIONS = MANIFESTS / "pending_promotions.json"
LATEST_MANIFEST = MANIFESTS / "intake_manifest_latest.json"

# ── Bounds (keeps a run from blind-copying gigabytes) ────────────────────────
MAX_STAGE_BYTES = 25 * 1024 * 1024        # per-file ceiling for auto-staging
STAGE_BUDGET_BYTES = 250 * 1024 * 1024    # total bytes staged per run
STALE_DAYS = 540                          # ~18 months → "stale"

# ── Classifications ──────────────────────────────────────────────────────────
RUNTIME_CODE = "runtime_code"
LOCAL_STATE = "local_state"
DRIVE_DOCTRINE = "drive_doctrine"
SNAPSHOT = "snapshot"
DUPLICATE = "duplicate"
STALE = "stale"
SECRET_RISK = "secret_risk"
UNKNOWN = "unknown"

# ── Ingest statuses ──────────────────────────────────────────────────────────
ST_STAGED = "staged"
ST_DUPLICATE = "duplicate_skipped"
ST_SECRET = "secret_flagged"
ST_LARGE = "deferred_large"
ST_BUDGET = "deferred_budget"
ST_CLOUD_STUB = "cloud_stub_skipped"
ST_MISSING = "missing"
ST_ERROR = "error"
ST_SKIPPED_SELF = "skipped_self"
ST_CLOUD_DEFERRED = "deferred_cloud"

# Cloud-backed mounts: hashing/copying these would trigger downloads (network).
# Deferred by default to honor the "no network calls" rule; opt in explicitly.
CLOUD_DRIVES = frozenset({"G:"})

# Same keyword set used by the discovery scan.
SCAN_KEYWORDS = (
    "oracle", "sov1", "sovereign", "miracledrive", "mirrorgpt", "flamecard",
    "flameanchor", "noah_eternal", "noaheternal", "hydra_stack", "rendered_reality",
    "recursive_identity", "noahai",
)

# Google-native cloud stubs: pointers, not real bytes.
_CLOUD_STUB_EXT = {".gdoc", ".gsheet", ".gslides", ".gprj", ".gdraw", ".gform", ".gmap", ".gsite"}

# ── Secret detection (PATH + TYPE only — never content) ──────────────────────
_SECRET_EXACT_NAMES = {
    ".env", "credentials.json", "credentials", "secrets.json", "secrets.yaml",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".netrc", ".pgpass",
    "login data", "web data", "cookies", "key3.db", "key4.db", "logins.json",
}
_SECRET_NAME_SUBSTR = (
    "secret", "credential", "password", "passwd", "apikey", "api_key",
    "token", "private_key", "privatekey",
)
_SECRET_EXT = {
    ".pem", ".key", ".pfx", ".p12", ".keystore", ".jks", ".ovpn", ".asc",
    ".gpg", ".kdbx",
}
_SECRET_PATH_SUBSTR = (
    "\\.ssh\\", "/.ssh/", "\\.aws\\", "/.aws/", "\\.gnupg\\", "/.gnupg/",
    "\\user data\\", "/user data/", "\\appdata\\local\\google\\chrome",
    "\\appdata\\roaming\\mozilla", "\\microsoft\\edge\\user data",
    "\\.config\\google-chrome", "\\.mozilla\\",
)


def secret_risk_for(path: str) -> str | None:
    """Return a secret risk *type* if the path looks like a secret, else None.

    Operates on the path string only — the file is never opened or read.
    """
    p = path.lower().replace("/", "\\")
    name = p.rsplit("\\", 1)[-1]
    ext = ("." + name.rsplit(".", 1)[-1]) if "." in name else ""

    if name in _SECRET_EXACT_NAMES:
        return f"secret_file:{name}"
    if name == ".env" or name.startswith(".env."):
        return "dotenv"
    if ext in _SECRET_EXT:
        return f"key_material:{ext}"
    for s in _SECRET_NAME_SUBSTR:
        if s in name:
            return f"secret_name:{s}"
    for s in _SECRET_PATH_SUBSTR:
        if s in p:
            return "browser_or_credential_store"
    return None


# ── Manifest entry ───────────────────────────────────────────────────────────
@dataclass
class IntakeEntry:
    original_path: str
    source_drive: str
    filename: str
    size_bytes: int
    modified_time: str
    sha256: str
    keyword_matches: list[str]
    classification: str
    staged_path: str
    ingest_status: str
    reason: str


# ── Small JSON helpers ───────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_dirs() -> dict[str, str]:
    """Create/verify the intake scaffold. Returns {abs_path: 'created'|'exists'}."""
    out: dict[str, str] = {}
    for d in (STAGING, MANIFESTS, QUARANTINE, APPROVED, SOURCE_MAPS):
        existed = d.exists()
        if not existed:
            d.mkdir(parents=True, exist_ok=True)
        out[str(d)] = "exists" if existed else "created"
    return out


# ── Scan-file parser ─────────────────────────────────────────────────────────
_FILE_LINE = re.compile(r"^(?P<path>.+?)\t(?P<date>\d{4}-\d{2}-\d{2})\t(?P<bytes>\d+) bytes\s*$")


def parse_scan_file(scan_file: Path = DEFAULT_SCAN_FILE) -> list[dict[str, Any]]:
    """Parse oracle_content_scan.txt into file records. Read-only."""
    records: list[dict[str, Any]] = []
    if not scan_file.exists():
        return records
    text = scan_file.read_text(encoding="utf-8", errors="replace")
    in_files = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--- Files ---"):
            in_files = True
            continue
        if stripped.startswith("--- Directories ---") or stripped.startswith("=========="):
            in_files = False
            continue
        if not in_files:
            continue
        m = _FILE_LINE.match(line)
        if not m:
            continue
        records.append({
            "path": m.group("path").strip(),
            "modified_date": m.group("date"),
            "size_bytes": int(m.group("bytes")),
        })
    return records


def _source_drive(path: str) -> str:
    p = path.replace("/", "\\")
    if len(p) >= 2 and p[1] == ":":
        return p[0].upper() + ":"
    if p.startswith("\\\\"):
        return "UNC"
    return "UNKNOWN"


def _keyword_matches(path: str) -> list[str]:
    low = path.lower()
    return [k for k in SCAN_KEYWORDS if k.replace("_", "") in low.replace("_", "")]


def _classify(path: str, size_bytes: int, mtime: datetime | None, *, secret: str | None) -> str:
    if secret:
        return SECRET_RISK
    name = path.lower().replace("/", "\\").rsplit("\\", 1)[-1]
    ext = ("." + name.rsplit(".", 1)[-1]) if "." in name else ""

    if ext in _CLOUD_STUB_EXT:
        return DRIVE_DOCTRINE
    if ext in {".zip", ".bundle", ".tar", ".gz", ".tgz", ".7z", ".rar", ".bak"} or "backup" in name or "snapshot" in name:
        return SNAPSHOT
    if ext in {".py", ".js", ".ts", ".tsx", ".jsx", ".swift", ".java", ".c", ".cpp", ".h", ".sh", ".bat", ".ps1", ".rb", ".go"}:
        return RUNTIME_CODE
    if ext in {".db", ".sqlite", ".sqlite3", ".log", ".jsonl"} or "\\state\\" in path.lower() or "receipt" in name:
        return LOCAL_STATE
    if ext in {".md", ".txt", ".pdf", ".doc", ".docx", ".rtf", ".odt"} or ext in _CLOUD_STUB_EXT:
        return DRIVE_DOCTRINE
    if mtime is not None:
        age = datetime.now(timezone.utc) - mtime
        if age > timedelta(days=STALE_DAYS):
            return STALE
    return UNKNOWN


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _under(path: str, base: Path) -> bool:
    try:
        Path(path).resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


# ── Core build ───────────────────────────────────────────────────────────────
def build_intake(
    scan_file: Path = DEFAULT_SCAN_FILE,
    *,
    max_files: int | None = None,
    stage_budget_bytes: int = STAGE_BUDGET_BYTES,
    max_stage_bytes: int = MAX_STAGE_BYTES,
    include_cloud: bool = False,
) -> dict[str, Any]:
    """Read the scan, build the governed manifest, stage safe candidates.

    Idempotent: a SHA-256 already present in the staged index is never staged
    again. Returns a summary dict (also written to a per-run manifest).
    """
    ensure_dirs()
    records = parse_scan_file(scan_file)
    if max_files is not None:
        records = records[:max_files]

    staged_index: dict[str, str] = _read_json(STAGED_INDEX, {})
    pending: list[dict[str, Any]] = _read_json(PENDING_PROMOTIONS, [])
    pending_ids = {p.get("sha256") for p in pending if isinstance(p, dict)}

    entries: list[IntakeEntry] = []
    budget_used = 0

    for rec in records:
        path = rec["path"]
        size = int(rec["size_bytes"])
        drive = _source_drive(path)
        name = path.replace("/", "\\").rsplit("\\", 1)[-1]
        kw = _keyword_matches(path)
        try:
            mtime = datetime.fromisoformat(rec["modified_date"]).replace(tzinfo=timezone.utc)
        except Exception:
            mtime = None
        mtime_str = rec.get("modified_date", "")

        # Never re-ingest the active runtime repo or the intake zone itself.
        if _under(path, RUNTIME_ROOT):
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, "", kw,
                                       RUNTIME_CODE, "", ST_SKIPPED_SELF,
                                       "inside active runtime root — already canonical"))
            continue

        secret = secret_risk_for(path)
        cls = _classify(path, size, mtime, secret=secret)

        # Secret: flag by path+type ONLY. Never hash, never open, never copy.
        if secret:
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, "", kw,
                                       SECRET_RISK, "", ST_SECRET,
                                       f"secret risk ({secret}); flagged by path/type only — not copied or read"))
            continue

        # Cloud-backed drive: defer (no hash/copy) so no download/network occurs.
        if drive in CLOUD_DRIVES and not include_cloud:
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, "", kw,
                                       cls, "", ST_CLOUD_DEFERRED,
                                       "cloud-backed drive; deferred to avoid download/network (pass include_cloud to override)"))
            continue

        ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
        if ext in _CLOUD_STUB_EXT:
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, "", kw,
                                       DRIVE_DOCTRINE, "", ST_CLOUD_STUB,
                                       "Google-native cloud stub — pointer only, must be exported not copied"))
            continue

        src = Path(path)
        if not src.exists():
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, "", kw,
                                       cls, "", ST_MISSING, "original not found at scan-time path"))
            continue

        if size > max_stage_bytes:
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, "", kw,
                                       cls, "", ST_LARGE,
                                       f"exceeds per-file stage ceiling ({max_stage_bytes} bytes); recorded, not staged"))
            continue

        # Hashing reads bytes to fingerprint; content is NOT stored in memory.
        try:
            digest = _sha256(src)
        except Exception as exc:
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, "", kw,
                                       cls, "", ST_ERROR, f"hash failed: {type(exc).__name__}: {exc}"))
            continue

        # Idempotent dedupe by SHA-256.
        if digest in staged_index and (STAGING / staged_index[digest]).exists():
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, digest, kw,
                                       DUPLICATE, str(STAGING / staged_index[digest]), ST_DUPLICATE,
                                       "identical SHA-256 already staged"))
            continue

        if budget_used + size > stage_budget_bytes:
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, digest, kw,
                                       cls, "", ST_BUDGET,
                                       f"per-run stage budget reached ({stage_budget_bytes} bytes); rerun to continue"))
            continue

        # Stage by COPY (never move). Collision-proof name keyed by hash.
        staged_name = f"{digest[:16]}__{name}"
        dest = STAGING / staged_name
        try:
            shutil.copy2(src, dest)   # copy2 preserves mtime; original untouched
        except Exception as exc:
            entries.append(IntakeEntry(path, drive, name, size, mtime_str, digest, kw,
                                       cls, "", ST_ERROR, f"copy failed: {type(exc).__name__}: {exc}"))
            continue

        budget_used += size
        staged_index[digest] = staged_name
        entries.append(IntakeEntry(path, drive, name, size, mtime_str, digest, kw,
                                   cls, str(dest), ST_STAGED, "copied to staging; awaiting Guard approval"))

        if digest not in pending_ids:
            pending.append({
                "sha256": digest,
                "original_path": path,
                "staged_path": str(dest),
                "filename": name,
                "classification": cls,
                "status": "pending",
                "created_at": _now(),
            })
            pending_ids.add(digest)

    # Persist state.
    _write_json(STAGED_INDEX, staged_index)
    _write_json(PENDING_PROMOTIONS, pending)

    summary = _summarize(entries)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {
        "manifest_version": "1.0",
        "built_at": _now(),
        "scan_file": str(scan_file),
        "runtime_root": str(RUNTIME_ROOT),
        "bounds": {
            "max_stage_bytes": max_stage_bytes,
            "stage_budget_bytes": stage_budget_bytes,
            "stale_days": STALE_DAYS,
        },
        "summary": summary,
        "entries": [asdict(e) for e in entries],
    }
    manifest_path = MANIFESTS / f"intake_manifest_{stamp}.json"
    _write_json(manifest_path, manifest)
    _write_json(LATEST_MANIFEST, manifest)
    _write_source_map(summary, stamp)

    summary["manifest_path"] = str(manifest_path)
    summary["pending_promotions"] = len([p for p in pending if p.get("status") == "pending"])
    return summary


def _summarize(entries: list[IntakeEntry]) -> dict[str, Any]:
    by_class: dict[str, int] = {}
    by_status: dict[str, int] = {}
    staged_bytes = 0
    for e in entries:
        by_class[e.classification] = by_class.get(e.classification, 0) + 1
        by_status[e.ingest_status] = by_status.get(e.ingest_status, 0) + 1
        if e.ingest_status == ST_STAGED:
            staged_bytes += e.size_bytes
    return {
        "total_candidates": len(entries),
        "by_classification": by_class,
        "by_ingest_status": by_status,
        "staged_bytes": staged_bytes,
        "secret_flagged": by_status.get(ST_SECRET, 0),
    }


def _write_source_map(summary: dict[str, Any], stamp: str) -> None:
    source_map = {
        "generated_at": _now(),
        "summary": summary,
        "note": "Condensed intake source map. No raw file contents are stored here.",
    }
    _write_json(SOURCE_MAPS / f"intake_source_map_{stamp}.json", source_map)
    _write_json(SOURCE_MAPS / "intake_source_map_latest.json", source_map)


# ── Promotion (post-approval, copy not move) ─────────────────────────────────
def list_pending_promotions() -> list[dict[str, Any]]:
    return [p for p in _read_json(PENDING_PROMOTIONS, []) if isinstance(p, dict) and p.get("status") == "pending"]


def promote(sha256: str, *, approved_by: str = "noah") -> dict[str, Any]:
    """Promote one staged file into intake/approved by COPY after Guard approval.

    Never moves or deletes the staged copy or the original. Idempotent.
    """
    pending = _read_json(PENDING_PROMOTIONS, [])
    for entry in pending:
        if isinstance(entry, dict) and entry.get("sha256") == sha256:
            staged = Path(entry.get("staged_path", ""))
            if not staged.exists():
                return {"ok": False, "sha256": sha256, "error": "staged file missing"}
            dest = APPROVED / staged.name
            if not dest.exists():
                shutil.copy2(staged, dest)
            entry["status"] = "approved"
            entry["approved_by"] = approved_by
            entry["approved_at"] = _now()
            entry["approved_path"] = str(dest)
            _write_json(PENDING_PROMOTIONS, pending)
            return {"ok": True, "sha256": sha256, "approved_path": str(dest)}
    return {"ok": False, "sha256": sha256, "error": "not found in pending promotions"}


def format_intake_summary(summary: dict[str, Any]) -> str:
    lines = [
        "GOVERNED ORACLE INTAKE — read-only copy+manifest pass",
        f"Total candidates examined: {summary.get('total_candidates', 0)}",
        f"Staged (awaiting Guard approval): {summary.get('by_ingest_status', {}).get(ST_STAGED, 0)}",
        f"Secrets flagged (path/type only, never copied): {summary.get('secret_flagged', 0)}",
        f"Pending promotions in Guard lane: {summary.get('pending_promotions', 0)}",
        "",
        "By classification:",
    ]
    for k, v in sorted(summary.get("by_classification", {}).items()):
        lines.append(f"  - {k}: {v}")
    lines.append("By ingest status:")
    for k, v in sorted(summary.get("by_ingest_status", {}).items()):
        lines.append(f"  - {k}: {v}")
    if summary.get("manifest_path"):
        lines.append("")
        lines.append(f"Manifest: {summary['manifest_path']}")
    lines.append("BOUNDARY: No originals moved/deleted/modified. No secrets copied. No network calls.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        from test_intake_pipeline import run_smoke_tests  # type: ignore
        raise SystemExit(run_smoke_tests())
    print(format_intake_summary(build_intake()))
