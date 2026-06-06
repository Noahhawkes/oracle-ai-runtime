"""
Source Map — indexes Noah's key folders and makes them searchable by Oracle.

Builds a lightweight JSON cache of file metadata (path, size, date, type, excerpt).
Oracle can search the index to find relevant files, then read them with read_file.
High-value docs can be ingested: summarized by the LLM and saved to Oracle's memory DB.

Key locations indexed by default:
  - G:\\My Drive\\HawkesNest LLC\\ORACLE.AI\\          (live code repo)
  - C:\\Users\\noahh\\OneDrive - sov1.ai\\Noah.AI Tech Documents\\
  - C:\\Users\\noahh\\OneDrive - sov1.ai\\ORACLE.AI\\
  - C:\\Users\\noahh\\OneDrive - sov1.ai\\Noah.AI Tech Business Records\\
  - C:\\Users\\noahh\\OneDrive - sov1.ai\\AI Compliance Core\\  (if present)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ROOT detection
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

INDEX_PATH = ROOT / "Memory" / "source_map.json"

# Folders to index (skip massive media folders)
DEFAULT_SCAN_PATHS = [
    r"G:\My Drive\HawkesNest LLC\ORACLE.AI",
    r"C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Documents",
    r"C:\Users\noahh\OneDrive - sov1.ai\ORACLE.AI",
    r"C:\Users\noahh\OneDrive - sov1.ai\Noah.AI Tech Business Records",
]

# File extensions worth indexing (skip media, executables)
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".ps1", ".bat", ".sh",
    ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".csv",
    ".html", ".htm", ".xml", ".sql",
}

SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "venv", ".venv",
    "Noah.AI Tech Photos", "Noah.AI Tech Video", "Oracle_JDK-24",
    "dist", "build", ".claude",
}

MAX_EXCERPT_CHARS = 500
MAX_FILES_PER_SCAN = 5000


# ── Index building ────────────────────────────────────────────────────────────

def _read_excerpt(path: Path) -> str:
    """Read the first MAX_EXCERPT_CHARS of a text-like file."""
    try:
        ext = path.suffix.lower()
        if ext == ".pdf":
            return _read_pdf_excerpt(path)
        if ext in (".docx", ".doc"):
            return _read_docx_excerpt(path)
        # Plain text fallback
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:MAX_EXCERPT_CHARS].strip()
    except Exception:
        return ""


def _read_pdf_excerpt(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            if pdf.pages:
                text = pdf.pages[0].extract_text() or ""
                return text[:MAX_EXCERPT_CHARS].strip()
    except ImportError:
        pass
    try:
        import PyPDF2
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            if reader.pages:
                text = reader.pages[0].extract_text() or ""
                return text[:MAX_EXCERPT_CHARS].strip()
    except Exception:
        pass
    return "[PDF — install pdfplumber to read excerpts]"


def _read_docx_excerpt(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        lines = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(lines)[:MAX_EXCERPT_CHARS].strip()
    except ImportError:
        return "[DOCX — install python-docx to read excerpts]"
    except Exception:
        return ""


def build_index(scan_paths=None, include_excerpts=True) -> dict:
    """
    Walk the given paths and build a file metadata index.
    Returns a dict: { "built_at": ..., "file_count": N, "files": [...] }
    """
    scan_paths = scan_paths or DEFAULT_SCAN_PATHS
    files = []
    seen = set()

    for root_str in scan_paths:
        root_path = Path(root_str)
        if not root_path.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            # Prune skipped dirs in-place so os.walk doesn't descend
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fname in filenames:
                if len(files) >= MAX_FILES_PER_SCAN:
                    break
                fpath = Path(dirpath) / fname
                if fpath in seen:
                    continue
                seen.add(fpath)
                ext = fpath.suffix.lower()
                if ext not in TEXT_EXTENSIONS:
                    continue
                try:
                    stat = fpath.stat()
                    entry = {
                        "path": str(fpath),
                        "name": fname,
                        "ext": ext,
                        "size_kb": round(stat.st_size / 1024, 1),
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                        "excerpt": _read_excerpt(fpath) if include_excerpts else "",
                    }
                    files.append(entry)
                except Exception:
                    continue

    index = {
        "built_at": datetime.now().isoformat(),
        "file_count": len(files),
        "scanned_paths": scan_paths,
        "files": files,
    }
    return index


def save_index(index: dict):
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")


def load_index() -> dict | None:
    if not INDEX_PATH.exists():
        return None
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── Search ────────────────────────────────────────────────────────────────────

def search_index(query: str, max_results: int = 20) -> list[dict]:
    """
    Search the cached index for files whose name, path, or excerpt contains the query.
    Returns a list of matching file entries (without full excerpts to keep output short).
    """
    index = load_index()
    if not index:
        return []
    q = query.lower()
    results = []
    for f in index["files"]:
        score = 0
        if q in f["name"].lower():
            score += 3
        if q in f["path"].lower():
            score += 2
        if q in f.get("excerpt", "").lower():
            score += 1
        if score:
            results.append((score, f))
    results.sort(key=lambda x: -x[0])
    return [
        {"path": f["path"], "name": f["name"], "ext": f["ext"],
         "size_kb": f["size_kb"], "modified": f["modified"]}
        for _, f in results[:max_results]
    ]


def get_index_summary() -> str:
    index = load_index()
    if not index:
        return "No source map built yet. Run source_map_scan first."
    lines = [
        f"Source map built: {index['built_at'][:16]}",
        f"Total files indexed: {index['file_count']}",
        "Scanned paths:",
    ]
    for p in index["scanned_paths"]:
        lines.append(f"  {p}")
    # Breakdown by extension
    from collections import Counter
    counts = Counter(f["ext"] for f in index["files"])
    lines.append("File types:")
    for ext, n in counts.most_common(10):
        lines.append(f"  {ext}: {n}")
    return "\n".join(lines)


# ── Memory ingestion ──────────────────────────────────────────────────────────

def ingest_file_to_memory(path: str, summary: str, category: str = "source_map"):
    """
    Save a file summary as a persistent memory fact so Oracle can recall it later.
    Uses Oracle's existing memory DB (facts table).
    """
    sys.path.insert(0, str(ROOT / "core"))
    from memory import upsert_fact
    key = Path(path).name
    value = f"{path}\n---\n{summary}"
    upsert_fact(category, key, value)


def get_file_excerpt(path: str) -> str:
    """Return the stored excerpt for a given path from the index, or read it fresh."""
    index = load_index()
    if index:
        for f in index["files"]:
            if f["path"] == path:
                return f.get("excerpt", "") or _read_excerpt(Path(path))
    return _read_excerpt(Path(path))
