"""
core/drive_scope.py — ORACLE Drive Scope v0.1

Safe read-only discovery of Noah's full Windows computer.
ORACLE must stop treating G:\\ as the whole world.

Rules (non-negotiable):
  - Read-only discovery only. No file content reading.
  - No recursive full-drive crawl by default.
  - No delete / move / rename / upload / sync / share / permission changes.
  - External/removable drives blocked unless explicitly approved.
  - Blocked folders: financial, legal, medical, tax, browser profiles,
    password managers, system directories.

Output:
  Memory/drive_scope.json   — discovered drives and approved candidate paths
  Memory/scoped_paths.json  — flat list of approved scoped paths

Usage:
    python core/drive_scope.py --discover
    python core/drive_scope.py --status
    python core/drive_scope.py --smoke-test
"""

from __future__ import annotations

import json
import os
import string
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
DRIVE_SCOPE_FILE  = ROOT / "Memory" / "drive_scope.json"
SCOPED_PATHS_FILE = ROOT / "Memory" / "scoped_paths.json"

_NOW = lambda: datetime.now(timezone.utc).isoformat()

# ── Blocked folder patterns — never traversed ─────────────────────────────────
BLOCKED_FOLDER_PATTERNS = frozenset([
    # System
    "windows", "system32", "syswow64", "program files", "program files (x86)",
    "programdata", "recovery", "boot", "$recycle.bin", "system volume information",
    # Browser / credentials
    "chrome", "firefox", "edge", "opera", "brave", "safari",
    "default\\cookies", "default\\login data", "passwords",
    "keychain", "1password", "lastpass", "bitwarden", "keepass",
    # Financial / legal / medical / tax
    "tax", "taxes", "irs", "w-2", "1099", "financial", "bank",
    "legal", "attorney", "medical", "health", "insurance", "hipaa",
    # Sensitive OS
    "appdata\\local\\microsoft\\credentials",
    "appdata\\roaming\\microsoft\\protect",
    "ntuser.dat",
])

# ── Approved candidate root paths — discovered at runtime ────────────────────
_CANDIDATE_ROOTS = [
    # User directories
    ("desktop",    lambda: Path.home() / "Desktop"),
    ("documents",  lambda: Path.home() / "Documents"),
    ("downloads",  lambda: Path.home() / "Downloads"),
    ("pictures",   lambda: Path.home() / "Pictures"),
    ("videos",     lambda: Path.home() / "Videos"),
    ("music",      lambda: Path.home() / "Music"),
    # OneDrive variants
    ("onedrive",   lambda: Path.home() / "OneDrive"),
    ("onedrive_sov1", lambda: Path(os.environ.get("OneDrive", str(Path.home() / "OneDrive - sov1.ai")))),
    # Google Drive typical locations
    ("gdrive_g",   lambda: Path("G:\\My Drive")),
    ("gdrive_h",   lambda: Path("H:\\My Drive")),
    # Dev / project roots
    ("dev_c",      lambda: Path("C:\\dev")),
    ("repos_c",    lambda: Path("C:\\repos")),
    ("projects_c", lambda: Path("C:\\projects")),
    ("users_dev",  lambda: Path.home() / "dev"),
    ("users_repos",lambda: Path.home() / "repos"),
    ("users_projects", lambda: Path.home() / "projects"),
    # ORACLE itself
    ("oracle_root", lambda: ROOT),
]

# OBS default recording dirs
_OBS_CANDIDATES = [
    Path.home() / "Videos" / "OBS",
    Path.home() / "Videos",
    Path("C:\\Users") / os.environ.get("USERNAME", "Noah") / "Videos" / "OBS",
]


def _is_blocked(path: Path) -> bool:
    """True if path matches any blocked pattern."""
    low = str(path).lower()
    return any(pat in low for pat in BLOCKED_FOLDER_PATTERNS)


def _drive_type(drive_letter: str) -> str:
    """Best-effort drive type string on Windows."""
    try:
        import ctypes
        dt = ctypes.windll.kernel32.GetDriveTypeW(f"{drive_letter}:\\")
        return {1: "no_root", 2: "removable", 3: "fixed", 4: "network",
                5: "cdrom", 6: "ramdisk"}.get(dt, "unknown")
    except Exception:
        return "unknown"


