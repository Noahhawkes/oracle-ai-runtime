"""
core/miracledrive_index.py — MiracleDrive filesystem index.

Scans configured source paths, builds a live metadata index of all
readable files, and exposes a query interface for ORACLE.

No data leaves the local machine. No network calls. No LLM involved.
All reads use real pathlib/stat calls — no fabricated metadata.

Readable formats: .txt, .md, .json, .py, .bat, .yaml, .yml, .csv,
                  .log, .docx (text extraction), .pdf (text extraction)

Large files: metadata indexed, content skipped (> MAX_CONTENT_BYTES).
Binary files: metadata only.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Configuration ─────────────────────────────────────────────────────────────

GDRIVE_ROOT = Path("G:/My Drive")
ORACLE_ROOT = Path("G:/My Drive/HawkesNest LLC/ORACLE.AI")

# Paths ORACLE indexes (all readable, no restrictions)
SOURCE_PATHS = [
    GDRIVE_ROOT / "MiracleDrive_SealPhase_2025-04-05_16-44-46",
    ORACLE_ROOT,  # live workspace first for recovery/search relevance
    GDRIVE_ROOT / "HawkesNest LLC",
    GDRIVE_ROOT / "ORACLE.AI",
    GDRIVE_ROOT / "OracleAI",
    GDRIVE_ROOT / "SOv1",
    GDRIVE_ROOT / "SOV1_Migration_2025",
    GDRIVE_ROOT / "LOGS",
    GDRIVE_ROOT / "Noah_Eternal_Rebuild",
    GDRIVE_ROOT / "NOAH_FlameAnchor_Deployment",
    GDRIVE_ROOT / "HYDRA_STACK_Figures",
    GDRIVE_ROOT / "DOCX",
    ORACLE_ROOT,  # live workspace duplicate kept harmless by root dedupe
]

# OBS recording directories (common locations)
OBS_PATHS = [
    Path("C:/Users/noahh/Videos"),
    Path("C:/Users/noahh/Documents/OBS"),
    Path(os.path.expanduser("~/Videos")),
]

# Cold CLI searches should be fast and relevant. The full background index still
# covers SOURCE_PATHS above for the MiracleDrive UI.
SEARCH_PRIORITY_PATHS = [
    ORACLE_ROOT / "core",
    ORACLE_ROOT / "docs",
    ORACLE_ROOT / "reference",
    ORACLE_ROOT / "Memory",
    ORACLE_ROOT / "tests",
    ORACLE_ROOT / "ui",
]

# Text-readable extensions (content extracted up to MAX_CONTENT_BYTES)
TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".py", ".js", ".ts", ".html", ".css",
    ".yaml", ".yml", ".csv", ".log", ".bat", ".ps1", ".sh",
    ".xml", ".toml", ".ini", ".cfg", ".env", ".example",
    ".gdoc",  # treated as text if accessible
}

# Docx/PDF require extra libraries — attempted, not required
RICH_EXTENSIONS = {".docx", ".pdf"}

# Max bytes to read for content indexing
MAX_CONTENT_BYTES = 32_000   # ~8k tokens

# Max bytes to hash during broad indexing. Full hashes remain available through
# read_file(path), where the user asked for one specific file.
MAX_HASH_BYTES = 1_000_000

# Max files per scan to avoid runaway (expand as needed)
MAX_FILES = 5_000

SKIP_DIR_NAMES = {
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    "worktrees",
}

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class FileRecord:
    path: str
    name: str
    extension: str
    size_bytes: int
    mtime_utc: str
    sha256_prefix: str          # first 16 chars only — not a full hash claim
    content_preview: Optional[str]  # first 500 chars if text-readable
    content_available: bool
    source_root: str
    category: str               # derived from extension / location


@dataclass
class DriveIndex:
    built_at: str
    total_files: int
    total_bytes: int
    source_paths_scanned: list[str]
    source_paths_missing: list[str]
    files: list[FileRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        by_cat: dict[str, int] = {}
        for f in self.files:
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
        return {
            "built_at": self.built_at,
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "total_mb": round(self.total_bytes / (1024*1024), 1),
            "by_category": by_cat,
            "source_paths_scanned": self.source_paths_scanned,
            "source_paths_missing": self.source_paths_missing,
            "errors": self.errors[:10],
        }

    def search(self, query: str, limit: int = 20) -> list[FileRecord]:
        """Simple text search across name + content_preview."""
        q = query.lower()
        results = []
        for f in self.files:
            if (q in f.name.lower() or
                q in f.path.lower() or
                (f.content_preview and q in f.content_preview.lower())):
                results.append(f)
            if len(results) >= limit:
                break
        return results

    def recent(self, limit: int = 20) -> list[FileRecord]:
        """Most recently modified files."""
        return sorted(self.files, key=lambda f: f.mtime_utc, reverse=True)[:limit]

    def by_category(self, cat: str) -> list[FileRecord]:
        return [f for f in self.files if f.category == cat]


# ── Category classifier ───────────────────────────────────────────────────────

def _classify(path: Path) -> str:
    ext = path.suffix.lower()
    name = path.name.lower()
    parts = [p.lower() for p in path.parts]

    if ext in {".mp4", ".mkv", ".mov", ".avi", ".webm"}:
        return "video"
    if ext in {".mp3", ".m4a", ".wav", ".flac", ".aac"}:
        return "audio"
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".bmp"}:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in {".docx", ".doc", ".gdoc"}:
        return "document"
    if ext in {".py", ".js", ".ts", ".bat", ".ps1", ".sh"}:
        return "code"
    if ext in {".json", ".yaml", ".yml", ".toml", ".xml"}:
        return "config"
    if ext in {".log"}:
        return "log"
    if ext in {".txt", ".md"}:
        if "obs" in parts or "obs" in name:
            return "obs_log"
        return "text"
    if ext in {".csv"}:
        return "data"
    if ext in {".zip", ".tar", ".gz"}:
        return "archive"
    if any(p in parts for p in ["videos", "video", "recordings", "obs"]):
        return "video"
    return "other"


# ── File reader ───────────────────────────────────────────────────────────────

def _read_text_content(path: Path) -> Optional[str]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        return text[:MAX_CONTENT_BYTES]
    except Exception:
        return None


def _read_docx_content(path: Path) -> Optional[str]:
    try:
        import docx
        doc = docx.Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return text[:MAX_CONTENT_BYTES]
    except Exception:
        return None


def _read_pdf_content(path: Path) -> Optional[str]:
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            pages = [pg.extract_text() or "" for pg in pdf.pages[:5]]
        return "\n".join(pages)[:MAX_CONTENT_BYTES]
    except Exception:
        try:
            import PyPDF2
            with open(str(path), "rb") as f:
                reader = PyPDF2.PdfReader(f)
                pages = [reader.pages[i].extract_text() or "" for i in range(min(5, len(reader.pages)))]
            return "\n".join(pages)[:MAX_CONTENT_BYTES]
        except Exception:
            return None


def _sha256_prefix(path: Path) -> str:
    try:
        raw = path.read_bytes()
        return hashlib.sha256(raw).hexdigest()[:16]
    except Exception:
        return "unreadable"


def _iter_source_roots() -> list[Path]:
    """Return configured roots without duplicate child paths."""
    roots: list[Path] = []
    for root in list(SOURCE_PATHS) + list(OBS_PATHS):
        if not root.exists():
            roots.append(root)
            continue
        try:
            resolved = root.resolve()
        except Exception:
            resolved = root
        duplicate_child = False
        for existing in roots:
            if not existing.exists():
                continue
            try:
                existing_resolved = existing.resolve()
                if resolved == existing_resolved or resolved.is_relative_to(existing_resolved):
                    duplicate_child = True
                    break
            except Exception:
                continue
        if not duplicate_child:
            roots.append(root)
    return roots


def _walk_files(root: Path):
    """Yield files while pruning hidden/build/cache directories early."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIR_NAMES
            and not d.startswith(".")
            and not d.lower().endswith(".worktrees")
        ]
        for name in filenames:
            if name.startswith(".") or name == "desktop.ini" or name.endswith(".pyc"):
                continue
            yield Path(dirpath) / name


