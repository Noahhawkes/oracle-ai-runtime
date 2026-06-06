"""
ORACLE.AI — Filesystem Mapper (Phase 2)
Scans, indexes, and learns Noah's machine file structure.
Gives ORACLE awareness of what exists where — drives, projects, documents, apps.
"""

import os
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
INDEX_PATH = ROOT / "Memory" / "filesystem_index.json"

# Directories to skip (system/noise)
SKIP_DIRS = {
    "$Recycle.Bin", "System Volume Information", "Windows", "Program Files",
    "Program Files (x86)", "__pycache__", ".git", "node_modules",
    "venv", ".venv", "env", "dist", "build", ".cache", "AppData",
    "Temp", "temp", "tmp", "hiberfil.sys", "pagefile.sys"
}

# File extensions worth indexing
KNOWN_EXTENSIONS = {
    "code": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
             ".yaml", ".yml", ".toml", ".sh", ".ps1", ".bat", ".cpp", ".c",
             ".cs", ".java", ".go", ".rs", ".php", ".rb", ".sql"],
    "docs": [".docx", ".doc", ".pdf", ".txt", ".md", ".rtf", ".odt",
              ".xlsx", ".xls", ".csv", ".pptx", ".ppt"],
    "media": [".mp4", ".mp3", ".wav", ".avi", ".mov", ".mkv", ".jpg",
               ".jpeg", ".png", ".gif", ".svg", ".psd", ".ai"],
    "apps": [".exe", ".msi", ".lnk"],
    "data": [".db", ".sqlite", ".sqlite3", ".json", ".xml", ".env"]
}

ALL_TRACKED = [ext for exts in KNOWN_EXTENSIONS.values() for ext in exts]


def _get_file_category(ext: str) -> str:
    for cat, exts in KNOWN_EXTENSIONS.items():
        if ext.lower() in exts:
            return cat
    return "other"


def scan_directory(path: str, max_depth: int = 4, current_depth: int = 0) -> dict:
    """
    Recursively scan a directory up to max_depth.
    Returns a nested dict representing the structure.
    """
    result = {
        "path": path,
        "type": "directory",
        "children": [],
        "file_count": 0,
        "dir_count": 0
    }

    try:
        entries = list(os.scandir(path))
    except PermissionError:
        result["error"] = "Permission denied"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result

    for entry in entries:
        if entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue

        if entry.is_dir(follow_symlinks=False):
            result["dir_count"] += 1
            if current_depth < max_depth:
                child = scan_directory(entry.path, max_depth, current_depth + 1)
                result["children"].append(child)
            else:
                result["children"].append({
                    "path": entry.path,
                    "type": "directory",
                    "truncated": True
                })

        elif entry.is_file(follow_symlinks=False):
            ext = Path(entry.name).suffix.lower()
            if ext in ALL_TRACKED:
                try:
                    size = entry.stat().st_size
                    modified = datetime.fromtimestamp(entry.stat().st_mtime).isoformat()
                except Exception:
                    size = 0
                    modified = "unknown"

                result["children"].append({
                    "name": entry.name,
                    "path": entry.path,
                    "type": "file",
                    "category": _get_file_category(ext),
                    "ext": ext,
                    "size_kb": round(size / 1024, 1),
                    "modified": modified
                })
                result["file_count"] += 1

    return result


def map_drives() -> list:
    """Detect available drives on Windows."""
    drives = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            try:
                total, used, free = (
                    os.statvfs(drive).f_blocks * os.statvfs(drive).f_frsize,
                    0, 0
                ) if os.name != "nt" else _win_disk_usage(drive)
                drives.append({
                    "drive": drive,
                    "total_gb": round(total / (1024**3), 1),
                    "free_gb": round(free / (1024**3), 1)
                })
            except Exception:
                drives.append({"drive": drive, "total_gb": "unknown", "free_gb": "unknown"})
    return drives


def _win_disk_usage(path: str):
    """Get disk usage for Windows drive."""
    import shutil
    usage = shutil.disk_usage(path)
    return usage.total, usage.used, usage.free


def build_index(paths: list = None, max_depth: int = 4) -> dict:
    """
    Build a full filesystem index.
    paths: list of directories to scan. Defaults to common Noah locations.
    """
    if not paths:
        paths = [
            str(ROOT),
            str(ROOT / "Projects"),
        ]

    index = {
        "built_at": datetime.now().isoformat(),
        "drives": map_drives(),
        "locations": {}
    }

    for p in paths:
        if os.path.exists(p):
            print(f"[Filesystem Mapper] Scanning: {p}")
            index["locations"][p] = scan_directory(p, max_depth=max_depth)
        else:
            index["locations"][p] = {"error": "Path not found"}

    return index


def save_index(index: dict) -> str:
    """Save the filesystem index to disk."""
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    return f"Index saved: {INDEX_PATH}"


def load_index() -> dict:
    """Load existing filesystem index."""
    if not INDEX_PATH.exists():
        return {}
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def search_index(query: str, index: dict = None) -> list:
    """
    Search the filesystem index for files matching a query string.
    Returns list of matching file entries.
    """
    if index is None:
        index = load_index()

    results = []
    query_lower = query.lower()

    def _search_node(node):
        if isinstance(node, dict):
            if node.get("type") == "file":
                name = node.get("name", "")
                path = node.get("path", "")
                if query_lower in name.lower() or query_lower in path.lower():
                    results.append(node)
            for child in node.get("children", []):
                _search_node(child)
            for loc in node.get("locations", {}).values():
                _search_node(loc)

    _search_node(index)
    return results[:50]


def get_summary(index: dict = None) -> str:
    """Generate a human-readable summary of the filesystem index."""
    if index is None:
        index = load_index()

    if not index:
        return "No filesystem index found. Run build_index() first."

    lines = [f"Filesystem Index — Built: {index.get('built_at', 'unknown')}"]

    drives = index.get("drives", [])
    if drives:
        lines.append(f"\nDrives: {len(drives)}")
        for d in drives:
            lines.append(f"  {d['drive']} — {d.get('free_gb', '?')} GB free / {d.get('total_gb', '?')} GB total")

    locations = index.get("locations", {})
    lines.append(f"\nScanned Locations: {len(locations)}")
    for path, data in locations.items():
        if "error" in data:
            lines.append(f"  {path}: ERROR — {data['error']}")
        else:
            fc = data.get("file_count", 0)
            dc = data.get("dir_count", 0)
            lines.append(f"  {path}: {fc} files, {dc} dirs")

    return "\n".join(lines)


def run_full_scan() -> str:
    """
    Run a complete machine scan and save the index.
    Call this to give ORACLE full filesystem awareness.
    """
    print("[Filesystem Mapper] Starting full scan...")
    index = build_index()
    msg = save_index(index)
    summary = get_summary(index)
    print(f"[Filesystem Mapper] Done.\n{summary}")
    return f"{msg}\n\n{summary}"