def _discover_drives() -> list[dict]:
    """List all drive letters present on this Windows machine."""
    drives = []
    for letter in string.ascii_uppercase:
        p = Path(f"{letter}:\\")
        if p.exists():
            dtype = _drive_type(letter)
            approved = dtype in ("fixed", "network") or letter in ("C", "D", "G", "H")
            blocked  = dtype == "removable"
            drives.append({
                "letter":   letter,
                "path":     str(p),
                "type":     dtype,
                "approved": approved,
                "blocked":  blocked,
                "reason":   "removable drive blocked by default" if blocked else "",
            })
    return drives


def _discover_candidate_paths() -> list[dict]:
    """Probe all candidate root paths and return those that exist."""
    candidates = []
    for name, factory in _CANDIDATE_ROOTS:
        try:
            p = factory()
            exists = p.exists() and not _is_blocked(p)
            candidates.append({
                "name":    name,
                "path":    str(p),
                "exists":  p.exists(),
                "approved": exists,
                "blocked": _is_blocked(p),
            })
        except Exception as e:
            candidates.append({
                "name": name, "path": "error", "exists": False,
                "approved": False, "blocked": False, "error": str(e),
            })

    # OBS recording folders
    for obs_p in _OBS_CANDIDATES:
        if obs_p.exists() and not _is_blocked(obs_p):
            candidates.append({
                "name":    "obs_recordings",
                "path":    str(obs_p),
                "exists":  True,
                "approved": True,
                "blocked": False,
            })
            break

    return candidates