# ── Scanner ───────────────────────────────────────────────────────────────────

def _scan_path(root: Path, index: DriveIndex, file_count: list[int]) -> None:
    if not root.exists():
        index.source_paths_missing.append(str(root))
        return

    index.source_paths_scanned.append(str(root.resolve()))

    try:
        for path in _walk_files(root):
            if file_count[0] >= MAX_FILES:
                break

            try:
                stat = path.stat()
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            except Exception as e:
                index.errors.append(f"stat failed: {path}: {e}")
                continue

            ext = path.suffix.lower()
            cat = _classify(path)
            sha = _sha256_prefix(path) if size <= MAX_HASH_BYTES else "large_file"

            # Content extraction
            content = None
            content_available = False
            if size < MAX_CONTENT_BYTES:
                if ext in TEXT_EXTENSIONS:
                    content = _read_text_content(path)
                    content_available = content is not None
                elif ext == ".docx":
                    content = _read_docx_content(path)
                    content_available = content is not None
                elif ext == ".pdf":
                    content = _read_pdf_content(path)
                    content_available = content is not None

            preview = content[:500] if content else None

            record = FileRecord(
                path=str(path.resolve()),
                name=path.name,
                extension=ext,
                size_bytes=size,
                mtime_utc=mtime,
                sha256_prefix=sha,
                content_preview=preview,
                content_available=content_available,
                source_root=str(root),
                category=cat,
            )
            index.files.append(record)
            index.total_bytes += size
            file_count[0] += 1

    except PermissionError as e:
        index.errors.append(f"permission denied: {root}: {e}")
    except Exception as e:
        index.errors.append(f"scan error: {root}: {e}")


