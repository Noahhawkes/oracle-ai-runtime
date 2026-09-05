"""Build a read-only document atlas across local/Drive-mounted files.

The atlas is a metadata-first index for ORACLE continuity review. It scans
document-like files modified or created inside a time window, classifies them
as candidate material, and writes local JSONL/Markdown reports.

Boundaries:
- no sandbox writes or reads
- no Google Drive mutation
- no canon promotion
- no secret/financial raw-content ingestion
- archive files are noted only when they are document-like stubs; ZIPs are not
  expanded in this pass
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SANDBOX_ROOT = ROOT / "sandbox"

DEFAULT_OUTPUT_DIR = ROOT / "data" / "document_atlas"
DEFAULT_CUTOFF = "2024-07-17"

DOC_EXTS = {
    ".ai",
    ".doc",
    ".docx",
    ".gdoc",
    ".gsheet",
    ".gslides",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".odt",
    ".pdf",
    ".rtf",
    ".text",
    ".txt",
}

TEXT_EXTS = {".ai", ".html", ".htm", ".md", ".markdown", ".rtf", ".text", ".txt"}
GOOGLE_STUB_EXTS = {".gdoc", ".gsheet", ".gslides"}

SKIP_DIR_NAMES = {
    "$recycle.bin",
    ".cache",
    ".encrypted",
    ".git",
    ".gradle",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".svn",
    ".tmp.driveupload",
    ".venv",
    "__pycache__",
    "appdata",
    "cache",
    "caches",
    "dist",
    "google photos",
    "node_modules",
    "music",
    "photos",
    "pictures",
    "program files",
    "program files (x86)",
    "programdata",
    "recovery",
    "system volume information",
    "temp",
    "takeout",
    "tmp",
    "venv",
    "videos",
    "windows",
}

SKIP_PATH_CONTAINS = {
    str(SANDBOX_ROOT).lower(),
    str(Path.home() / ".codex" / "plugins" / "cache").lower(),
}

CONTENT_MAX_BYTES = 2_000_000
PDF_MAX_BYTES = 8_000_000
DOCX_MAX_BYTES = 16_000_000
TEXT_SAMPLE_CHARS = 24_000
HASH_MAX_BYTES = 1_000_000

HIGH_RISK_NAME = re.compile(
    r"(password|passwd|secret|credential|token|api[_ -]?key|oauth|"
    r"bank|wells|fargo|chase|statement|1099|tax|ssn|social security|"
    r"account info|routing|invoice|unemployment|benefit|credit|card|"
    r"birth certificate|driver.?license|insurance|medical|health)",
    re.IGNORECASE,
)


@dataclass
class AtlasRecord:
    record_id: str
    source_surface: str
    path: str
    name: str
    extension: str
    size_bytes: int
    created_utc: str
    modified_utc: str
    touched_utc: str
    sha256_prefix: str
    content_status: str
    classification: str
    secondary_tags: list[str]
    sensitivity: str
    oracle_relevance: str
    routing_recommendation: str
    canon_status: str
    promotion_status: str
    google_url: str | None = None
    google_doc_id: str | None = None


def utc_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_cutoff(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def path_key(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path).lower()


def is_skipped_dir(path: Path) -> bool:
    key = path_key(path)
    if any(blocked in key for blocked in SKIP_PATH_CONTAINS):
        return True
    name = path.name.lower()
    if name in SKIP_DIR_NAMES:
        return True
    return False


def iter_document_files(roots: Iterable[Path]) -> Iterable[Path]:
    seen_dirs: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        stack = [root]
        while stack:
            current = stack.pop()
            current_key = path_key(current)
            if current_key in seen_dirs or is_skipped_dir(current):
                continue
            seen_dirs.add(current_key)
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                p = Path(entry.path)
                                if not is_skipped_dir(p):
                                    stack.append(p)
                            elif entry.is_file(follow_symlinks=False):
                                p = Path(entry.path)
                                if p.suffix.lower() in DOC_EXTS:
                                    yield p
                        except (OSError, PermissionError):
                            continue
            except (OSError, PermissionError):
                continue


def source_surface(path: Path) -> str:
    text = str(path).lower()
    home = str(Path.home()).lower()
    if "\\my drive\\" in text or text.startswith("g:\\"):
        return "google_drive_desktop"
    if "\\onedrive\\" in text:
        return "onedrive"
    if "\\downloads\\" in text:
        return "downloads"
    if "\\desktop\\" in text:
        return "desktop"
    if "\\documents\\" in text:
        return "documents"
    if "\\.codex\\attachments\\" in text:
        return "codex_attachments"
    if text.startswith(str(ROOT).lower()):
        return "oracle_runtime"
    if text.startswith(home):
        return "user_profile"
    return "local_drive"


def partial_hash(path: Path, high_risk: bool, drive_metadata_only: bool = False) -> str:
    if high_risk:
        return "metadata_only_sensitive"
    if drive_metadata_only:
        return "drive_metadata_only"
    try:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            h.update(handle.read(HASH_MAX_BYTES))
        return h.hexdigest()[:16]
    except OSError:
        return "unreadable"


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    return re.sub(r"\s+", " ", value).strip()


def read_text_sample(path: Path, *, sample_pdf: bool = False) -> tuple[str, str]:
    ext = path.suffix.lower()
    try:
        size = path.stat().st_size
    except OSError:
        return "", "stat_error"

    if ext in GOOGLE_STUB_EXTS:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return "", "google_stub_unreadable"
        fields = [str(data.get(k, "")) for k in ("url", "doc_id", "resource_id")]
        return " ".join(fields), "google_stub_metadata"

    if ext in TEXT_EXTS:
        if size > CONTENT_MAX_BYTES:
            return "", "text_too_large_metadata_only"
        try:
            raw = path.read_bytes()[:CONTENT_MAX_BYTES]
            return clean_text(raw.decode("utf-8", errors="replace"))[:TEXT_SAMPLE_CHARS], "text_sampled"
        except OSError:
            return "", "text_unreadable"

    if ext == ".docx":
        if size > DOCX_MAX_BYTES:
            return "", "docx_too_large_metadata_only"
        try:
            with zipfile.ZipFile(path) as zf:
                xml = zf.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            parts: list[str] = []
            for node in root.iter():
                if node.tag.endswith("}t") and node.text:
                    parts.append(node.text)
            return clean_text(" ".join(parts))[:TEXT_SAMPLE_CHARS], "docx_sampled"
        except Exception:
            return "", "docx_unreadable"

    if ext == ".pdf":
        if not sample_pdf:
            return "", "pdf_metadata_only"
        if size > PDF_MAX_BYTES:
            return "", "pdf_too_large_metadata_only"
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            pages = []
            for page in reader.pages[:3]:
                pages.append(page.extract_text() or "")
            text = clean_text("\n".join(pages))
            return text[:TEXT_SAMPLE_CHARS], "pdf_sampled" if text else "pdf_no_text"
        except Exception:
            return "", "pdf_metadata_only"

    return "", "metadata_only"


def google_stub_fields(path: Path) -> tuple[str | None, str | None]:
    if path.suffix.lower() not in GOOGLE_STUB_EXTS:
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None, None
    return data.get("url"), data.get("doc_id") or str(data.get("resource_id", "")).split(":")[-1] or None


DOMAIN_KEYWORDS: list[tuple[str, list[str]]] = [
    ("oracle_runtime_build", ["oracle", "ellie", "miracledrive", "source map", "sourcemap", "guard", "route", "receipt", "canon", "sandbox", "memory authority", "nexus"]),
    ("ai_compliance_product", ["ai compliance", "audit", "approval gate", "flight recorder", "provenance", "source verification", "work audit", "external action"]),
    ("legacy_gi_truthwriter", ["legacygi", "legacy.gi", "truthwriter", "return-from-dark", "light compression", "sovereign continuity", "compression is identity"]),
    ("rendered_reality_research", ["rendered reality", "cognitive world projection", "continuity intelligence", "identity is information", "reality is rendered"]),
    ("jupiter_station_avalon_canon", ["jupiter station", "avalon", "starfleet", "captain noah", "temporal", "voyager", "klingon", "season bible"]),
    ("thread_dump_ai_conversation", ["chatgpt thread", "thread injection", "threadmerge", "thread pass", "conversation", "prompt injection", "claude", "gemini", "copilot"]),
    ("ecowater_business", ["ecowater", "eco water", "bdm", "water treatment", "dealer", "sales 101", "residential water"]),
    ("personal_identity_journal", ["personal journal", "personality profile", "identity", "childhood", "family", "letter to", "dad", "ashley", "holland"]),
    ("finance_legal_admin", ["bank", "statement", "1099", "tax", "invoice", "unemployment", "benefit", "account info", "assets and budget", "credit", "legal", "law firm"]),
    ("creative_writing_publish", ["novel", "manuscript", "kdp", "chapter", "story", "series bible", "book", "proofread", "dragonkin", "drakin", "silverback"]),
    ("training_sales_outreach", ["masterclass", "workbook", "linkedin", "outreach", "upwork", "sales", "resume", "profile", "powerpoint"]),
]


def classify(path: Path, sample: str, *, high_risk_name: bool = False) -> tuple[str, list[str], str, str, str]:
    hay = f"{path} {sample[:4000]}".lower()
    scores: list[tuple[int, str]] = []
    matched_tags: list[str] = []
    for domain, keys in DOMAIN_KEYWORDS:
        score = 0
        for key in keys:
            if key in hay:
                score += 1
                matched_tags.append(key)
        if score:
            scores.append((score, domain))

    scores.sort(reverse=True)
    classification = scores[0][1] if scores else "unclassified_document"
    secondary = [domain for _, domain in scores[1:5]]

    if high_risk_name:
        sensitivity = "metadata_only_high_risk"
    elif classification in {"personal_identity_journal"}:
        sensitivity = "personal_sensitive"
    elif classification in {"ecowater_business", "finance_legal_admin"}:
        sensitivity = "work_or_admin_sensitive"
    elif classification in {"jupiter_station_avalon_canon", "creative_writing_publish"}:
        sensitivity = "creative_candidate"
    elif classification in {"oracle_runtime_build", "ai_compliance_product", "legacy_gi_truthwriter", "rendered_reality_research"}:
        sensitivity = "project_candidate"
    else:
        sensitivity = "unknown"

    if classification in {
        "oracle_runtime_build",
        "ai_compliance_product",
        "legacy_gi_truthwriter",
        "rendered_reality_research",
        "jupiter_station_avalon_canon",
        "thread_dump_ai_conversation",
        "personal_identity_journal",
    }:
        relevance = "high"
    elif classification in {"creative_writing_publish", "training_sales_outreach", "ecowater_business"}:
        relevance = "medium"
    else:
        relevance = "unknown"

    if sensitivity == "metadata_only_high_risk":
        routing = "metadata_only_review_manually"
    elif classification == "unclassified_document":
        routing = "candidate_triage_needed"
    elif classification in {"thread_dump_ai_conversation", "personal_identity_journal"}:
        routing = "candidate_recall_review_no_auto_canon"
    else:
        routing = "candidate_index_for_recall"

    return classification, sorted(set(secondary + matched_tags))[:12], sensitivity, relevance, routing


def make_record(path: Path, cutoff: datetime, *, sample_pdf: bool = False) -> AtlasRecord | None:
    try:
        st = path.stat()
    except OSError:
        return None

    created = datetime.fromtimestamp(st.st_ctime, tz=timezone.utc)
    modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    touched = max(created, modified)
    if touched < cutoff:
        return None

    surface = source_surface(path)
    cloud_sync_metadata_only = surface in {"google_drive_desktop", "onedrive"} and path.suffix.lower() not in GOOGLE_STUB_EXTS
    high_risk = bool(HIGH_RISK_NAME.search(str(path)))
    if high_risk:
        sample, content_status = "", "metadata_only_high_risk"
    elif cloud_sync_metadata_only:
        sample, content_status = "", f"{surface}_metadata_only"
    else:
        sample, content_status = read_text_sample(path, sample_pdf=sample_pdf)
    classification, tags, sensitivity, relevance, routing = classify(path, sample, high_risk_name=high_risk)
    url, doc_id = google_stub_fields(path)
    record_id = hashlib.sha256(str(path).lower().encode("utf-8", errors="replace")).hexdigest()[:16]
    return AtlasRecord(
        record_id=record_id,
        source_surface=surface,
        path=str(path),
        name=path.name,
        extension=path.suffix.lower(),
        size_bytes=st.st_size,
        created_utc=created.isoformat().replace("+00:00", "Z"),
        modified_utc=modified.isoformat().replace("+00:00", "Z"),
        touched_utc=touched.isoformat().replace("+00:00", "Z"),
        sha256_prefix=partial_hash(path, high_risk, drive_metadata_only=cloud_sync_metadata_only),
        content_status=content_status,
        classification=classification,
        secondary_tags=tags,
        sensitivity=sensitivity,
        oracle_relevance=relevance,
        routing_recommendation=routing,
        canon_status="candidate_unreviewed",
        promotion_status="not_promoted",
        google_url=url,
        google_doc_id=doc_id,
    )


def write_jsonl(path: Path, records: list[AtlasRecord]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(asdict(rec), ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, records: list[AtlasRecord]) -> None:
    fieldnames = list(asdict(records[0]).keys()) if records else list(AtlasRecord.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            row = asdict(rec)
            row["secondary_tags"] = ";".join(row["secondary_tags"])
            writer.writerow(row)


def write_summary(path: Path, records: list[AtlasRecord], roots: list[Path], cutoff: str, generated_at: str) -> None:
    by_class = Counter(r.classification for r in records)
    by_surface = Counter(r.source_surface for r in records)
    by_ext = Counter(r.extension for r in records)
    by_sensitivity = Counter(r.sensitivity for r in records)
    high_value = [
        r for r in records
        if r.oracle_relevance == "high" and r.sensitivity != "metadata_only_high_risk"
    ]
    high_value.sort(key=lambda r: r.touched_utc, reverse=True)

    grouped: dict[str, list[AtlasRecord]] = defaultdict(list)
    for rec in high_value:
        grouped[rec.classification].append(rec)

    lines = [
        "# Document Atlas Status",
        "",
        f"Generated: `{generated_at}`",
        f"Cutoff: `{cutoff}` (created or modified on/after this date)",
        "",
        "Boundary: read-only local/Drive metadata index; no sandbox access, no Drive edits, no canon promotion, no external send.",
        "",
        "## Scope",
        "",
    ]
    for root in roots:
        lines.append(f"- `{root}`")

    lines.extend([
        "",
        "## Counts",
        "",
        f"- total records: `{len(records)}`",
        f"- Google Drive Desktop / native stubs: `{by_surface.get('google_drive_desktop', 0)}`",
        f"- OneDrive: `{by_surface.get('onedrive', 0)}`",
        f"- ORACLE runtime: `{by_surface.get('oracle_runtime', 0)}`",
        f"- Codex attachments: `{by_surface.get('codex_attachments', 0)}`",
        "",
        "## By Classification",
        "",
    ])
    for key, value in by_class.most_common():
        lines.append(f"- `{key}`: {value}")

    lines.extend(["", "## By Sensitivity", ""])
    for key, value in by_sensitivity.most_common():
        lines.append(f"- `{key}`: {value}")

    lines.extend(["", "## By Extension", ""])
    for key, value in by_ext.most_common():
        lines.append(f"- `{key or '(none)'}`: {value}")

    lines.extend(["", "## High-Relevance Candidate Clusters", ""])
    for classification, items in sorted(grouped.items()):
        lines.append(f"### {classification}")
        for item in items[:20]:
            link = item.google_url or item.path
            lines.append(
                f"- `{item.touched_utc[:10]}` `{item.source_surface}` "
                f"`{item.name}` -> {item.routing_recommendation}"
            )
            lines.append(f"  - source: `{link}`")
        if len(items) > 20:
            lines.append(f"  - ... {len(items) - 20} more in JSONL")
        lines.append("")

    lines.extend([
        "## Known Holes",
        "",
        "- Large Google Takeout ZIP archives are indexed only as surrounding files when document-like; ZIP contents were not expanded.",
        "- Native Google Docs reached through Drive-for-Desktop `.gdoc` stubs are metadata-indexed here; use the Google Drive connector/export path for full text review.",
        "- High-risk finance, legal, credential, tax, and account-looking files are metadata-only by design.",
        "",
        "## Status",
        "",
        "- `canon_status`: all records are `candidate_unreviewed`.",
        "- `promotion_status`: all records are `not_promoted`.",
    ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    cutoff = parse_cutoff(args.cutoff)
    roots = [Path(r).resolve() for r in args.root]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[AtlasRecord] = []
    scanned = 0
    for candidate in iter_document_files(roots):
        scanned += 1
        rec = make_record(candidate, cutoff, sample_pdf=args.sample_pdf)
        if rec:
            records.append(rec)
        if args.max_candidates and scanned >= args.max_candidates:
            break

    records.sort(key=lambda r: (r.touched_utc, r.path.lower()), reverse=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = output_dir / f"document_index_{stamp}.jsonl"
    csv_path = output_dir / f"document_index_{stamp}.csv"
    summary_path = output_dir / f"document_index_summary_{stamp}.md"
    latest_jsonl = output_dir / "latest_document_index.jsonl"
    latest_csv = output_dir / "latest_document_index.csv"
    latest_summary = output_dir / "latest_document_atlas_summary.md"

    write_jsonl(jsonl_path, records)
    write_jsonl(latest_jsonl, records)
    write_csv(csv_path, records)
    write_csv(latest_csv, records)
    generated_at = now_utc()
    write_summary(summary_path, records, roots, args.cutoff, generated_at)
    write_summary(latest_summary, records, roots, args.cutoff, generated_at)

    return {
        "ok": True,
        "generated_at": generated_at,
        "cutoff": args.cutoff,
        "roots": [str(r) for r in roots],
        "scanned_candidates": scanned,
        "records": len(records),
        "jsonl": str(jsonl_path),
        "csv": str(csv_path),
        "summary": str(summary_path),
        "latest_jsonl": str(latest_jsonl),
        "latest_csv": str(latest_csv),
        "latest_summary": str(latest_summary),
        "by_classification": Counter(r.classification for r in records),
        "by_surface": Counter(r.source_surface for r in records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ORACLE document atlas")
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    parser.add_argument("--root", action="append", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--sample-pdf", action="store_true", help="extract text from small PDFs during the sweep")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, indent=2, default=lambda value: dict(value), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