def discover() -> dict:
    """Run full drive and path discovery. Returns scope dict."""
    drives     = _discover_drives()
    candidates = _discover_candidate_paths()

    scope = {
        "discovered_at": _NOW(),
        "drives":        drives,
        "candidate_paths": candidates,
        "approved_paths":  [c["path"] for c in candidates if c["approved"]],
        "blocked_paths":   [c["path"] for c in candidates if c["blocked"]],
        "oracle_root":     str(ROOT),
        "safety": {
            "read_only":           True,
            "no_recursive_crawl":  True,
            "no_file_content":     True,
            "external_blocked":    True,
            "blocked_patterns":    sorted(BLOCKED_FOLDER_PATTERNS),
        },
    }

    # Persist
    DRIVE_SCOPE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DRIVE_SCOPE_FILE.write_text(
        json.dumps(scope, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Flat scoped paths list
    scoped = {
        "generated_at":   _NOW(),
        "approved_paths": scope["approved_paths"],
        "oracle_root":    str(ROOT),
    }
    SCOPED_PATHS_FILE.write_text(
        json.dumps(scoped, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return scope


def load_scope() -> dict:
    """Load existing scope from disk, or run discovery if missing."""
    try:
        raw = json.loads(DRIVE_SCOPE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and raw.get("drives"):
            return raw
    except Exception:
        pass
    return discover()


def approved_paths() -> list[str]:
    """Return current list of approved scoped paths."""
    try:
        raw = json.loads(SCOPED_PATHS_FILE.read_text(encoding="utf-8"))
        return raw.get("approved_paths", [])
    except Exception:
        return [str(ROOT)]


def is_in_scope(path) -> bool:
    """True if path is within an approved scoped path."""
    p = str(Path(path).resolve()).lower()
    for ap in approved_paths():
        if p.startswith(ap.lower()):
            return True
    return False


def status_report(scope: Optional[dict] = None) -> str:
    if scope is None:
        scope = load_scope()
    drives = scope.get("drives", [])
    approved = scope.get("approved_paths", [])
    blocked  = scope.get("blocked_paths", [])
    lines = [
        "",
        "=" * 55,
        "  ORACLE Drive Scope — Status",
        "=" * 55,
        f"  Discovered at  : {scope.get('discovered_at', 'never')[:19]}",
        f"  Drives found   : {len(drives)}",
    ]
    for d in drives:
        tag = "BLOCKED" if d["blocked"] else ("OK" if d["approved"] else "skip")
        lines.append(f"    [{tag:7}] {d['letter']}:\\ ({d['type']})")
    lines += [
        f"  Approved paths : {len(approved)}",
        f"  Blocked paths  : {len(blocked)}",
        f"  Oracle root    : {scope.get('oracle_root', 'unknown')}",
        "=" * 55,
        "",
    ]
    return "\n".join(lines)


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0

    def check(label, passed, detail=""):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        suffix = f" — {detail}" if detail and not passed else ""
        print(f"  [{tag}] {label}{suffix}")
        if not passed:
            failures += 1

    print("=" * 55)
    print("Drive Scope v0.1 — Smoke Tests")
    print("=" * 55)

    import tempfile
    import drive_scope as _ds
    orig_scope  = _ds.DRIVE_SCOPE_FILE
    orig_scoped = _ds.SCOPED_PATHS_FILE
    tmp = Path(tempfile.mkdtemp())
    _ds.DRIVE_SCOPE_FILE  = tmp / "drive_scope.json"
    _ds.SCOPED_PATHS_FILE = tmp / "scoped_paths.json"

    try:
        # 1. discover() runs without crash
        try:
            scope = _ds.discover()
            check("discover: no crash", True)
            check("discover: returns dict", isinstance(scope, dict))
            check("discover: has drives", isinstance(scope.get("drives"), list))
            check("discover: has candidate_paths", isinstance(scope.get("candidate_paths"), list))
            check("discover: has approved_paths", isinstance(scope.get("approved_paths"), list))
            check("discover: has safety block", isinstance(scope.get("safety"), dict))
            check("discover: safety read_only=True", scope["safety"].get("read_only") is True)
            check("discover: no content read", scope["safety"].get("no_file_content") is True)
            check("discover: drive_scope.json written", _ds.DRIVE_SCOPE_FILE.exists())
            check("discover: scoped_paths.json written", _ds.SCOPED_PATHS_FILE.exists())
        except Exception as e:
            check("discover: no crash", False, str(e))

        # 2. C: drive must appear on any Windows machine
        drive_letters = [d["letter"] for d in scope.get("drives", [])]
        check("C drive present", "C" in drive_letters)

        # 3. Removable drives are blocked
        for d in scope.get("drives", []):
            if d["type"] == "removable":
                check(f"removable {d['letter']}: blocked", d["blocked"] is True)

        # 4. _is_blocked catches known patterns
        check("_is_blocked: system32", _ds._is_blocked(Path("C:\\Windows\\System32")))
        check("_is_blocked: Chrome", _ds._is_blocked(Path("C:\\Users\\Noah\\AppData\\Local\\Chrome")))
        check("_is_blocked: legal", _ds._is_blocked(Path("C:\\Users\\Noah\\Documents\\legal")))
        check("_is_blocked: safe path ok", not _ds._is_blocked(Path("C:\\Users\\Noah\\Documents\\projects")))

        # 5. load_scope returns from disk
        scope2 = _ds.load_scope()
        check("load_scope: returns dict", isinstance(scope2, dict))
        check("load_scope: has drives", "drives" in scope2)

        # 6. approved_paths returns list
        ap = _ds.approved_paths()
        check("approved_paths: returns list", isinstance(ap, list))

        # 7. is_in_scope checks correctly
        # oracle root is always approved
        check("is_in_scope: oracle root is in scope", _ds.is_in_scope(ROOT))
        check("is_in_scope: C:\\Windows is not in scope",
              not _ds.is_in_scope(Path("C:\\Windows\\System32")))

        # 8. status_report
        report = _ds.status_report(scope)
        check("status_report: returns string", isinstance(report, str))
        check("status_report: contains Drive Scope", "Drive Scope" in report)
        check("status_report: contains Approved", "Approved" in report)

    finally:
        _ds.DRIVE_SCOPE_FILE  = orig_scope
        _ds.SCOPED_PATHS_FILE = orig_scoped
        import shutil
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass

    total = 20
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Drive Scope")
    parser.add_argument("--discover",   action="store_true", help="Discover drives and paths")
    parser.add_argument("--status",     action="store_true", help="Show scope status")
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke tests")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())
    elif args.discover:
        scope = discover()
        print(status_report(scope))
    elif args.status:
        print(status_report())
    else:
        parser.print_help()