# ── Public API ────────────────────────────────────────────────────────────────

_cached_index: Optional[DriveIndex] = None
_cache_built_at: float = 0.0
_build_in_progress: bool = False
CACHE_TTL = 300  # rebuild index every 5 minutes


def build_index() -> DriveIndex:
    """Scan all configured source paths and return a DriveIndex."""
    index = DriveIndex(
        built_at=datetime.now(timezone.utc).isoformat(),
        total_files=0,
        total_bytes=0,
        source_paths_scanned=[],
        source_paths_missing=[],
    )
    file_count = [0]
    for root in _iter_source_roots():
        if file_count[0] >= MAX_FILES:
            break
        _scan_path(root, index, file_count)
    index.total_files = len(index.files)
    return index


def search_filesystem(text: str, limit: int = 20, max_files: int = MAX_FILES) -> list[dict]:
    """
    Cold-search configured MiracleDrive roots without building the whole index.

    This is for CLI/manual recovery paths. It searches high-value ORACLE roots,
    avoids broad hashing and slow rich-document extraction. The web index covers
    broader Drive roots in the background.
    """
    q = text.lower().strip()
    if not q:
        return []
    query_terms = [t for t in q.replace("_", " ").replace("-", " ").split() if t]

    def term_hit(value: str) -> bool:
        normalized = value.lower().replace("_", " ").replace("-", " ")
        return all(term in normalized for term in query_terms)

    def make_record(path: Path, root: Path, size: int, content: Optional[str]) -> dict:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except Exception:
            mtime = ""
        return asdict(FileRecord(
                path=str(path.resolve()),
                name=path.name,
                extension=path.suffix.lower(),
                size_bytes=size,
                mtime_utc=mtime,
                sha256_prefix="not_hashed",
                content_preview=(content[:500] if content else None),
                content_available=content is not None,
                source_root=str(root),
                category=_classify(path),
            ))

    out: list[tuple[int, dict]] = []
    seen: set[str] = set()

    def append_match(score: int, path: Path, root: Path, content: Optional[str] = None) -> None:
        key = str(path.resolve())
        if key in seen:
            return
        try:
            size = path.stat().st_size
        except Exception:
            return
        seen.add(key)
        out.append((score, make_record(path, root, size, content)))

    roots = [p for p in SEARCH_PRIORITY_PATHS if p.exists()] or _iter_source_roots()

    scanned = 0
    for root in roots:
        if not root.exists():
            continue
        for path in _walk_files(root):
            if scanned >= max_files or len(out) >= limit:
                break
            scanned += 1
            name_hit = q in path.name.lower() or term_hit(path.name)
            path_hit = q in str(path).lower() or term_hit(str(path))
            if name_hit or path_hit:
                content = None
                try:
                    if path.stat().st_size < MAX_CONTENT_BYTES and path.suffix.lower() in TEXT_EXTENSIONS:
                        content = _read_text_content(path)
                except Exception:
                    content = None
                append_match(0 if name_hit else 1, path, root, content)
        if scanned >= max_files or len(out) >= limit:
            break

    if len(out) < limit:
        scanned = 0
        for root in roots:
            if not root.exists():
                continue
            for path in _walk_files(root):
                if scanned >= max_files or len(out) >= limit:
                    break
                scanned += 1
                if str(path.resolve()) in seen or path.suffix.lower() not in TEXT_EXTENSIONS:
                    continue
                try:
                    size = path.stat().st_size
                except Exception:
                    continue
                if size >= MAX_CONTENT_BYTES:
                    continue
                content = _read_text_content(path)
                if content and q in content.lower():
                    append_match(2, path, root, content)
            if scanned >= max_files or len(out) >= limit:
                break

    ranked = sorted(out, key=lambda item: (item[0], item[1]["name"].lower(), item[1]["path"].lower()))
    return [item[1] for item in ranked[:limit]]


def _build_in_background() -> None:
    """Run build_index() in a thread and cache the result."""
    global _cached_index, _cache_built_at, _build_in_progress
    try:
        _cached_index = build_index()
        _cache_built_at = time.time()
    finally:
        _build_in_progress = False


def get_index(force: bool = False) -> Optional[DriveIndex]:
    """
    Return cached index. If stale or missing, kick off a background build
    and return the stale cache (or None if never built). Non-blocking.
    """
    global _cached_index, _cache_built_at, _build_in_progress
    import threading
    now = time.time()
    needs_build = (
        force or
        _cached_index is None or
        (now - _cache_built_at) > CACHE_TTL
    )
    if needs_build and not _build_in_progress:
        _build_in_progress = True
        t = threading.Thread(target=_build_in_background, daemon=True)
        t.start()
    return _cached_index  # may be None while first build runs


def start_background_index() -> None:
    """Kick off index build at server startup — call once from _boot()."""
    get_index()  # triggers background thread if not cached


def query(text: str, limit: int = 20, *, force_build: bool = False) -> list[dict]:
    """Search the index. Returns [] if index not yet built unless force_build is set."""
    idx = build_index() if force_build else get_index()
    if idx is None:
        return []
    return [asdict(r) for r in idx.search(text, limit=limit)]


def read_file(path_str: str) -> dict:
    """
    Read a specific file by absolute path.
    Returns content + metadata. No path restriction — ORACLE has full access.
    Real pathlib calls only. No fabrication.
    """
    path = Path(path_str)
    if not path.exists():
        return {"ok": False, "error": "file_not_found", "path": str(path.resolve())}
    if not path.is_file():
        return {"ok": False, "error": "not_a_file", "path": str(path.resolve())}

    try:
        stat = path.stat()
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        ext = path.suffix.lower()
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if size < 50_000_000 else None

        content = None
        if size < MAX_CONTENT_BYTES:
            if ext in TEXT_EXTENSIONS:
                content = _read_text_content(path)
            elif ext == ".docx":
                content = _read_docx_content(path)
            elif ext == ".pdf":
                content = _read_pdf_content(path)

        return {
            "ok": True,
            "path": str(path.resolve()),
            "name": path.name,
            "extension": ext,
            "size_bytes": size,
            "mtime_utc": mtime,
            "sha256": sha,
            "content": content,
            "content_available": content is not None,
            "category": _classify(path),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "path": str(path)}


def drive_state() -> dict:
    """
    Real-time state summary for the MiracleDrive UI.
    Returns immediately — returns building=True if index not yet ready.
    No LLM. No fabrication.
    """
    idx = get_index()  # triggers background build if needed, non-blocking
    if idx is None:
        return {
            "building": True,
            "total_files": 0,
            "total_bytes": 0,
            "total_mb": 0,
            "by_category": {},
            "source_paths_scanned": [],
            "source_paths_missing": [],
            "recent_files": [],
            "index_age_seconds": None,
            "errors": [],
        }

    summ = idx.summary()
    recent = [
        {"name": f.name, "category": f.category, "mtime": f.mtime_utc, "path": f.path}
        for f in idx.recent(5)
    ]
    return {
        **summ,
        "building": False,
        "recent_files": recent,
        "index_age_seconds": round(time.time() - _cache_built_at, 1),
    }


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    failures = 0

    def check(label: str, passed: bool, detail: str = ""):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}" + (f" -- {detail}" if detail and not passed else ""))
        if not passed:
            failures += 1

    print("=" * 60)
    print("MiracleDriveIndex -- Smoke Tests")
    print("=" * 60)

    idx = build_index()

    check("build_index returns DriveIndex", isinstance(idx, DriveIndex))
    check("built_at is ISO timestamp", "T" in idx.built_at)
    check("total_files >= 0", idx.total_files >= 0)
    check("total_bytes >= 0", idx.total_bytes >= 0)
    check("source_paths_scanned is a list", isinstance(idx.source_paths_scanned, list))
    check("source_paths_missing is a list", isinstance(idx.source_paths_missing, list))

    # At least one path should be accessible
    any_scanned = len(idx.source_paths_scanned) > 0
    check("at least one source path scanned", any_scanned,
          f"all {len(idx.source_paths_missing)} paths missing")

    if idx.total_files > 0:
        f = idx.files[0]
        check("file record has real path", Path(f.path).is_absolute())
        check("file record has name", bool(f.name))
        check("file record has mtime_utc", "T" in f.mtime_utc)
        check("file record has category", bool(f.category))
        check("file size_bytes >= 0", f.size_bytes >= 0)
        check("sha256_prefix is 16 chars or 'unreadable'/'large_file'",
              len(f.sha256_prefix) in {8, 16} or f.sha256_prefix in {"unreadable", "large_file"})

    # summary
    s = idx.summary()
    check("summary has total_files", "total_files" in s)
    check("summary has by_category dict", isinstance(s.get("by_category"), dict))
    check("summary total_mb is float", isinstance(s.get("total_mb"), (int, float)))

    # search
    if idx.total_files > 0:
        hits = idx.search(idx.files[0].name[:4])
        check("search returns list", isinstance(hits, list))

    # read_file on a real file
    real_path = str(Path(__file__).resolve())
    result = read_file(real_path)
    check("read_file self -> ok", result.get("ok") is True)
    check("read_file has sha256", bool(result.get("sha256")))
    check("read_file has content", bool(result.get("content")))

    # read_file on missing path
    missing = read_file("/nonexistent/oracle_fake_12345.txt")
    check("missing file -> ok=False", missing.get("ok") is False)
    check("missing file -> error=file_not_found", missing.get("error") == "file_not_found")

    # drive_state
    ds = drive_state()
    check("drive_state has total_files", "total_files" in ds)
    check("drive_state has recent_files", "recent_files" in ds)
    check("drive_state has index_age_seconds", "index_age_seconds" in ds)

    total = 20
    passed = total - failures
    print("=" * 60)
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print("=" * 60)
    return failures


if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("--smoke-test", action="store_true")
    p.add_argument("--index", action="store_true", help="Print index summary")
    p.add_argument("--search", help="Search the index")
    p.add_argument("--read", help="Read a specific file path")
    args = p.parse_args()

    if args.smoke_test:
        sys.exit(_smoke_test())
    elif args.index:
        idx = build_index()
        print(json.dumps(idx.summary(), indent=2, default=str))
    elif args.search:
        results = search_filesystem(args.search)
        for r in results:
            print(f"  {r['category']:12} {r['mtime_utc'][:10]}  {r['name']}")
            if r.get('content_preview'):
                print(f"             {r['content_preview'][:100]!r}")
        if not results:
            print("  no MiracleDrive matches")
    elif args.read:
        result = read_file(args.read)
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python core/miracledrive_index.py --smoke-test | --index | --search <q> | --read <path>")
